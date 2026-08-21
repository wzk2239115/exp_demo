#!/bin/bash
# env_check.sh — 开局环境预检,一次性查清约束,省掉前 ~20 步试探。
# 输出: 人类可读(stdout)+ JSON(/workspace/facts.json,供 check_fact.py 查)
# 用法: bash /workspace/tools/env_check.sh
set +e

OUT_JSON="${FACTS_FILE:-/workspace/facts.json}"
mkdir -p "$(dirname "$OUT_JSON")" 2>/dev/null

have() { command -v "$1" >/dev/null 2>&1; }

echo "===== 环境预检 $(date '+%F %T') ====="

# ── 1. ptrace / 调试 ──
PTRACE="unknown"
if [ -w /proc/sys/kernel/yama/ptrace_scope ] 2>/dev/null; then
    PS=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null)
    PTRACE="yama=${PS} (0=同uid可ptrace,1=受限,2=仅祖先,3=禁)"
fi
# 实测能否 ptrace 自身
cat > /tmp/_pt.c <<'EOF'
#include <sys/ptrace.h>
#include <unistd.h>
int main(){ return ptrace(PTRACE_TRACEME,0,0,0)==0?0:1; }
EOF
PT_OK="?"
if have gcc; then
    gcc -x c -o /tmp/_pt /tmp/_pt.c 2>/dev/null && /tmp/_pt >/dev/null 2>&1 \
        && PT_OK="yes" || PT_OK="no(gdb 不可用,转 core dump/LD_PRELOAD)"
fi
echo "[ptrace] $PTRACE ; TRACEME 测试=$PT_OK"

# ── 2. ASLR / KASLR ──
ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)
echo "[ASLR] randomize_va_space=$ASLR (0=off,2=full)"
KALLSYMS=$(head -c 80 /proc/kallsyms 2>/dev/null | tr -d '\0')
case "$KALLSYMS" in
    *0000000000000000*) echo "[kallsyms] 全 0 → 未授权读不到符号,转本地 vmlinux 静态分析"; KSYM="zero";;
    "") echo "[kallsyms] 不可读"; KSYM="unreadable";;
    *) echo "[kallsyms] 可读符号 → 可直接定位内核符号"; KSYM="readable";;
esac
# no_hash_pointers / nokaslr boot param
if grep -qE "no_hash_pointers|nokaslr" /proc/cmdline 2>/dev/null; then
    echo "[kaslr] boot 参数含 nokaslr/no_hash_pointers → 指针可读,任意读无需先破 KASLR"
    KASLR_OFF=1
else
    KASLR_OFF=0
fi

# ── 3. glibc 版本(决定 hook vs IO_FILE)──
GLIBC="?"
if have ldd; then
    GV=$(ldd --version 2>/dev/null | head -1)
    echo "[glibc] $GV"
    GLIBC="$GV"
elif [ -f /lib/x86_64-linux-gnu/libc.so.6 ]; then
    GV=$(/lib/x86_64-linux-gnu/libc.so.6 2>&1 | head -1)
    echo "[glibc] $GV"; GLIBC="$GV"
fi
# 判 __free_hook 是否还在(glibc<2.34 信号)
FH="?"
if [ -f /lib/x86_64-linux-gnu/libc.so.6 ]; then
    if nm -D /lib/x86_64-linux-gnu/libc.so.6 2>/dev/null | grep -q __free_hook; then
        echo "[__free_hook] 存在 → 强信号,优先 hook 路线"; FH="present"
    else
        echo "[__free_hook] 不存在(glibc>=2.34)→ 转 _IO_FILE/exit_funcs/tcache"; FH="absent"
    fi
fi

# ── 4. seccomp ──
SCMP="unknown"
if [ -f /proc/self/status ]; then
    SS=$(grep -i seccomp /proc/self/status 2>/dev/null)
    echo "[seccomp] $SS"
    SCMP="$SS"
fi

# ── 5. NoNewPrivs ──
NNP=$(grep NoNewPrivs /proc/self/status 2>/dev/null | awk '{print $2}')
if [ "$NNP" = "1" ]; then
    echo "[NoNewPrivs] 1 → setuid 提权被禁,走 BPF/CAP_BPF 或内核任意写"
else
    echo "[NoNewPrivs] $NNP"
fi

# ── 6. MEMCG_KMEM / slab 合并 ──
if grep -q CONFIG_MEMCG_KMEM=y /boot/config-* /proc/config.gz 2>/dev/null; then
    echo "[memcg] CONFIG_MEMCG_KMEM=y → kmalloc-cg-* 与 kmalloc-* 隔离,cred_jar 独立,别假设 slab 合并"
    MEMCG=1
else
    MEMCG=0
fi

# ── 7. NX / 栈可执行 ──
NX="?"
if [ -r /proc/self/exe ]; then
    if readelf -l /proc/self/exe 2>/dev/null | grep -qi 'GNU_STACK.*RWE'; then
        echo "[NX] GNU_STACK RWX → 栈可执行,直接栈 shellcode,别费劲 ROP"; NX="off_rwstack"
    else
        NX="on"
    fi
fi

# ── 8. 工具存在性 ──
TOOLS=""
for t in gdb strace ltrace objdump nm readelf pahole python3 pip3 gcc make xxd socat nc curl wget base64 capstone pwntools ropper one_gadget; do
    if have "$t"; then TOOLS="$TOOLS $t"; fi
done
echo "[tools present]$TOOLS"
MISSING=""
for t in gdb strace objdump pahole python3 gcc; do
    have "$t" || MISSING="$MISSING $t"
done
[ -n "$MISSING" ] && echo "[tools missing] 关键缺失:$MISSING"

# ── 9. 权限 ──
mount --bind /proc /tmp/_mbind 2>/dev/null && { echo "[mount] bind 可用"; umount /tmp/_mbind 2>/dev/null; MOUNT=1; } || { echo "[mount] 不可用 → 用 debugfs+dd 提取 rootfs"; MOUNT=0; }
mknod /tmp/_mnod c 1 3 2>/dev/null && { rm -f /tmp/_mnod; echo "[mknod] 可用 → 能造设备节点"; MNOD=1; } || { echo "[mknod] 不可用"; MNOD=0; }
unshare -Ur true 2>/dev/null && echo "[userns] unshare -Ur 可用" || echo "[userns] 不可用"
echo "[id] $(id)"
echo "[caps] $(grep Cap /proc/self/status 2>/dev/null | tr '\n' ' ')"

# ── 10. 内核/目标信息 ──
echo "[uname] $(uname -srmo)"
[ -f /out/README.md ] && echo "[/out] 有 README,先读" || true
ls /out/ 2>/dev/null | head -5 | sed 's/^/[\/out] /'
ls /src 2>/dev/null >/dev/null && echo "[/src] 源码在 /src"
ls /kernel 2>/dev/null >/dev/null && echo "[/kernel] 内核镜像在 /kernel"

# ── 输出 facts.json ──
cat > "$OUT_JSON" <<EOF
{
  "ptrace": "$PT_OK", "aslr": "$ASLR", "kallsyms": "$KSYM",
  "kaslr_off_boot": "$KASLR_OFF", "glibc": "$GLIBC", "free_hook": "$FH",
  "seccomp": "$SCMP", "nonewprivs": "$NNP", "memcg_kmem": "$MEMCG",
  "nx": "$NX", "mount": "$MOUNT", "mknod": "$MNOD",
  "tools_present": "$TOOLS", "tools_missing": "$MISSING",
  "uname": "$(uname -srmo)"
}
EOF
echo "===== 已写入 $OUT_JSON (供 check_fact.py 查询) ====="
