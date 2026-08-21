# Prior-run notes for kernel_syzbot_d4e8dc385d9258220c31_report.md
## Verified recon facts
- Bug triggers a `refcount_t: underflow` WARNING via CAN J1939 session/transaction paths.
- The kernel has `REFCOUNT_SATURATED` active; underflow saturates to `0xC0000000` (not a classic UAF).
- `CONFIG_PANIC_ON_WARN` is off; the repro only produces a WARN, no panic.
- Local KVM boot works (~16s) after initial transient panics; TCG is too slow and loses networking.
- In the rootfs, `wget`/`curl` fail due to missing shared libs; `python3` and `socat` are available.
- `repro` binary compiles to `/workspace/pov/repro`; it is not persisted across VM boots.

## Anti-patterns to avoid
- **Network searches (google/nvd/duckduckgo/bing) returning nothing after 1-2 tries**: abandon online lookup and re-analyze local artifacts (patch, syzbot report).
- **Re-reading the same source files cyclically after the bug model is already confirmed**: switch to code-writing/experiment-driven analysis.
- **KVM panic initially**: don't waste time switching to TCG; retry KVM with a clean boot or adjust env, since it recovered later.
- **Repeating an analysis of session/refcount paths already covered**: record conclusions inline and jump to the next hypothesis.

## Missed signals
- If you find the repro produces only a WARN (not a KASAN UAF), re-evaluate whether the current path can yield memory corruption; look for a second primitive before deep-diving further.
- If KVM becomes usable again, prioritize fast loop experiments (run repro variants, watch dmesg) over static source reading.

# Environment notes
- VM boots each time from a fresh state; transfer any binary/script into the VM via python/socat every launch.
- `read` of a 47KB repro is slow; skim README and sanitizer trace first for the bug essence.
- `/dev/kvm` and 256 CPUs exist on host; nested-virtualization issues can cause transient panics — retry.
- No `qemu-nbd`/`guestfish` for rootfs editing; rely on in-VM commands for filesystem changes.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
