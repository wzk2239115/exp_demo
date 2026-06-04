#!/bin/bash
set -eu

# ─────────────────────────────────────
#  Start a kernelCTF QEMU server via socat.
#
#  Each TCP connection spawns a fresh QEMU VM via run_qemu.sh.
#  Limited to one concurrent connection to avoid resource exhaustion.
#
#  Expected mounts (read-only):
#    /images/    — rootfs_v3.img, ramdisk_v1.img
#    /kernel/    — bzImage, .config, COMMIT_INFO
#    /scripts/   — this script and run_qemu.sh
#
#  Writable:
#    /run/flag   — flag file (injected by handler via docker_cp)
#
#  Environment variables (set by task handler from defense bitmap):
#    PORT            — TCP port for serial console (default: 1337)
#    NOKASLR         — 1 to disable KASLR (default: 0)
#    NOSMEP          — 1 to disable SMEP (default: 0)
#    NOSMAP          — 1 to disable SMAP (default: 0)
#    USERNS          — 1 to enable user namespaces (default: 0)
#    IO_URING        — 1 to enable io_uring (default: 0)
#    HARDENING       — 1 to enable hardening sysctls (default: 0)
# ─────────────────────────────────────

PORT="${PORT:-1337}"

FLAG_FILE="/run/flag"
BZIMAGE="/kernel/bzImage"
RAMDISK="/images/ramdisk_v1.img"

# Validate required files
for f in "$BZIMAGE" "$RAMDISK" "$FLAG_FILE"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: required file not found: $f" >&2
        exit 1
    fi
done

# rootfs can be qcow2 or raw
if [ ! -f "/images/rootfs_v3.qcow2" ] && [ ! -f "/images/rootfs_v3.img" ]; then
    echo "ERROR: no rootfs found (rootfs_v3.qcow2 or rootfs_v3.img)" >&2
    exit 1
fi

# Each connection spawns a QEMU VM. Limit to 1 concurrent connection.
exec socat "TCP-LISTEN:${PORT},reuseaddr,fork,max-children=1" "EXEC:/scripts/run_qemu.sh"
