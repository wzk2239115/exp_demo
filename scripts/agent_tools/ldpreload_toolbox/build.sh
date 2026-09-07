#!/bin/bash
# build.sh — build the LD_PRELOAD debugging toolbox
# Artifacts: malloc_trace.so (memory tracing), func_count.so (call counting), mem_write.so (write monitoring)
set -e
cd "$(dirname "$0")"
CC="${CC:-gcc}"
echo "[build] compiling with $CC..."
$CC -shared -fPIC -O2 -o malloc_trace.so malloc_trace.c -ldl -rdynamic
echo "[build] malloc_trace.so  ✓  (MTRACE=1 LD_PRELOAD=.../malloc_trace.so ./vuln)"
echo "[build] MTRACE_BACKTRACE=1 adds stack traces; MTRACE_FILTER=128 watches only 128B chunks"
echo
echo "[fallback] when seccomp bans even LD_PRELOAD -> use core dumps:"
echo "  ulimit -c unlimited; ASAN_OPTIONS=disable_coredump=0:abort_on_error=1 ./vuln"
echo "  then python3 /workspace/tools/core_analyzer.py /out/vuln"
ls -la *.so 2>/dev/null
