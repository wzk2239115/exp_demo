# Prior-run notes for kernel_syzbot_f0c4a4aba757549ae26c_report.md
## Verified recon facts
- `struct net` size is 7936 bytes; `net->ns.count` offset is 0x16c; `net->ns.ops` referenced around 0x1c.
- `struct tipc_aead` is 256 bytes; relevant `crypto` pointer offset verified via gdb.
- Kernel config: `CONFIG_SLAB_FREELIST_RANDOM` is NOT set; `CONFIG_TIPC_MEDIA_UDP=y`; `CONFIG_KALLSYMS_BASE_RELATIVE` appears not set.
- The bug's high-level trigger condition: a use-after-free / refcount issue reachable via TIPC rekeying during netns teardown, specifically in the crypto xmit path.
- `gcm(aes)` is an async crypto algorithm in this kernel (`async: yes`).
- The reproducer's TIPC netlink messages require the `NLA_F_NESTED` flag on nested attributes or they fail with EINVAL.
- TIPC bearer over UDP requires a local interface IP (e.g., 172.20.20.170 on `lo`); `__ip_dev_find` returns NULL otherwise.

## Anti-patterns to avoid
- **Repeatedly patching a VM interaction script after every run (pty errors, missing logs, syntax errors)**: do a single full diagnostic of the script's I/O and error handling before using it for experiments.
- **Trying curl, then wget, then python downloads without checking VM network state**: first verify interface IP and routing setup, then pick one working transfer method.
- **Re-running "measurement" boots that silently lack expected markers**: always grep the output for a sentinel line first and, if absent, inspect the raw boot log for where it stopped before another attempt.
- **Long brute-force comparison of netlink messages against the repro**: if you have the repro source and kernel source, diff the message construction code paths directly to find missing flags or version fields.
- **Rewriting binaries repeatedly without verifying they actually changed**: check the file hash or size after each rebuild; identical output means the build did not pick up your edit.

## Missed signals
- If you find a downloaded reproducer or trace file, read its full contents before spawning another search or test — a single read may confirm the exact trigger sequence.
- If you confirm the crypto operation is async, immediately trace the async completion callback's code path in full before designing experiments around it.
- If you discover a resource is freed by a condition (like `b->up` clearing), check for other paths (not just the obvious one) that still reference the same object before abandoning that avenue.
- If a KEY_SET operation starts succeeding, note that the reproducer's looping lifecycle is now controllable and likely a reliable trigger point; do not discard it.

## Environment notes
- The VM boots to a root shell; rootfs is read-only by default (use `--rw` or a tmpfs like `/w` for writable scratch space).
- `/tmp` is not writable without remount; the full Ubuntu userspace lives under `/chroot` inside the VM.
- `curl` is broken/absent; `wget` exists but depends on shared libs not in the minimal rootfs; `python3` works for simple output. Static binaries transferred via base64 over serial work but can lose bytes—include size/checksum validation after upload.
- No `qemu-img` in the container; direct qcow2 mounting is not possible. A pty-based VM control harness is the working path.
- An HTTP server on the host (e.g., port 8090) is usable for file serving once the VM's network is up, but network availability lags boot—verify `eth0` and `lo` addresses before relying on it.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
