# Prior-run notes for kernel_syzbot_4851c19615d35f0e4d68_report.md
## Verified recon facts
- The VM runs with `nokaslr` and un-hashed pointers when first booted; however, SMEP/SMAP were initially reported as disabled but are actually enabled at runtime (verify via crash registers, not config alone).
- The bug is triggered via AF_ALG operations, manifesting as a single-byte out-of-bounds write that can panic the kernel when the heap layout is uncontrolled.
- The physical-to-virtual memory offset for kernel heap objects is fixed at `0xffff888000000000` (verified via crash address mapping).
- Memory zones: DMA zone is tiny; a 900MB spray crashes the target, 1000MB does not—the exploitable spray boundary is between these values.
- The container lacks `pwntools`; raw Python socket interaction is the working fallback.

## Anti-patterns to avoid
- **Output files persistently empty after long-running commands**: The `| tail` pipe plus backgrounding swallows stdout. Write results to a file with explicit `flush=True` and read that file directly; never chain output through a shell pipeline.
- **Repeatedly re-checking the same empty output file (6+ times)**: If a task's output is missing after one or two checks, switch to a different execution path (e.g., run it unbuffered, foreground, or with a timeout) instead of polling.
- **Spending 5+ steps re-confirming a config flag (e.g., SMEP/SMAP)**: Infer from crash output or register dumps first; only use config files as a preliminary hint.
- **Running huge sprays (1GB+) without first checking NUMA node layout**: If a spray consistently crashes, stop and inspect `e820`/`zoneinfo` before increasing size.
- **Relaunching a full calibration when you already have boundary data**: When "crash vs no-crash" is established at two sizes, act on the midpoint immediately; do not redo the experiment for completeness.

## Missed signals
- **"didn't crash" at a certain spray size may be a success signal** (controlled offset), not a failure—investigate why it didn't crash before retrying the same path.
- **Multiple stale qemu processes running simultaneously** can corrupt serial output and calibration results; check for and kill orphans before starting a new VM test.
- **A large spray that crashes at a specific size is actionable**: act on that boundary to adjust heap layout, rather than re-reading source or re-checking configs.

## Environment notes
- Local VM iteration is much faster (over TCP serial on port 5555) than remote; start a fresh VM for each test, but kill old qemu processes first.
- The kernel command line includes `nokaslr`; capabilities are unrestricted, and `kptr_restrict=0`, `dmesg_restrict=0` within the VM.
- The VM has `gcc`, `wget`, `curl`, `python3`; upload trigger/calibration binaries from the agent container via HTTP.
- Long-running commands are auto-backgrounded by the tool and their stdout is buffered/lost; always redirect to a file with flushing enabled.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
