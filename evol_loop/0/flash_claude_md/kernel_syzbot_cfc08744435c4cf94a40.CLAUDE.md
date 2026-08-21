# Prior-run notes for kernel_syzbot_cfc08744435c4cf94a40_report.md
## Verified recon facts
- Vulnerable kernel is 6.8.0; KMSAN report confirms a stack/padding infoleak via `copy_siginfo` to userspace.
- `struct sigqueue` is a dedicated slab cache, object size 80 bytes; `struct siginfo` is 128 bytes.
- `sigqueue` has 4-byte padding (offset 12-15) confirmed via pahole/source layout.
- Kernel config: `INIT_ON_ALLOC_DEFAULT_ON`, KASAN, KMSAN are all NOT set/enabled.
- `unprivileged_bpf_disabled=0` is set in the VM kernel.
- Tooling present in container: KVM, qemu, gcc, gdb, python3, nc, objdump, debugfs. Missing: qemu-img.
- vmlinux with full debug symbols is available (1.3GB unpacked); `collect_signal` and `copy_siginfo_to_user` symbols locate via `/proc/kallsyms` in VM.

## Anti-patterns to avoid
- **Looping through all ~50 `kernel_siginfo` senders one-by-one**: Stop after ~5 confirmations that all legitimate paths call `clear_siginfo`; pivot to modeling the buggy allocation site instead of exhaustively enumerating call sites.
- **Repeatedly re-checking KASAN/KMSAN config early**: If confirmed off in the first check, don't revisit it later; treat it as a fixed fact.
- **Fetching the same patch/message from multiple inaccessible sources**: Recognize the signal is bot-protection or JS-rendered (e.g. 403, huge unparseable HTML) and go back to the syzbot page's own `/text?tag=Patch` endpoint before trying new URLs.
- **Modifying VM boot mode without re-verifying environment**: Switching from default nsjail mode to `--root` breaks networking and lib availability; if tools suddenly fail, revert to the working boot mode before debugging the missing tool.
- **Spamming `wget`/`curl` variants for file transfer**: If one fails on missing libs, immediately switch technique (e.g. python3 http server + `nc`) rather than trying the next CLI tool.

## Missed signals
- **If you find a patch diff from the syzbot page, read and apply its insight immediately**: The patch revealed the exact vulnerable function and hint about the fix scope; delaying disassembly to chase commit hashes cost many steps.
- **If disassembly shows `copy_siginfo` performs a full struct copy, trust that as ground truth**: The disassembly result that padding is copied wholesale was strong evidence; don't re-derive it from source reading again.
- **If a fresh-page leak experiment times out after first run, dump the full 48-byte buffer per leak before re-running**: The richer dump should be added to the first attempt to avoid a second compile-run cycle.

## Environment notes
- VM boots with nsjail init by default; `--root` mode gives root shell but breaks network setup—use only on purpose.
- File transfer works via HTTP server on host port 8000; inside VM use `nc` or python, since wget/curl link to stripped libs that error at runtime.
- The rootfs is minimal; static binaries or python are the reliable way to run code inside the VM.
- Previous HTTP server on port 8000 may already be running; check before starting a new one.
- Shell variable expansion mangles commands passed via Python driver; quote or escape `$` and other metacharacters when constructing remote command strings.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
