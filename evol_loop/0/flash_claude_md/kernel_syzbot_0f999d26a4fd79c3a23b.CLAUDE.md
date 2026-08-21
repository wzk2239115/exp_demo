# Prior-run notes for kernel_syzbot_0f999d26a4fd79c3a23b_report.md
## Verified recon facts
- Kernel is 6.8.0-rc4; build config has `CONFIG_PANIC_ON_OOPS=y` and KASAN disabled.
- Root VM exposes `/dev/dri/card0` (vgem), `card1` (vkms), `card2` (bochs-drm); all are root-owned mode 0600.
- The challenge `nsjail.cfg` does **not** mount `/dev/dri`; it has `uidmap` (maps uid 1000), `clone_newnet: false`, and mode `ONCE`.
- Within the jail, after a successful userns+new-mount-namespace setup, mounting a tmpfs works; but `mknod` fails with EPERM because `CAP_MKNOD` is checked against the initial user namespace.
- `devtmpfs` cannot be mounted from a userns (lacks `FS_USERNS_MOUNT`).
- Container lacks `capstone`/`pyelftools` and has no `pip`; relies on `objdump` for disassembly. A working HTTP file server (port 8080/8099) was established for transferring binaries to the VM.

## Anti-patterns to avoid
- **Repeatedly testing `mknod` or `/dev` access from the jail** (each returns "Permission denied"): instead, read the kernel source for the capability check first to confirm the boundary.
- **Debugging rsh command parsing for many iterations** (output truncation/echo issues): use a simpler protocol like `base64` encoding a single command into a file, or write scripts to disk and execute them, before refining interactive parsing.
- **Searching for ROP/stack-pivot gadgets early** when device access is unverified: first confirm the exploit's reachable interface (e.g., open `/dev/dri`), then commit to the exploitation technique.
- **Re-compiling and re-serving the same test binary** to debug a subtle runtime issue: check the binary's own strace output on the target machine first, not its source.

## Missed signals
- If you find you can gain root (uid=0) in the jail but cannot access `/dev/dri`, act on this by enumerating all other capabilities and file-system paths for a device or FD entry point *before* concluding the path is blocked.
- If the VM kernel panics, inspect the panic log for a trace of the faulting object before rebooting; it may reveal a useful kernel state or pointer.
- If you have a FIFO/stdin control issue, verify the qemu command line's stdin redirection with `readlink /proc/<pid>/fd/0` before re-creating the FIFO.

## Environment notes
- The VM boots via `qemu -nographic`; stdin is the serial console. A clean root shell is obtained with `init=/bin/bash` on the kernel command line.
- The remote challenge jail and the local nsjail VM are confirmed identical in mountinfo and restrictions, so local testing is a valid proxy for the remote.
- The toolchain inside the jail has a `collect2` issue; adding `-B/usr/bin` to `gcc` fixes compilation.
- There are no `nft`/`iptables` binaries inside the jail; `capsh` is available.
- `/tmp` on the root VM is on the read-only rootfs; write to `/dev/shm` or a fresh mount point instead.
- `unshare -Ur` is not in the default `PATH`; use absolute path `/usr/bin/unshare` or the busybox equivalent.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
