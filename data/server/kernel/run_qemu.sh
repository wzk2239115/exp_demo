#!/bin/bash
set -eu

# ─────────────────────────────────────
#  Run QEMU with serial console on a Unix socket.
#  Called by start_qemu.sh.
#
#  Usage: run_qemu.sh
#
#  Environment variables (set by task handler from defense bitmap):
#    NOKASLR       — 1 to disable KASLR (default: 0)
#    NOSMEP        — 1 to disable SMEP (default: 0)
#    NOSMAP        — 1 to disable SMAP (default: 0)
#    USERNS        — 1 to enable user namespaces (default: 0)
#    IO_URING      — 1 to enable io_uring (default: 0)
#    HARDENING     — 1 to enable kernelctf hardening sysctls (default: 0)
#    QEMU_EXTRA_ARGS      — per-task extra qemu args (default empty; e.g. "-vga none")
#    KERNEL_CMDLINE_EXTRA — per-task extra kernel cmdline tokens (default empty; e.g. "pci=nomsi")
# ─────────────────────────────────────

NOKASLR="${NOKASLR:-0}"
NOSMEP="${NOSMEP:-0}"
NOSMAP="${NOSMAP:-0}"
USERNS="${USERNS:-0}"
IO_URING="${IO_URING:-0}"
HARDENING="${HARDENING:-0}"
QEMU_EXTRA_ARGS="${QEMU_EXTRA_ARGS:-}"
KERNEL_CMDLINE_EXTRA="${KERNEL_CMDLINE_EXTRA:-}"

FLAG_FILE="/run/flag"
BZIMAGE="/kernel/bzImage"
RAMDISK="/images/ramdisk_v1.img"

# Prefer qcow2 (compressed) over raw
if [ -f "/images/rootfs_v3.qcow2" ]; then
    ROOTFS="/images/rootfs_v3.qcow2"
    ROOTFS_FORMAT="qcow2"
elif [ -f "/images/rootfs_v3.img" ]; then
    ROOTFS="/images/rootfs_v3.img"
    ROOTFS_FORMAT="raw"
else
    echo "ERROR: no rootfs found" >&2
    exit 1
fi

# ── Build kernel cmdline ──

HARDENING_OPTS=""
if [[ "$HARDENING" == "1" ]]; then
    HARDENING_OPTS="sysctl.kernel.dmesg_restrict=1 sysctl.kernel.kptr_restrict=2 sysctl.kernel.unprivileged_bpf_disabled=2 sysctl.net.core.bpf_jit_harden=1 sysctl.kernel.yama.ptrace_scope=1"
fi

KASLR_OPT=""
if [[ "$NOKASLR" == "1" ]]; then
    KASLR_OPT="nokaslr"
fi

USERNS_OPT=""
if [[ "$USERNS" == "0" ]]; then
    USERNS_OPT="sysctl.user.max_user_namespaces=1"
fi

IO_URING_OPT=""
if [[ "$IO_URING" == "0" ]]; then
    IO_URING_OPT="sysctl.kernel.io_uring_disabled=2"
fi

CMDLINE="console=ttyS0 root=/dev/vda1 rootfstype=ext4 rootflags=discard ro $HARDENING_OPTS $USERNS_OPT $IO_URING_OPT $KASLR_OPT $KERNEL_CMDLINE_EXTRA init=/home/user/run.sh hostname=exphost"

# ── KVM & CPU flags ──

KVM_ARGS=""
CPU_FLAGS=""
if [ -e /dev/kvm ]; then
    KVM_ARGS="-enable-kvm"
    CPU_FLAGS="host"
    [[ "$NOSMEP" == "1" ]] && CPU_FLAGS="${CPU_FLAGS},-smep" || CPU_FLAGS="${CPU_FLAGS},+smep"
    [[ "$NOSMAP" == "1" ]] && CPU_FLAGS="${CPU_FLAGS},-smap" || CPU_FLAGS="${CPU_FLAGS},+smap"
else
    CPU_FLAGS="max"
    [[ "$NOSMEP" == "1" ]] && CPU_FLAGS="${CPU_FLAGS},-smep" || CPU_FLAGS="${CPU_FLAGS},+smep"
    [[ "$NOSMAP" == "1" ]] && CPU_FLAGS="${CPU_FLAGS},-smap" || CPU_FLAGS="${CPU_FLAGS},+smap"
fi

exec qemu-system-x86_64 \
    -m 3.5G \
    -nographic \
    -no-reboot \
    -monitor none \
    $KVM_ARGS \
    -cpu "$CPU_FLAGS" \
    -smp cores=2 \
    -kernel "$BZIMAGE" \
    -initrd "$RAMDISK" \
    -nic user,model=virtio-net-pci \
    -drive "file=$ROOTFS,if=virtio,cache=none,format=$ROOTFS_FORMAT,readonly=on" \
    -drive file=$FLAG_FILE,if=virtio,format=raw,readonly=on \
    $QEMU_EXTRA_ARGS \
    -append "$CMDLINE"
