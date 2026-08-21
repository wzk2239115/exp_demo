# Prior-run notes for kernel_syzbot_bc3d3c58ff37aa23b3a696101f48ec9110c480e2_report.md
## Verified recon facts
- Kernel config: `CONFIG_KASAN` and `CONFIG_X86_SMAP` are NOT set.
- `struct scatterlist` is 32 bytes (verified via gdb, not 40).
- `struct hash_ctx` is 832 bytes; `struct af_alg_sgl` layout was extracted via gdb.
- The crash is a general protection fault from a non-canonical address in the hash path (`md5_update`).
- QEMU (`qemu-system`) is present, but `qemu-img` is not; KVM is available.
- The rootfs is a read-only qcow2; `/tmp` and `/run` are tmpfs, with `/run` initially mounted `noexec`.
- chroot environment has missing shared libs for `wget` (needs `libnettle.so.8`, only `.so.7` present); system `curl` also missing libs.

## Anti-patterns to avoid
- **Repeatedly checking an empty gdb trace log**: after 2-3 empty checks, suspect the serial input is mangled or the target process never ran; verify the command was received intact before deeper debugging.
- **Base64-over-serial file transfer timing out**: if the binary is >100KB, switch to an HTTP transfer from the host immediately.
- **Spawning a new HTTP server only to find port 8000 busy**: before starting one, check for and kill stale `http.server` processes.
- **Zombie qemu processes blocking ports**: before relaunching a VM, aggressively clean up old qemu/gdb processes; check `ps` state (Z) rather than assuming they are gone.
- **Reading source continuously without experimental validation**: after ~20 steps of source analysis on a mechanism, force a small experiment or reformulate the hypothesis to test it.
- **Re-running the same broken gdb `-batch` mode**: if breakpoints never fire and the command exits early, switch to an interactive/non-batch gdb session.

## Missed signals
- When gdb confirmed a `[PIN-RET] res=16` but only 15 valid pages, treat that as the core bug mechanism and pivot to exploitation design immediately, not further confirmatory source reads.
- If a downloaded file (e.g., a trace log) is read and shows key patterns, act on that data to craft the next step before spawning another source-grep or VM session.
- A successful "executing program" output and a crash group appearing in the trace is a decisive signal; preserve that state and build on it rather than restarting the environment.

## Environment notes
- VM boots with `init=/bin/bash` giving a root shell over a serial socket (`-nographic`).
- A custom Python serial client was needed (no `pexpect`); use `\r` as line terminator, as `\n` can mangle commands.
- Network in VM: `eth0` exists but needs manual config; `ifconfig` works, `dhclient` fails (missing libdns). Host is reachable at `172.17.0.1` or `10.0.2.2`.
- Use `LD_LIBRARY_PATH=/chroot/usr/lib/x86_64-linux-gnu` to run binaries like `curl` inside the chroot.
- To execute files on `/run`, must `mount -o remount,exec /run` first.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
