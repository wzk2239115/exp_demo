#!/bin/bash
# build.sh — 构建 LD_PRELOAD 调试工具箱
# 产物: malloc_trace.so(内存追踪)、func_count.so(函数调用计数)、mem_write.so(内存写监控)
set -e
cd "$(dirname "$0")"
CC="${CC:-gcc}"
echo "[build] 用 $CC 编译..."
$CC -shared -fPIC -O2 -o malloc_trace.so malloc_trace.c -ldl -rdynamic
echo "[build] malloc_trace.so  ✓  (MTRACE=1 LD_PRELOAD=.../malloc_trace.so ./vuln)"
echo "[build] MTRACE_BACKTRACE=1 带栈; MTRACE_FILTER=128 只看 128B chunk"
echo
echo "[fallback] seccomp 连 LD_PRELOAD 都禁时 → 用 core dump:"
echo "  ulimit -c unlimited; ASAN_OPTIONS=disable_coredump=0:abort_on_error=1 ./vuln"
echo "  然后 python3 /workspace/tools/core_analyzer.py /out/vuln"
ls -la *.so 2>/dev/null
