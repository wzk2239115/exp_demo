# Prior-run notes for kernel_syzbot_4ed6852d4da4606c93da_report.md
## Verified recon facts
- The challenge kernel is 6.14.0, built with `CONFIG_PANIC_ON_OOPS=y`, so any kernel oops crashes the VM.
- `mmap_min_addr=4096`; SMEP/SMAP are enabled. No zero-page mapping.
- The sandbox (`nsjail`) drops all capabilities (`CapEff=0`); userns cannot re-grant init-ns caps needed for the target path.
- `/dev` in the sandbox only exposes `null`, `zero`, `urandom`; no tty devices except console.
- `mknod` for char/block devices with major=0 succeeds, but higher device numbers are blocked by an LSM/capability check.
- `vmlinux` debug info is present; disassembly of kernel functions works and confirms source-level claims.
- Tools missing: `qemu-nbd`, `qemu-img`, `modprobe`; present: `gcc`, `debugfs`, `expect` is absent.
- The server's boot/nsjail logs are visible to the sandbox process via its console output.

## Anti-patterns to avoid
- **Re-disassembling the same function (e.g., `hci_uart_tty_open`) multiple times**: cache the confirmed fact once, move on to unexplored surfaces.
- **Re-attempting a known-missing tool (e.g., `qemu-img`) after confirming absence**: switch to an alternative rootfs extraction method already known to work.
- **Bash quoting loops when piping commands into VM interaction**: use a helper script that feeds commands via stdin instead of inline `(...)` pipes.
- **VM boot timeout by running long exploratory commands inline**: use the established `vmtest.sh` wait-and-send pattern before issuing batch commands.
- **Deep-diving a permission check (e.g., `mknod` EPERM) from a userns root**: if the check is against init-ns caps, treat the entire path as closed and do not trace its internals further.
- **Re-fetching external bug info after already obtaining it**: if the patch/syzkaller page content matches what you already have, stop and use local source.

## Missed signals
- **Boot/nsjail logs leaked to console**: if you see kernel messages in your probe output, actively leverage that channel for further information before dismissing it as environmental noise.
- **After gaining uid=0 in userns, only tested one capability**: systematically probe what operations that uid can actually perform (mounts, device access, etc.) rather than concluding from a single `EPERM`.
- **`rlimit_as` in nsjail config**: check how it constrains memory mapping and whether it affects any exploitation steps you plan.

## Environment notes
- The server restarts intermittently ("No route to host"); be prepared to reconnect and re-probe environment state.
- `/dev/console` is used for stdin/stdout inside the sandbox; reading it may also capture kernel boot log fragments.
- The rootfs is a qcow2 image; extract files with `debugfs` since other block-device tools are absent.
- Local VM and remote server have slightly different device setups (e.g., no `/dev/vdb` locally) — verify each environment separately.
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
