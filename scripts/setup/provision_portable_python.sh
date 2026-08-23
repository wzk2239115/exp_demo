#!/usr/bin/env bash
# provision_portable_python.sh — 一次性:把便携 CPython 3.12 + pwn 工具链
# 装进 data/runtime/python/,随 runtime_dir 只读挂载进每个 agent 容器的
# /data/python,配合 helper.py install phase 的 /usr/local/bin symlink,
# 让三类任务镜像统一拥有 python3(3.12)/pwn/ROPgadget/ropper,不改镜像。
#
# 解决的问题(来自 flash 轮 report 与 probe_agent_env.sh 实测):
#   - 三类镜像容器内均无 pip/pwntools/capstone,agent 只能裸 python;
#   - arvo(user)镜像是 EOL xenial,自带 python 3.5.2(无 f-string);
#   - kernel 容器裸镜像连 python3 都没有。
#
# 产物: data/runtime/python/{bin,lib,...}(install_only 发行版,pip 已内嵌)
#   bin/: python3 python3.12 pip pwn ROPgadget ropper ...
#
# 用法(评测服务器,项目根目录):
#   bash scripts/setup/provision_portable_python.sh
# 可用环境变量:
#   PYPS_VERSION  指定 python-build-standalone tag(默认按候选列表逐个试)
#   PYPS_TARBALL  直接给本地 tarball 路径(离线场景)
#   PIP_INDEX     pip 源(默认清华,失败回退官方)
#
# 幂等: 重复执行会覆盖安装。装完跑 validate.sh 校验。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$ROOT/data/runtime/python"

[ "$(uname -m)" = "x86_64" ] || { echo "ERROR: 仅支持 x86_64(评测镜像均为 linux/amd64)"; exit 1; }

# ── 1. 取 python-build-standalone install_only tarball ─────────────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
TARBALL="${PYPS_TARBALL:-}"

if [ -z "$TARBALL" ]; then
  # (tag, asset 内部版本串) 候选:新 → 老,逐个试
  CANDIDATES=(
    "3.12.7+20241016"
    "3.12.6+20240913"
    "3.13.1+20241210"
  )
  [ -n "${PYPS_VERSION:-}" ] && CANDIDATES=("$PYPS_VERSION")
  for tag in "${CANDIDATES[@]}"; do
    url="https://github.com/astral-sh/python-build-standalone/releases/download/${tag/+/%2B}/cpython-${tag}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    echo "[python] trying $tag ..."
    if curl -fSL --connect-timeout 20 -o "$TMP/python.tar.gz" "$url"; then
      TARBALL="$TMP/python.tar.gz"; break
    fi
  done
fi
[ -n "$TARBALL" ] && [ -f "$TARBALL" ] || { echo "ERROR: 拿不到 python-build-standalone tarball(检查网络,或设 PYPS_TARBALL 用本地包)"; exit 1; }

# ── 2. 解压到 data/runtime/python ─────────────────────────────────
rm -rf "$DEST"
mkdir -p "$DEST"
# install_only tarball 顶层就是 python/ 目录
tar -xzf "$TARBALL" -C "$DEST" --strip-components=1
PY="$DEST/bin/python3"
"$PY" --version

# ── 3. 装 pwn 工具链 ───────────────────────────────────────────────
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
install_pkgs() {
  "$PY" -m pip install --no-cache-dir -q -i "$1" pwntools ropgadget ropper capstone
}
echo "[python] pip install pwntools ropgadget ropper capstone (index: $PIP_INDEX)"
install_pkgs "$PIP_INDEX" || { echo "[python] 清华源失败,回退官方源"; install_pkgs https://pypi.org/simple; }

# ── 4. 冒烟测试 ────────────────────────────────────────────────────
"$PY" - <<'EOF'
import pwn, capstone, ropgadget  # noqa: F401
from pwn import ELF
print("[python] import ok:", pwn.__version__ if hasattr(pwn, "__version__") else "pwn")
EOF
for b in python3 pwn ROPgadget ropper; do
  [ -e "$DEST/bin/$b" ] && echo "[python] bin/$b ✓" || echo "[python] WARN: bin/$b 缺失"
done
echo "[python] done -> $DEST (装好后跑 bash scripts/setup/validate.sh 校验)"
