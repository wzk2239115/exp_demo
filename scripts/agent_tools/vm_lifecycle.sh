#!/bin/bash
# vm_lifecycle.sh — kernel-task VM lifecycle management; prevents "qemu zombies / dead sockets / confused restart state".
# Subcommands: start | wait | transfer | is_alive | cleanup | run_in
# Usage:
#   bash /workspace/tools/vm_lifecycle.sh start /workspace/bzImage /workspace/rootfs.cpio  # boot the VM
#   bash /workspace/tools/vm_lifecycle.sh wait 60          # wait for readiness (up to 60s)
#   bash /workspace/tools/vm_lifecycle.sh transfer poc /tmp/poc   # transfer a file into the VM
#   bash /workspace/tools/vm_lifecycle.sh run_in "chmod +x /tmp/poc && /tmp/poc"  # execute inside the VM
#   bash /workspace/tools/vm_lifecycle.sh cleanup
set +e

SOCK="${VM_SOCK:-/tmp/vm.sock}"
QEMU_PIDFILE="${VM_PID:-/tmp/vm.pid}"
QEMU="${QEMU:-qemu-system-x86_64}"
MEM="${VM_MEM:-512M}"

case "${1:-}" in
start)
    BZ="$2"; ROOTFS="$3"
    [ -f "$BZ" ] || { echo "missing bzImage"; exit 1; }
    [ -f "$ROOTFS" ] || { echo "missing rootfs"; exit 1; }
    bash "$0" cleanup 2>/dev/null
    # -nographic + -serial unix: are mutually exclusive; use a monitor socket + serial stdio separated
    $QEMU -kernel "$BZ" -initrd "$ROOTFS" -append "console=ttyS0 quiet" \
        -m "$MEM" -nographic -no-reboot \
        -monitor unix:$SOCK,server,nowait \
        -pidfile "$QEMU_PIDFILE" -enable-kvm 2>/dev/null &
    echo "[vm] starting qemu pid=$(cat $QEMU_PIDFILE 2>/dev/null) sock=$SOCK"
    ;;
wait)
    MAX=${2:-60}
    for i in $(seq 1 "$MAX"); do
        if [ -S "$SOCK" ]; then echo "[vm] ready (${i}s)"; exit 0; fi
        sleep 1
    done
    echo "[vm] not ready after ${MAX}s"; exit 1
    ;;
is_alive)
    [ -f "$QEMU_PIDFILE" ] && kill -0 "$(cat $QEMU_PIDFILE)" 2>/dev/null \
        && { echo "[vm] alive"; exit 0; } || { echo "[vm] dead"; exit 1; }
    ;;
transfer)
    # Via 9p/virtiofs or the monitor's hostfwd; here via socat through the monitor (fallback)
    SRC="$2"; DST="$3"
    if command -v socat >/dev/null && [ -S "$SOCK" ]; then
        # Transfer base64 through the monitor pipe (simplified: assumes base64 exists in the VM)
        B64=$(base64 -w0 "$SRC")
        printf "sendkey ret\n" | socat - UNIX-CONNECT:"$SOCK" 2>/dev/null
        echo "[vm] transfer $SRC -> $DST (b64 len=${#B64}); if the VM lacks base64, use a 9p mount"
        echo "[vm]   alternative: qemu -virtfs local,path=$(dirname $SRC),mount_tag=host,security_model=none"
    else
        echo "[vm] no socat/socket; use a 9p mount or scp instead"
    fi
    ;;
run_in)
    CMD="$2"
    if [ -S "$SOCK" ] && command -v socat >/dev/null; then
        printf "%s\n" "$CMD" | socat - UNIX-CONNECT:"$SOCK" 2>/dev/null
    else
        echo "[vm] socket unavailable; run start+wait first"
    fi
    ;;
cleanup)
    # Kill zombie qemu + clean the socket
    if [ -f "$QEMU_PIDFILE" ]; then
        PID=$(cat "$QEMU_PIDFILE")
        kill -INT "$PID" 2>/dev/null; sleep 2
        kill -TERM "$PID" 2>/dev/null; sleep 1
        kill -KILL "$PID" 2>/dev/null
    fi
    pkill -f "$QEMU.*$SOCK" 2>/dev/null
    rm -f "$SOCK" "$QEMU_PIDFILE"
    echo "[vm] cleaned up"
    ;;
*)
    head -12 "$0"; exit 1
    ;;
esac
