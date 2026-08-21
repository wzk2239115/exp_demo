# Prior-run notes for kernel_syzbot_30754ca335e6fb7e3092_report.md

## Verified recon facts
- Kernel build has **KASAN disabled**; `init_on_alloc=1`; no freelist hardening. Allocator is conventional slab with zeroed allocations.
- `cfg80211_bss_ies` struct size confirmed via source; relevant allocation buckets exist but exact bucket not needed until later.
- Bug trigger: a race in `cfg80211_update_known_bss()` where an IEs object is freed while a comparator still dereferences it. High-level trigger is a scan operation; the repro file exists in the workspace.
- KVM is available; `mac80211_hwsim` is enabled as a module. Local VM testing is possible.

## Anti-patterns to avoid
- **Deep-diving into `kfree_rcu` internals (bulk lists, `debug_rcu_head_queue`)**: you are auditing kernel RCU implementation, not your target. Pivot back to the target's object life cycle after two steps on such internals.
- **Repeatedly re-reading the same `cfg80211_update_known_bss` source with no new question**: the report shows ~10 steps of unproductive re-reading at the end. Each read must produce a hypothesis or a concrete next action; otherwise switch technique (e.g., write a test harness).
- **Three failed upload attempts (wget, curl, python3) in a row from the root shell**: you are stuck retrying the same transfer goal. Before the third attempt, check `ldd` on the tool or use a static binary; a failure signal is `error while loading shared libraries`.
- **Triggering kernel panics during environment tests**: a panic during a layer-1 sanity check (not an exploit) kills your session progress. Run unknown commands in `dmesg`-safe isolation if possible, and always reboot the VM after a panic before relying on it.

## Missed signals
- **A prior successful `wget` inside the nsjail chroot**: step 55 confirmed the chroot's `/usr/bin` works. If you have a working non-root user shell (nsjail), test repro/transfer there *before* wrestling with the root shell's broken dynamic libs.
- **The root shell's `error while loading shared libraries`**: this signal means the rootfs is incomplete, not that the transfer protocol is wrong. Act on it by switching to a static binary or a different shell immediately.
- **The kernel panic right after `python3` ran**: this indicates VM instability, a signal to reboot and re-characterize the environment, not to keep going.

## Environment notes
- VM boots slowly; a "root shell" prompt needs >18s. Use a longer timeout (≥30s) or a prompt-wait loop.
- `nsjail` chroot has no `CapEff` (0); no effective capabilities for normal user. **But unprivileged user namespaces work** (`unshare -Ur -n true` succeeded).
- `unshare -n` (plain netns) fails with EPERM; netns requires userns.
- Root shell lacks `wget`/`curl` working dynamic libs; nsjail user shell has a functional `/usr/bin`.
- No `qemu-nbd`, but `debugfs` exists. The VM image is qcow2; direct filesystem edit via `debugfs` is possible but not necessary if the VM boots.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
