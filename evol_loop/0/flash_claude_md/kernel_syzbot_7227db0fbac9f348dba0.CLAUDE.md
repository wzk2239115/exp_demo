# Prior-run notes for kernel_syzbot_7227db0fbac9f348dba0_report.md
## Verified recon facts
- Remote VM is interactive via `vmrun.py`; a local VM (qcow2, root on /dev/vda1) booted successfully with a root shell.
- Key struct sizes verified via debugger/pahole: `netfs_io_stream` offsets (`prepare_write` at 0x20, `issue_write` at 0x28); `netfs_io_request` is 808 bytes.
- Kernel config: `CONFIG_X86_KERNEL_IBT=y`, `no_hash_pointers`, `nokaslr`, `vsyscall=native`, `mmap_min_addr=4096`; SMEP/SMAP active (CR4).
- `panic_on_oops=1` is set.
- 9p filesystem is available (`nodev 9p`) and is the only netfs user lacking a `prepare_write` callback.
- In-VM toolchain: gcc exists but needs `-B/usr/bin` to find ld; no pip, no expect; `script` is available; /tmp is writable (tmpfs, uid 1000).

## Anti-patterns to avoid
- **Spending 40+ steps on deep source audit of netfs internals**: when stuck re-reading the same `direct_write.c`/`client.c` sections with no new info, switch to building a minimal reproducer or inspecting behavior at runtime instead.
- **Re-checking the same fact repeatedly (e.g., 9p availability, SMEP/SMAP status)**: after one failure signal, re-verify once, then proceed with that evidence rather than looping.
- **Rebuilding VM interaction plumbing from scratch (pexpect/pty/heredoc/bash quoting)**: before writing another script, test a one-liner command end-to-end; if it works, fuse it into the existing `vmrun.py` rather than adding new layers.
- **Retrying `curl` to external sources after timeouts (exit 143)**: wait, then try a different route (GitHub API vs raw vs patchwork) rather than hammering the same URL.
- **Analyzing `capable()`/mmap_min_addr write paths when the outcome is already known**: validate the constraint once, then design around it instead of re-deriving it.

## Missed signals
- **`panic_on_oops=1`**: if you confirm this, immediately consider how to keep the kernel alive after a bad call before writing any trigger—standard NULL-deref paths will just panic the box.
- **`mmap_min_addr=4096`**: this is a strong signal that mapping page zero is feasible; act on it as an opportunity early rather than treating it as a side-note.
- **A prior VM panic trace (RIP near `__pfx_...`)**: before reverting to source reading, decode that RIP to see exactly which call site fired and why it crashed—that trace is the fastest evidence of what went wrong.
- **Downloaded patch content was used, but the follow-up fix discussion wasn't mined for trigger nuances**: if you fetch a fix, read the surrounding conversation/commits it references before starting exploitation design.

## Environment notes
- QEMU image can be mounted/inspected with `debugfs` directly (no `qemu-img`); extracted root uses a chroot with gcc-9.
- `run.sh` in the rootfs boots the kernel; kernel cmdline has both `no_hash_pointers` and `nokaslr`—so pointer leaks are plaintext and KASLR is off.
- Remote interaction is flaky: use `stty -echo` carefully (it broke the PS1 handling); prefer single-shot commands over interactive sessions.
- Uploading large base64 blobs to VM fails; compile inside the VM instead, but remember the `-B/usr/bin` ld fix.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
