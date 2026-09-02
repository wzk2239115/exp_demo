#!/usr/bin/env python3
"""Probe every user task's target environment and emit per-task cheat sheets.

Runs ON THE EVAL SERVER (needs docker + the cybergym/n132 images). For each
user task it extracts, without booting the agent:

  * the target binary from the image (mode ``exp.none`` by default)
  * its interpreter/libc via container ``ldd``
  * ASLR sysctl seen inside the container

then analyzes everything with a built-in mini-ELF parser (no pwntools needed):

  * checksec facts: PIE / NX / RELRO / stack canary
  * libc version string, /bin/sh offset, system / __free_hook / __malloc_hook
    offsets (the numbers an exploit needs first)
  * GOT slots for a few classic imported functions (absolute when non-PIE)

Output: ``evol_loop/1/env_cards/<task>.md`` (consumed by
``build_fixdiff_claude_md.py --env-cards``) plus ``summary.tsv``.

Usage:
  python3 scripts/probe_task_env.py [-j 4] [--force] [--image-mode exp.none]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOT_FUNCS = {"free", "malloc", "realloc", "memcpy", "exit", "abort", "puts",
             "printf", "fwrite", "strlen", "system", "fopen"}


# ────────────────────────── mini ELF parser ──────────────────────────

class ELF:
    def __init__(self, data: bytes):
        self.data = data
        if data[:4] != b"\x7fELF" or data[4] != 2:
            raise ValueError("not ELF64")
        (self.e_type,) = struct.unpack_from("<H", data, 0x10)
        (phoff,) = struct.unpack_from("<Q", data, 0x20)
        (shoff,) = struct.unpack_from("<Q", data, 0x28)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)

        self.segments = []
        for i in range(phnum):
            o = phoff + i * phentsize
            p_type, p_flags = struct.unpack_from("<II", data, o)
            p_offset, _p_vaddr, _p_paddr, p_filesz = struct.unpack_from("<QQQQ", data, o + 8)
            self.segments.append({"type": p_type, "flags": p_flags,
                                  "offset": p_offset, "filesz": p_filesz})
        self.sections = {}
        shstr = None
        raw_sections = []
        for i in range(shnum):
            o = shoff + i * shentsize
            (sh_name,) = struct.unpack_from("<I", data, o)
            sh_type, = struct.unpack_from("<I", data, o + 4)
            sh_addr, sh_offset, sh_size = struct.unpack_from("<QQQ", data, o + 16)
            (sh_link,) = struct.unpack_from("<I", data, o + 40)
            raw_sections.append((sh_name, sh_type, sh_addr, sh_offset, sh_size, sh_link))
            if i == shstrndx:
                shstr = (sh_offset, sh_size)
        if shstr:
            base = data[shstr[0]:shstr[0] + shstr[1]]
            for nameoff, stype, addr, off, size, link in raw_sections:
                end = base.find(b"\x00", nameoff)
                nm = base[nameoff:end].decode(errors="replace")
                self.sections[nm] = {"type": stype, "addr": addr, "offset": off,
                                     "size": size, "link": link}
        self._dynsyms()

    def _dynsyms(self) -> None:
        self.symbols: dict[str, int] = {}
        ds = self.sections.get(".dynsym")
        st = self.sections.get(".dynstr")
        if not ds or not st:
            return
        strtab = self.data[st["offset"]:st["offset"] + st["size"]]
        for o in range(ds["offset"], ds["offset"] + ds["size"], 24):
            (st_name,) = struct.unpack_from("<I", self.data, o)
            (st_value,) = struct.unpack_from("<Q", self.data, o + 8)
            if not st_name or not st_value:
                continue
            end = strtab.find(b"\x00", st_name)
            nm = strtab[st_name:end].decode(errors="replace")
            if nm:
                self.symbols[nm] = st_value

    def got_slots(self) -> dict[str, int]:
        """symbol name -> relocation r_offset (GOT slot address)."""
        out = {}
        for secname in (".rela.plt", ".rela.dyn"):
            sec = self.sections.get(secname)
            if not sec:
                continue
            ds = self.sections.get(".dynsym")
            st = self.sections.get(".dynstr")
            if not ds or not st:
                continue
            strtab = self.data[st["offset"]:st["offset"] + st["size"]]
            for o in range(sec["offset"], sec["offset"] + sec["size"], 24):
                r_offset, r_info = struct.unpack_from("<QQ", self.data, o)
                symidx = r_info >> 32
                if not symidx:
                    continue
                so = ds["offset"] + symidx * 24
                (st_name,) = struct.unpack_from("<I", self.data, so)
                end = strtab.find(b"\x00", st_name)
                nm = strtab[st_name:end].decode(errors="replace")
                if nm in GOT_FUNCS and nm not in out:
                    out[nm] = r_offset
        return out

    @property
    def pie(self) -> bool:
        return self.e_type == 3

    @property
    def nx(self) -> bool:
        return not any(s["flags"] & 3 == 3 for s in self.segments if s["type"] == 1)

    @property
    def relro(self) -> str:
        has_relro = any(s["type"] == 0x6474E552 for s in self.segments)
        bind_now = False
        dyn = self.sections.get(".dynamic")
        if dyn:
            for o in range(dyn["offset"], dyn["offset"] + dyn["size"], 16):
                (tag, val) = struct.unpack_from("<qQ", self.data, o)
                if tag == 24:  # DT_BIND_NOW
                    bind_now = True
                elif tag == 30 and val & 8:  # DT_FLAGS BIND_NOW
                    bind_now = True
        if has_relro and bind_now:
            return "full"
        if has_relro:
            return "partial"
        return "none"

    @property
    def canary(self) -> bool:
        return "__stack_chk_fail" in self.symbols


# ────────────────────────── docker helpers ──────────────────────────

def sh(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, ""


def probe_one(entry: dict, image_mode: str, out_dir: Path) -> str | None:
    sanitized = f"user:{entry['entry_name']}".replace(":", "_").replace("/", "_")
    card = out_dir / f"{sanitized}.md"
    image = entry.get("images", {}).get(image_mode)
    if not image:
        return f"{sanitized}: no image mode {image_mode}"
    binary = entry["binary"]

    rc, cid = sh(["docker", "create", "--entrypoint", "/bin/sh", image, "-c", "true"])
    if rc != 0:
        return f"{sanitized}: docker create failed: {cid[:80]}"
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            rc, _ = sh(["docker", "cp", f"{cid}:/out/{binary}", str(tdp / "bin")], 180)
            if rc != 0:
                return f"{sanitized}: binary copy failed"
            bin_data = (tdp / "bin").read_bytes()

            rc, ldd_out = sh(["docker", "run", "--rm", "--entrypoint", "/bin/sh", image,
                              "-c", f"ldd /out/{binary}; cat /proc/sys/kernel/randomize_va_space"])
            aslr = "?"
            libc_path = None
            for line in ldd_out.splitlines():
                m = re.match(r"\s*(\S*libc\.so\.\S*)\s*=>", line)
                if m:
                    libc_path = m.group(1)
                if line.strip().isdigit():
                    aslr = line.strip()
            libc_data = None
            libc_ver = "?"
            if libc_path:
                sh(["docker", "cp", f"{cid}:{libc_path}", str(tdp / "libc")], 180)
                p = tdp / "libc"
                if p.is_file():
                    libc_data = p.read_bytes()
                    m = re.search(rb"GNU C Library[^\\\n]*release version ([0-9.]+)", libc_data)
                    if not m:
                        m = re.search(rb"GLIBC ([0-9]+\.[0-9]+)", libc_data)
                    if m:
                        libc_ver = m.group(1).decode()
    finally:
        sh(["docker", "rm", "-f", cid])

    # ── analysis ──
    lines = ["## Environment cheat sheet (precomputed; verify in 1 command each)",
             f"- image: `{image}`  binary: `/out/{binary}`"]
    try:
        elf = ELF(bin_data)
        lines.append(f"- checksec: PIE={'yes' if elf.pie else 'no (absolute addresses!)'}"
                     f" NX={'yes' if elf.nx else 'NO'} RELRO={elf.relro}"
                     f" canary={'yes' if elf.canary else 'NO'}")
        got = elf.got_slots()
        if got:
            pretty = ", ".join(f"{k}@{hex(v)}" for k, v in sorted(got.items(), key=lambda x: x[1]))
            lines.append(f"- GOT slots ({'vaddr, PIE=offset' if elf.pie else 'absolute'}): {pretty}")
    except Exception as e:  # noqa: BLE001
        lines.append(f"- binary parse failed: {e}")

    lines.append(f"- ASLR (randomize_va_space inside image at probe time): {aslr}"
                 " — re-check with `cat /proc/sys/kernel/randomize_va_space`")
    if libc_data:
        try:
            lelf = ELF(libc_data)
            syms = {}
            for name in ("system", "__free_hook", "__malloc_hook", "__realloc_hook"):
                if name in lelf.symbols:
                    syms[name] = hex(lelf.symbols[name])
            idx = libc_data.find(b"/bin/sh\x00")
            if idx >= 0:
                syms["/bin/sh"] = hex(idx)
            sha1 = __import__("hashlib").sha1(libc_data).hexdigest()[:12]
            lines.append(f"- libc: `{libc_path}` glibc {libc_ver} (sha1 {sha1})"
                         f" — offsets: {', '.join(f'{k}={v}' for k, v in syms.items()) or 'n/a'}"
                         f"{'; hooks absent (>=2.34) -> FSOP/exit_handlers' if '__free_hook' not in lelf.symbols else ''}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"- libc parse failed: {e}")
    else:
        lines.append(f"- libc: not extracted (ldd said: {libc_path or 'n/a'})")
    lines.append("- Delivery reminder: the remote target wraps this binary over TCP with a "
                 "token handshake — read README.md, and reuse its exact framing for your socket.")

    card.write_text("\n".join(lines) + "\n")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", type=Path, default=REPO_ROOT / "src/cybergym/task/metadata.json")
    ap.add_argument("--image-mode", default="exp.none")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evol_loop/1/env_cards")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    meta = json.loads(args.metadata.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    todo = [e for e in meta
            if args.force or not (args.out / f"user:{e['entry_name']}".replace(":", "_").replace("/", "_") + ".md").is_file()]

    errs = []
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as ex:
        futs = {ex.submit(probe_one, e, args.image_mode, args.out): e["entry_name"] for e in todo}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            try:
                err = f.result()
            except Exception as e:  # noqa: BLE001
                err = f"{futs[f]}: {e}"
            if err:
                errs.append(err)
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} done, {len(errs)} errors", file=sys.stderr)
    print(f"probed {len(todo)} tasks, errors: {len(errs)}")
    for e in errs[:20]:
        print("  !", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
