#!/usr/bin/env python3
"""core_analyzer.py — offline debugging when ptrace is banned.

Collects a core dump and uses gdb batch mode to extract the key facts (reading a
core needs no ptrace): crash instruction, registers, backtrace, top of stack,
memcpy/strcpy arguments. Saves the manual-gdb repetition (one task last round
spent 50+ steps hand-driving gdb).

Usage (inside the container):
    python3 /workspace/tools/core_analyzer.py /out/vuln /tmp/core.vuln.1234
    # or auto-find the newest core:
    python3 /workspace/tools/core_analyzer.py /out/vuln
"""
from __future__ import annotations
import glob, os, subprocess, sys, time

GDB = "/data/gdb/gdb"
if not os.path.isfile(GDB):
    for p in ["gdb", "gdb-multiarch"]:
        r = subprocess.run(["which", p], capture_output=True, text=True)
        if r.returncode == 0:
            GDB = r.stdout.strip()
            break

def find_core(binary: str) -> str | None:
    """Auto-find the newest core file (matching the binary name or .core.*)."""
    name = os.path.basename(binary)
    patterns = [
        f"core.{name}.*", f"core.*.{name}.*", "core.*", "/tmp/core*",
    ]
    best = None
    best_mtime = 0
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                m = os.path.getmtime(f)
                if m > best_mtime:
                    best, best_mtime = f, m
            except OSError:
                pass
    return best

def analyze(binary: str, core: str) -> str:
    """Extract the crash scene with gdb batch mode."""
    cmds = "; ".join([
        "set pagination off",
        "set print pretty on",
        "bt full",           # backtrace
        "info registers",    # registers
        "x/i $pc",           # crash instruction
        "x/16gx $sp",        # 16 qwords at stack top
        "x/16gx $rdi",       # rdi points at (many bugs: dest ptr)
        "x/16gx $rsi",       # rsi points at (src ptr for memcpy)
        "info proc mappings",# memory mappings (libc/heap base; break ASLR)
        "maintenance info sections",  # section bases
    ])
    r = subprocess.run(
        [GDB, "-q", "-batch", "-ex", cmds, binary, core],
        capture_output=True, text=True, timeout=60,
    )
    out = r.stdout + ("\n[gdb stderr]\n" + r.stderr if r.stderr.strip() else "")
    # Extract key pointers (for breaking ASLR)
    lines = []
    for line in out.splitlines():
        low = line.lower()
        if any(k in low for k in ["0x7f", "libc", "stack", "heap", "ld-", "ld.so", "/out/"]):
            lines.append(line)
    if lines:
        out += "\n\n===== Key addresses (for breaking ASLR) =====\n" + "\n".join(lines[:20])
    return out

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    binary = sys.argv[1]
    if not os.path.isfile(binary):
        print(f"binary not found: {binary}", file=sys.stderr); sys.exit(1)
    core = sys.argv[2] if len(sys.argv) > 2 else find_core(binary)
    if not core:
        print("No core dump found. Enable coredumps first:", file=sys.stderr)
        print("  ulimit -c unlimited; sysctl kernel.core_pattern=core.%e.%p.%t",
              file=sys.stderr)
        print("  (ASAN: ASAN_OPTIONS=disable_coredump=0:abort_on_error=1)", file=sys.stderr)
        sys.exit(1)
    print(f"[core_analyzer] binary={binary} core={core}")
    print(f"[core_analyzer] gdb={GDB}")
    if not os.path.isfile(GDB):
        print("gdb unavailable! Install gdb-multiarch or put a static gdb at /data/gdb/gdb", file=sys.stderr)
        sys.exit(1)
    result = analyze(binary, core)
    print(result)
    # Write to a file for later reference
    out_file = f"{core}.analysis.txt"
    with open(out_file, "w") as f:
        f.write(result)
    print(f"\n[core_analyzer] analysis written to {out_file}")

if __name__ == "__main__":
    main()
