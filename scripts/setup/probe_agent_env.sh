#!/usr/bin/env bash
# 忠实模拟真实评测环境:按 base.py 的容器启动方式起一次性容器,
# 挂载 data/runtime -> /data(ro),在 /workspace 下检查工具可用性。
#
# 与 check_image_tools.sh 的区别:
#   - 后者裸扫镜像内部(不挂载),回答"镜像里有什么";
#   - 本脚本按真实评测姿势(--entrypoint 覆盖、/data 挂载、workdir /workspace)
#     各类任务抽一个镜像,回答"agent 实际能用到什么"。
#     挂载进来的 /data/gdb、/data/nc、/data/node/bin/claude-code.sh 等都会被计入。
#
# 用法(项目根目录执行,需先按 docs/setup.md 备好 data/runtime):
#   bash scripts/setup/probe_agent_env.sh                # 自动每类挑一个已拉取的镜像
#   bash scripts/setup/probe_agent_env.sh <img1> <img2>  # 显式指定镜像
#
# 输出:每镜像一个分节(PATH 内工具清单 / python 模块 / 挂载件 / 网络),末尾小结。

set -u

cd "$(dirname "$0")/../.."   # 项目根

RUNTIME_DIR="data/runtime"

# ── 镜像挑选 ───────────────────────────────────────────
IMAGES=()
if [ $# -gt 0 ]; then
    IMAGES=("$@")
else
    pick() { docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "$1" | sort | head -1; }
    for pat in \
        '^cybergym/arvo:' \
        '^cybergym/v8:' \
        '^cybergym/(kernelctf-target|syzbot-target):'
    do
        img=$(pick "$pat")
        [ -n "$img" ] && IMAGES+=("$img") || echo "WARN: no image matches $pat"
    done
fi
[ ${#IMAGES[@]} -eq 0 ] && { echo "ERROR: no challenge images found"; exit 1; }

echo "探测镜像:"
printf '  %s\n' "${IMAGES[@]}"
echo "挂载: $RUNTIME_DIR -> /data (ro)  workdir: /workspace"
echo

# ── 容器内探测脚本 ─────────────────────────────────────
PROBE='
echo "PATH: $PATH"
echo
echo "== binaries on PATH =="
found=""
miss=""
for t in gcc g++ make python3 pip pip3 node gdb objdump readelf nm strings \
         file pahole ROPgadget ropper checksec qemu-system-x86_64 qemu-img \
         curl wget socat nc ncat xxd cpio debugfs git perl ruby php lua \
         patchelf strace ltrace gcc-9 clang tmux; do
  if command -v $t >/dev/null 2>&1; then found="$found $t"; else miss="$miss $t"; fi
done
echo "FOUND:$found"
echo "MISS:$miss"
echo
echo "== mounted runtime (/data) =="
for f in /data/gdb/gdb /data/nc /data/node/bin/node /data/node/bin/claude-code.sh \
         /data/v8/start.sh; do
  if [ -e "$f" ]; then echo "  have: $f"; else echo "  none: $f"; fi
done
[ -e /data/gdb/gdb ] && /data/gdb/gdb --version 2>/dev/null | head -1 | sed "s/^/  gdb: /"
echo
echo "== python3 modules =="
if command -v python3 >/dev/null 2>&1; then
  for m in pwn capstone keystone unicorn ropper; do
    python3 -c "import $m" 2>/dev/null && echo "  have: $m" || echo "  none: $m"
  done
else
  echo "  (no python3)"
fi
echo
echo "== python version =="
command -v python3 >/dev/null 2>&1 && python3 -V
'

# ── 逐镜像执行 ─────────────────────────────────────────
declare -A ALL_FOUND
for img in "${IMAGES[@]}"; do
  echo "=============================================================="
  echo "### $img"
  echo "=============================================================="
  if [ ! -d "$RUNTIME_DIR" ]; then
    echo "(no $RUNTIME_DIR on host — probing without mounts)"
    docker run --rm --entrypoint bash -w /workspace "$img" -c "$PROBE" 2>&1
  else
    docker run --rm --entrypoint bash -w /workspace \
      -v "$(pwd)/$RUNTIME_DIR:/data:ro" "$img" -c "$PROBE" 2>&1
  fi
  echo
done

# ── 小结 ───────────────────────────────────────────────
echo "=============================================================="
echo "### 小结: 三类镜像共性"
echo "=============================================================="
echo "(对比上面各节 FOUND/MISS 行:三节都缺的工具 = 每题 CLAUDE.md"
echo " Environment notes 的候选;只某类缺 = 该类镜像待补/待说明)"
