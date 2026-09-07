#!/bin/bash
# env_check.sh — startup environment pre-check; surveys all constraints once, saving ~20 probing steps.
# Output: human-readable (stdout) + JSON (/workspace/facts.json, queried by check_fact.py)
# Usage: bash /workspace/tools/env_check.sh
set +e

OUT_JSON="${FACTS_FILE:-/workspace/facts.json}"
mkdir -p "$(dirname "$OUT_JSON")" 2>/dev/null

have() { command -v "$1" >/dev/null 2>&1; }

echo "===== Environment pre-check $(date '+%F %T') ====="

# ── 1. ptrace / debugging ──
PTRACE="unknown"
if [ -w /proc/sys/kernel/yama/ptrace_scope ] 2>/dev/null; then
    PS=$(cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null)
    PTRACE="yama=${PS} (0=same-uid ptrace ok,1=restricted,2=ancestors only,3=disabled)"
fi
# Empirically test whether ptrace works on self
cat > /tmp/_pt.c <<'EOF'
#include <sys/ptrace.h>
#include <unistd.h>
int main(){ return ptrace(PTRACE_TRACEME,0,0,0)==0?0:1; }
EOF
PT_OK="?"
if have gcc; then
    gcc -x c -o /tmp/_pt /tmp/_pt.c 2>/dev/null && /tmp/_pt >/dev/null 2>&1 \
        && PT_OK="yes" || PT_OK="no (gdb unusable; switch to core dump/LD_PRELOAD)"
fi
echo "[ptrace] $PTRACE ; TRACEME test=$PT_OK"

# ── 2. ASLR / KASLR ──
ASLR=$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)
echo "[ASLR] randomize_va_space=$ASLR (0=off,2=full)"
KALLSYMS=$(head -c 80 /proc/kallsyms 2>/dev/null | tr -d '\0')
case "$KALLSYMS" in
    *0000000000000000*) echo "[kallsyms] all zeros -> symbols unreadable unprivileged; switch to local vmlinux static analysis"; KSYM="zero";;
    "") echo "[kallsyms] unreadable"; KSYM="unreadable";;
    *) echo "[kallsyms] symbols readable -> kernel symbols can be located directly"; KSYM="readable";;
esac
# no_hash_pointers / nokaslr boot param
if grep -qE "no_hash_pointers|nokaslr" /proc/cmdline 2>/dev/null; then
    echo "[kaslr] boot params contain nokaslr/no_hash_pointers -> pointers readable; arbitrary read needs no KASLR break first"
    KASLR_OFF=1
else
    KASLR_OFF=0
fi

# ── 3. glibc version (decides hooks vs IO_FILE) ──
GLIBC="?"
if have ldd; then
    GV=$(ldd --version 2>/dev/null | head -1)
    echo "[glibc] $GV"
    GLIBC="$GV"
elif [ -f /lib/x86_64-linux-gnu/libc.so.6 ]; then
    GV=$(/lib/x86_64-linux-gnu/libc.so.6 2>&1 | head -1)
    echo "[glibc] $GV"; GLIBC="$GV"
fi
# Check whether __free_hook still exists (glibc<2.34 signal)
FH="?"
if [ -f /lib/x86_64-linux-gnu/libc.so.6 ]; then
    if nm -D /lib/x86_64-linux-gnu/libc.so.6 2>/dev/null | grep -q __free_hook; then
        echo "[__free_hook] present -> strong signal; prefer the hook route"; FH="present"
    else
        echo "[__free_hook] absent (glibc>=2.34) -> switch to _IO_FILE/exit_funcs/tcache"; FH="absent"
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
    echo "[NoNewPrivs] 1 -> setuid privesc banned; go BPF/CAP_BPF or kernel arbitrary write"
else
    echo "[NoNewPrivs] $NNP"
fi

# ── 6. MEMCG_KMEM / slab merging ──
if grep -q CONFIG_MEMCG_KMEM=y /boot/config-* /proc/config.gz 2>/dev/null; then
    echo "[memcg] CONFIG_MEMCG_KMEM=y -> kmalloc-cg-* isolated from kmalloc-*; cred_jar separate; don't assume slab merging"
    MEMCG=1
else
    MEMCG=0
fi

# ── 7. NX / executable stack ──
NX="?"
if [ -r /proc/self/exe ]; then
    if readelf -l /proc/self/exe 2>/dev/null | grep -qi 'GNU_STACK.*RWE'; then
        echo "[NX] GNU_STACK RWX -> stack executable; shellcode straight on the stack; skip ROP"; NX="off_rwstack"
    else
        NX="on"
    fi
fi

# ── 8. tool availability ──
TOOLS=""
for t in gdb strace ltrace objdump nm readelf pahole python3 pip3 gcc make xxd socat nc curl wget base64 capstone pwntools ropper one_gadget; do
    if have "$t"; then TOOLS="$TOOLS $t"; fi
done
echo "[tools present]$TOOLS"
MISSING=""
for t in gdb strace objdump pahole python3 gcc; do
    have "$t" || MISSING="$MISSING $t"
done
[ -n "$MISSING" ] && echo "[tools missing] key tools missing:$MISSING"

# ── 9. permissions ──
mount --bind /proc /tmp/_mbind 2>/dev/null && { echo "[mount] bind available"; umount /tmp/_mbind 2>/dev/null; MOUNT=1; } || { echo "[mount] unavailable -> extract rootfs with debugfs+dd"; MOUNT=0; }
mknod /tmp/_mnod c 1 3 2>/dev/null && { rm -f /tmp/_mnod; echo "[mknod] available -> device nodes can be created"; MNOD=1; } || { echo "[mknod] unavailable"; MNOD=0; }
unshare -Ur true 2>/dev/null && echo "[userns] unshare -Ur available" || echo "[userns] unavailable"
echo "[id] $(id)"
echo "[caps] $(grep Cap /proc/self/status 2>/dev/null | tr '\n' ' ')"

# ── 10. kernel/target info ──
echo "[uname] $(uname -srmo)"
[ -f /out/README.md ] && echo "[/out] README present; read it first" || true
ls /out/ 2>/dev/null | head -5 | sed 's/^/[\/out] /'
ls /src 2>/dev/null >/dev/null && echo "[/src] source at /src"
ls /kernel 2>/dev/null >/dev/null && echo "[/kernel] kernel images at /kernel"

# ── write facts.json ──
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
echo "===== Written to $OUT_JSON (query it with check_fact.py) ====="
