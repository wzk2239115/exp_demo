# Prior-run notes for kernel_syzbot_20ed41006cf9d842c2b5_report.md

## Verified recon facts
- VM boots with a root shell and 3.2GB total RAM, no swap. NUMA: Node0 at 1792MB, Node1 at 2815MB.
- `CONFIG_DEBUG_VM=y`, `CONFIG_PANIC_ON_OOPS=y` — a crash panics the kernel, no post-mortem debugging.
- `unprivileged_userfaultfd` is 0, but `UFFD_USER_MODE_ONLY` flag is required and works in the sandbox. Without it, `userfaultfd` returns EPERM.
- `fail-nth`/`make-it-fail` is present but ineffective for the target allocation path.
- `RLIMIT_FSIZE` is 20MB, limiting memfd sizes. `OOM_DISABLE` via `oom_score_adj` is blocked by a capability check.
- `userfaultfd_ctx_cache` has a constructor, so it does not merge with other slab caches.

## Anti-patterns to avoid
- **Repeatedly trying guessed trigger parameters (e.g., 95/110/134) without a theory**: before varying a numeric knob, derive the expected range from `/proc/zoneinfo` watermarks and page allocation logic.
- **Iterating the same OOM-drain strategy after results plateau**: if memory draining doesn't change the outcome, the failure is not about the drain amount — reformulate the trigger condition or switch trigger vector.
- **Long source-audit sequences without a runtime test**: if you haven't executed a probe in the last few steps, pick the single most uncertain assumption and test it in the VM.
- **Assuming a tool exists based on the host**: check `which`, `ls`, or test the command directly in the VM; glibc-version mismatch from host-built binaries is a known trap (use static linking).
- **Exploring initramfs/qcow2 internals when tools are absent**: if `qemu-img`/`nbd` are missing, stop and use the serial-console-based workflows instead.

## Missed signals
- If you find `/proc/thread-self/fail-nth` exists, verify its runtime effect with a tiny allocation probe before dismissing it — source-level reasoning (e.g., about `ignore_gfp_reclaim`) may be wrong or incomplete.
- If SIGXFSZ appears, check all RLIMITs (`RLIMIT_AS`, `RLIMIT_DATA`, etc.) immediately, not just FSIZE; a different limit may offer an alternative angle.
- If NUMA node asymmetry is found, consider how to use it for targeted allocation control rather than treating memory as one pool.

## Environment notes
- No `expect`, `wget`, or `curl` in the VM. Use `python3 -m http.server` on the host and `urllib` in the guest, configuring network (e.g., `ifconfig eth0 up`) first.
- A local HTTP server on port 8000 (`http://10.0.2.2:8000/`) serves `/workspace` from the host.
- The `vm_cmd.py` serial-control harness works; verify basic commands before sending complex scripts (output capture was a recurring issue).
- `/sys/kernel/debug` is not mounted; sysfs and debugfs are unavailable. `/proc` is the primary introspection source.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
