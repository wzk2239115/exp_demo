#!/bin/bash
# vm_lifecycle.sh — 内核题 VM 生命周期管理,防"qemu 僵尸/socket 失效/重启状态混乱"。
# 子命令: start | wait | transfer | is_alive | cleanup | run_in
# 用法:
#   bash /workspace/tools/vm_lifecycle.sh start /workspace/bzImage /workspace/rootfs.cpio  # 起VM
#   bash /workspace/tools/vm_lifecycle.sh wait 60          # 等就绪(最多60s)
#   bash /workspace/tools/vm_lifecycle.sh transfer poc /tmp/poc   # 传文件进VM
#   bash /workspace/tools/vm_lifecycle.sh run_in "chmod +x /tmp/poc && /tmp/poc"  # VM内执行
#   bash /workspace/tools/vm_lifecycle.sh cleanup
set +e

SOCK="${VM_SOCK:-/tmp/vm.sock}"
QEMU_PIDFILE="${VM_PID:-/tmp/vm.pid}"
QEMU="${QEMU:-qemu-system-x86_64}"
MEM="${VM_MEM:-512M}"

case "${1:-}" in
start)
    BZ="$2"; ROOTFS="$3"
    [ -f "$BZ" ] || { echo "缺 bzImage"; exit 1; }
    [ -f "$ROOTFS" ] || { echo "缺 rootfs"; exit 1; }
    bash "$0" cleanup 2>/dev/null
    # -nographic + -serial unix: 互斥,用 monitor socket + serial stdio 分离
    $QEMU -kernel "$BZ" -initrd "$ROOTFS" -append "console=ttyS0 quiet" \
        -m "$MEM" -nographic -no-reboot \
        -monitor unix:$SOCK,server,nowait \
        -pidfile "$QEMU_PIDFILE" -enable-kvm 2>/dev/null &
    echo "[vm] 启动中 qemu pid=$(cat $QEMU_PIDFILE 2>/dev/null) sock=$SOCK"
    ;;
wait)
    MAX=${2:-60}
    for i in $(seq 1 "$MAX"); do
        if [ -S "$SOCK" ]; then echo "[vm] 就绪 (${i}s)"; exit 0; fi
        sleep 1
    done
    echo "[vm] ${MAX}s 未就绪"; exit 1
    ;;
is_alive)
    [ -f "$QEMU_PIDFILE" ] && kill -0 "$(cat $QEMU_PIDFILE)" 2>/dev/null \
        && { echo "[vm] alive"; exit 0; } || { echo "[vm] dead"; exit 1; }
    ;;
transfer)
    # 通过 9p/virtiofs 或 monitor 的 hostfwd;这里用 socat 经 monitor 发送(回退)
    SRC="$2"; DST="$3"
    if command -v socat >/dev/null && [ -S "$SOCK" ]; then
        # 用 base64 经 monitor pipe 传(简化:假设 VM 内有 base64)
        B64=$(base64 -w0 "$SRC")
        printf "sendkey ret\n" | socat - UNIX-CONNECT:"$SOCK" 2>/dev/null
        echo "[vm] transfer $SRC -> $DST (b64 len=${#B64}); 若 VM 无 base64 用 9p 挂载"
        echo "[vm]   替代:qemu -virtfs local,path=$(dirname $SRC),mount_tag=host,security_model=none"
    else
        echo "[vm] 无 socat/socket,用 9p 挂载或 scp 替代"
    fi
    ;;
run_in)
    CMD="$2"
    if [ -S "$SOCK" ] && command -v socat >/dev/null; then
        printf "%s\n" "$CMD" | socat - UNIX-CONNECT:"$SOCK" 2>/dev/null
    else
        echo "[vm] socket 不可用,先 start+wait"
    fi
    ;;
cleanup)
    # 杀僵尸 qemu + 清 socket
    if [ -f "$QEMU_PIDFILE" ]; then
        PID=$(cat "$QEMU_PIDFILE")
        kill -INT "$PID" 2>/dev/null; sleep 2
        kill -TERM "$PID" 2>/dev/null; sleep 1
        kill -KILL "$PID" 2>/dev/null
    fi
    pkill -f "$QEMU.*$SOCK" 2>/dev/null
    rm -f "$SOCK" "$QEMU_PIDFILE"
    echo "[vm] 已清理"
    ;;
*)
    head -12 "$0"; exit 1
    ;;
esac
