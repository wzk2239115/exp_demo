# Prior-run notes for kernel_syzbot_52c1a7d3e5b361ccd346_report.md

## Verified recon facts
- Challenge kernel has `CONFIG_KASAN` disabled; SMEP/SMAP are enabled.
- Userns creation is allowed (`unshare -Ur` works, maps uid 1000→0), but device node creation (`mknod`) always fails with EPERM—even as root in a fresh userns on tmpfs. The restriction comes from a `capable()` check against the init user namespace via the legacy device cgroup, not from nsjail's explicit config.
- The VM's initramfs is a standard Ubuntu one; booting with `init=/bin/bash` gives a real root shell where `mknod` on tmpfs succeeds.
- The jail's `/dev` contains only empty placeholder files (`full`, `null`, etc.). The real rootfs has `/dev/raw-gadget` (misc 126, mode 600 root:root) and `/dev/bus/usb` with many root hubs (no real devices).
- Kernel source is available at `/src/linux`; the reported defect is a NULL-pointer write in an I2C-over-HID driver (driver name: mcp2221). The bug triggers via malformed USB device enumeration.
- Tool availability: `gcc`, `make`, `python3`, `strace`, `gdb` exist inside the VM; `qemu-img` and `qemu-nbd` do not exist in the agent's container.

## Anti-patterns to avoid
- **Re-confirming the same EPERM on mknod from different angles**: after you've established the failure mechanism via one source-level check, stop re-testing it; switch technique to a different attack surface.
- **Serial-socket flakiness eating dozens of steps**: when the VM serial connection returns nothing or dies, don't retry it more than twice; switch to a different transfer mechanism (e.g., an HTTP server inside the VM) or restart with a fresh, single QEMU process.
- **Pursuing filesystem-based escapes (e.g., open_tree/bind-mount tricks)**: if the goal is to get a writable device node and the test shows you can only read the target dir, drop it and look for a path that doesn't require device creation at all.
- **Spawning a new QEMU/VM repeatedly on a failed boot**: if a boot is panicking or the process is becoming a zombie, read the boot log for the actual error instead of just killing and restarting.
- **Uploading large binaries over serial in chunks**: if the binary is >500 bytes, set up an HTTP download inside the VM early; do not debug base64 chunk corruption.

## Missed signals
- If you find `/dev/kmsg` is readable, consider its potential role before moving on; it was noted but never exploited.
- If you find a `uhid` device (misc minor 239) alongside the target gadget, investigate whether it can create synthetic HID devices; this was left unexplored.
- If you see a network interface (`eth0`) with no IP inside the VM, configure it immediately with a small ctypes-based `SIOCSIFADDR` script; waiting made later file transfers slow and fragile.

## Environment notes
- The VM's rootfs is mounted read-only; use `/run` for writable scratch space.
- The VM's default shell is PID 1 and initramfs-based; no nsjail is set up in local/root boots.
- A remote server (reachable at the challenge target) runs an identical jail; its VM may crash intermittently during boot—don't confuse that with your own setup failure.
- The local and remote jails restrict mounts: `sysfs`/`proc` are not mountable, but `tmpfs` is. The jail shares the network namespace with the host.
- The provided QEMU boot script uses a serial socket for I/O; the socket is exclusive—ensure previous QEMU processes are fully dead before starting a new one.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
