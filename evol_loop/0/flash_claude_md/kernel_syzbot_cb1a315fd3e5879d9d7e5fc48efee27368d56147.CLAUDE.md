# Prior-run notes for kernel_syzbot_cb1a315fd3e5879d9d7e5fc48efee27368d56147_report.md
## Verified recon facts
- Kernel is 6.16.0-rc5; KASAN and SLAB_FREELIST_RANDOM are both disabled in the build config.
- The host container has QEMU and KVM (256 cores), but `qemu-nbd`/`qemu-img` are missing; you can still boot a provided qcow2 directly.
- Inside the VM, rootfs lacks `ip` command; network works via HTTP server hosted on the host container at `/workspace`.
- The VM's nsjail chroot forbids `mknod` (EPERM) and `/dev/vdb` is absent; userns+netns creation works after writing uid_map/gid_map in the correct order.
- `CONFIG_TUN=y` in config, but device nodes for it are not creatable due to the chroot.
## Anti-patterns to avoid
- **Repeated "Exit code 144" and missing log files**: this is a signal that a `pkill` target (likely QEMU) is being killed by the signal, not a script bug; first check for zombie processes before editing harness code.
- **Rewriting serial/harness scripts multiple times for "no output"**: often the script's `waitfor` logic consumed the prompt/output; add explicit, persistent logging to a file and check that file immediately after each run.
- **Long source-dive loops when frames transmit but nothing is captured**: this indicates a timing or packet-sniffing setup flaw (sniffer not ready), not necessarily a kernel bug; restructure to start the sniffer before sending, then re-run the minimal reproducer.
- **Pivoting to complex alternatives without exhausting a simpler verified flag**: if a control-flow condition (like a "collect_md" mode) is confirmed to always pass the gate, test that mode in isolation before building a bridge/VLAN chain.
## Missed signals
- If a device creation call (e.g., `ip6gretap`) succeeds with one mode, check whether that mode's `collect_md` variant bypasses the restrictive routing checks before trying other setups.
- A log line like "entered forwarding state" for a bridge port means bridging is functioning; if outer packets are still unseen, debug the encapsulator's route/source address, not the STP logic again.
- If `/sys` isn't mounted and a stats dump yields nothing, mount or remount `/sys` early in the probe phase instead of inferring failures from missing output.
## Environment notes
- The VM boots with a custom init scheme; `--root` passed to QEMU can start a minimal shell, but the standard init path shows the nsjail constraints immediately.
- The rootfs is extracted via standard tools into a temp dir; HTTP is the reliable file-transfer method into the VM (works from host's `/workspace`).
- Sniffing external GRE packets requires starting the capture in the VM before triggering the send; there is a race where late start misses everything.
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
