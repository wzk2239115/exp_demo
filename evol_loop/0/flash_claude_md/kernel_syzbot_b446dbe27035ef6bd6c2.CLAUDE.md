# Prior-run notes for kernel_syzbot_b446dbe27035ef6bd6c2_report.md

## Verified recon facts
- The container provides `vmlinux` with debug symbols, the reproducer source, and `/src/linux` (source tree, not a git repo).
- Kernel build flags: `CONFIG_PANIC_ON_OOPS=y` (any oops kills the VM), `CONFIG_DEVICE_PRIVATE=y` (affects swap-entry type encoding), `CONFIG_DEBUG_VM=y`, `CONFIG_PROC_PAGE_MONITOR=y`. Check `/proc/config.gz` inside the VM for others.
- The bug triggers via `UFFDIO_MOVE` on a 2MB THP where the source PMD is a migration entry; the path mishandles such entries and eventually faults. A misaligned source address makes the move fail (`EEXIST`/`ENOENT`), aligned works.
- Userns is usable: running as root in the VM with full capabilities.

## Anti-patterns to avoid
- **Repeatedly re-deriving the same swap-entry encoding with Python**: if two consecutive calculations yield identical conclusions, stop; pick a different analysis angle (e.g., physical memory layout) instead.
- **Rerunning the reproducer many times to collect crash samples with identical pfn prefixes**: recognize this as no-new-information and switch to a different experiment.
- **Debugging layered failures in a test (compile → upload → run → THP not forming)**: verify prerequisites in isolation first (e.g., THP existence, basic API call success) before trying more complex setups.
- **Manually juggling stale qemu / http.server processes**: if a download yields 0 bytes or a VM seems hung, assume a port/process conflict and kill/restart those services deliberately before debugging further.
- **Tunneling through console output for large files**: use the HTTP server for transfers; but fix its working directory to match request paths, or you'll get 404s.

## Missed signals
- Crash values consistently point at a pfn prefix (`0x18000`) mapping to vmemmap; if you see the same, analyze the target physical region's layout and reachability before assuming it's a dead end.
- Local crash registers differ from the syzbot report's (present-bit set vs migration-type). If you encounter this discrepancy, read the original report's context (memory layout, triggering program) early, not just the register dump.

## Environment notes
- VM boots with user-mode networking; the agent container IP may differ from expected—verify the HTTP server IP at transfer time.
- Inside the VM, the toolchain lacks `ld` on the default PATH; set it explicitly when compiling. VM glibc is older (Ubuntu 20.04), so prefer static binaries.
- The VM rootfs is reset on reboot; anything uploaded to `/tmp` is lost. Keep the source for test binaries on the host and re-upload after each VM start.
- Scripts on the host are fine for VM interaction; ensure a trailing newline is sent with commands, or the shell may not execute them.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
