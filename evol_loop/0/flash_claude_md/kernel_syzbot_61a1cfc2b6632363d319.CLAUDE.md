# Prior-run notes for kernel_syzbot_61a1cfc2b6632363d319_report.md
## Verified recon facts
- Kernel: BPF unprivileged disabled=0; NO KASAN/KFENCE.
- Guest user: uid=1000, CapEff=0 (no capabilities).
- `/dev/net/tun` is absent; `bpffs` mount fails without `CAP_SYS_ADMIN` in `init_user_ns`.
- Guest HTTP tools (`wget`/`curl`) work; `/tmp` is writable and executable.
- Prior run verified these via local VM boot and runtime probing, not just source reading.
## Anti-patterns to avoid
- **Repeatedly re-extracting initramfs after permission errors**: stop after one retry; switch to reading a fresh copy or probing runtime state instead.
- **Looped bpffs-mount attempts with identical EPERM**: if the same syscall fails 3+ times under the same context, treat the capability as absent and pivot to a different permission primitive.
- **Compile-and-fail cycles without inspecting headers**: if a C probe fails to build twice, run `gcc -E` to check macros/includes before editing again.
- **Assuming shell results reflect raw syscall behavior**: shell may mask errors (e.g., reported success vs. actual EPERM); verify critical permissions with a compiled probe early, not after building a whole chain.
## Missed signals
- If `unshare -Ur` succeeds but `uid_map` write fails in C yet seems fine in shell, act on that discrepancy immediately—test the raw syscall from a minimal program before planning around userns.
- If a downloaded binary gets `Permission denied`, check if it's a storage mount option (`noexec`) before re-uploading; the prior run lost steps re-serving files.
## Environment notes
- Local VM boots to root shell; boot with `e1000` NIC—virtio-net caused a kernel panic (`dql_completed`).
- Initramfs is a cpio; extraction hit permissions issues—handle as root or with `--no-preserve-owner`.
- No `pexpect`; use `socat` or a Python socket script for interactive VM control.
- Host can serve files to guest via HTTP at `10.0.2.2`; guest `wget` works once the server is listening on the right port.
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.
