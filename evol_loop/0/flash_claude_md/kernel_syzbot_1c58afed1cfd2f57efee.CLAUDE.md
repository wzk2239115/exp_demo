# Prior-run notes for kernel_syzbot_1c58afed1cfd2f57efee_report.md
## Verified recon facts
- The vulnerability is a use-after-free in kernel page-table lock handling, triggered via the `move_pages_pte` path.
- The `.config` shows `CONFIG_SLUB=y` and `CONFIG_SPLIT_PTE_PTLOCKS=y`; `LOCKDEP` is enabled, and `ptdesc->ptl` is at a verified offset (offset 32).
- `vmlinux.gz` extraction yields a 0-byte file; use the kernel source and commit info from the provided directory instead.
- The rootfs is an Ubuntu qcow2 (4GB virtual, 64KB clusters) with an initramfs containing a static `/bin/sh` (klibc-based).
- The VM boots to an nsjail sandbox as a non-root user; the boot script (`run.sh`) is inside the rootfs.

## Anti-patterns to avoid
- **Serial console yields only negotiation bytes or nothing after 2 attempts**: stop trying different connection tools (telnet, socat, unix socket) — check the VM launch script for `-serial stdio` and use a pty wrapper (`script`) instead.
- **`rdinit=/bin/sh` or init replacement exits with 127 repeatedly**: do not keep tweaking init args; the rootfs chroot is broken — create a custom initramfs with a debug init to mount and explore the real rootfs.
- **Spending >10 consecutive steps on static source analysis after the bug model is clear**: stop reading code and compile/run the provided reproducer in the VM to get actual runtime feedback (panic, offsets).
- **Manually parsing qcow2 headers with struct.unpack**: print raw bytes first to diagnose format errors before iterating on format strings.
- **Repeatedly checking VM process state when no serial output**: this yields no new information — jump straight to changing how the VM is launched.

## Missed signals
- **If you successfully boot the VM into the nsjail user shell (step ~90)**: act on it immediately by testing the PoC inside the VM; the prior run returned to source audit and never used the working environment.
- **If you have the fix patch hash and a local checkout**: read the downloaded patch file before spawning more web searches; the patch already confirms the vulnerability details and affected code paths.

## Environment notes
- No `telnet`, `expect`, `tmux`, or `screen` available; `socat` and `nc` exist but their serial usage yields no output for this VM setup.
- `script` command (pty) works to capture kernel boot logs and interact with the VM.
- KVM is available; booting the VM locally works and the rootfs can be mounted via `/dev/vda1` from a custom debug initramfs.
- Internet access is available but some sources are blocked (lore 403, DuckDuckGo blocked); GitHub API is reachable.
- The session was cut off at step 101; exploit development was not started.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
