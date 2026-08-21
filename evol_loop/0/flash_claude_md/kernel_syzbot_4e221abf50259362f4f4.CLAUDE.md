# Prior-run notes for kernel_syzbot_4e221abf50259362f4f4_report.md
## Verified recon facts
- Kernel is 6.17-rc1 with `CONFIG_PREEMPT=y`; boot cmdline has `nokaslr` and user namespaces enabled.
- The bug is a use-after-free in the `mremap` path; the trigger involves a `read(-1,0,0)` syscall followed by concurrent `mremap` calls from forked children.
- Local VM rootfs is a stripped Ubuntu; `/sys/kernel/slab` and `pahole` are unavailable, but `vmlinux` with debug symbols is present in the source tree.
- Struct `vm_area_struct` layout (post-randomization) was confirmed via debug info; relying on source definitions is misleading due to `__randomize_layout`.
- All reachable filesystem `get_unmapped_area` implementations honor `MAP_FIXED`; no path yields a non-aligned result for an unprivileged user.
- `/dev/mem` ignores `MAP_FIXED` but requires `CAP_SYS_RAWIO`; not usable. No hugetlb mount point exists.

## Anti-patterns to avoid
- **Repeatedly re-verifying that all `get_unmapped_area` paths honor `MAP_FIXED`**: once the set of reachable files is enumerated, stop re-auditing; switch to a different attack surface.
- **Spending 20+ steps retrying bot-protected external sites (lore, git.kernel.org) for a fix patch**: if the first two attempts fail, stop fetching; rely on the local source tree and the syzbot reproducer already on disk.
- **Deep-diving into standard, non-buggy functions like `move_page_tables` or `copy_vma`**: read them once to confirm they are standard, then move on; do not re-derive their logic.
- **Repeatedly re-checking known call sites of `vma_multi_allowed`**: that analysis was complete; re-doing it adds no value.
- **Generating stress tests that race without a clear trigger hypothesis**: if 75 iterations produce no warning, reformulate the hypothesis about the race window instead of increasing iterations.

## Missed signals
- If you find a KASAN trace showing `slab_free_after_rcu_debug`, note that without KASAN the RCU-delayed free may be immediate — this tightens timing. Act on this before designing a race.
- If `kptr_restrict=0` but `kallsyms` shows zeroed addresses, do not assume address leak is trivial; pivot to another primitive early.
- If a local VM test succeeds, immediately mirror it on the remote target — environment differences (like extra devices) may invalidate or enable the approach.

## Environment notes
- KVM crashes the VM during this test; boot with `-no-kvm` (slower but stable). The VM shell is interactive through a pty; commands sometimes yield no output on first send, so read after a short wait.
- The container cannot run gcc's default linker; compile with `-B/usr/bin/` to fix the missing `ld`.
- Network to kernel.org and lore is behind Anubis bot protection; syzbot appspot pages are accessible but also partially protected.
- The reproducer file is at `/workspace/pov/repro.syz`; a large `/tmp/fix.patch` exists and is the linux-next merge commit, not the actual fix.

> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
