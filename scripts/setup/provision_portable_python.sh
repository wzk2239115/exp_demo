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
#   PYPS_TARBALL  直接给本地 tarball 路径(离线场景)
#   PYPS_TAGVER   静态兜底候选,格式 "日期Tag 版本" 如 "20241016 3.12.7"
#   PIP_INDEX     pip 源(默认清华,失败回退官方)
#
# 下载源: astral-sh/python-build-standalone。优先走 GitHub API 解析最新
# release 的准确 asset 名(tag 是纯日期,版本在文件名里,不能瞎拼);
# API 不可用时退回静态候选列表。
#
# 幂等: 重复执行会先在临时目录解压验证,成功才整体替换旧安装。
# 装完跑 validate.sh 校验。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$ROOT/data/runtime/python"

[ "$(uname -m)" = "x86_64" ] || { echo "ERROR: 仅支持 x86_64(评测镜像均为 linux/amd64)"; exit 1; }

# ── 1. 取 python-build-standalone install_only tarball ─────────────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
TARBALL="${PYPS_TARBALL:-}"

# GitHub release 直连在部分国内网络不可达;ghproxy 类镜像可反代同一 URL。
# 按序尝试:直连 → 镜像。
GH_MIRRORS=(
  "https://github.com"
  "https://ghproxy.net/https://github.com"
  "https://gh-proxy.com/https://github.com"
  "https://ghfast.top/https://github.com"
)

fetch() { # fetch <github相对URL路径> <outfile>   相对路径形如 /astral-sh/.../download/...
  local path="$1" out="$2" url base
  for base in "${GH_MIRRORS[@]}"; do
    url="$base$path"
    echo "[python] trying: $url"
    if curl -fSL --retry 2 --connect-timeout 15 -o "$out" "$url"; then
      return 0
    fi
    echo "[python] failed, trying next source ..."
  done
  return 1
}

STATIC_CANDIDATES=(
  "20260814 3.12.14"
  "20241016 3.12.7"
)

if [ -z "$TARBALL" ]; then
  # 1a. GitHub API(可走镜像): 最新 release 里挑 cpython-3.12(其次 3.13) x86_64 install_only
  api_urls="https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest https://ghproxy.net/https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
  rel_path=""
  for api in $api_urls; do
    echo "[python] resolving latest release via $api ..."
    rel_path=$(curl -fsSL --connect-timeout 15 "$api" 2>/dev/null \
      | grep -oE 'browser_download_url": *"[^"]+' \
      | grep -oE '/astral-sh/python-build-standalone/releases/download/[^"]+x86_64-unknown-linux-gnu-install_only\.tar\.gz$' \
      | { grep 'cpython-3\.12\.' || true; } | head -1) || true
    if [ -z "$rel_path" ]; then
      rel_path=$(curl -fsSL --connect-timeout 15 "$api" 2>/dev/null \
        | grep -oE 'browser_download_url": *"[^"]+' \
        | grep -oE '/astral-sh/python-build-standalone/releases/download/[^"]+x86_64-unknown-linux-gnu-install_only\.tar\.gz$' \
        | { grep 'cpython-3\.13\.' || true; } | head -1) || true
    fi
    [ -n "$rel_path" ] && break
  done
  if [ -n "$rel_path" ]; then
    # 剥成相对路径,统一走 fetch 的镜像链
    fetch "$rel_path" "$TMP/python.tar.gz" && TARBALL="$TMP/python.tar.gz"
  else
    echo "[python] API 未解析到 asset(限流或网络),退回静态候选"
  fi
fi

if [ -z "$TARBALL" ]; then
  # 1b. 静态兜底: (tag=纯日期, 版本) 对,asset 名 = cpython-<ver>+<tag>-x86_64-...
  [ -n "${PYPS_TAGVER:-}" ] && STATIC_CANDIDATES=("$PYPS_TAGVER")
  for cand in "${STATIC_CANDIDATES[@]}"; do
    read -r tag ver <<< "$cand"
    if fetch "/astral-sh/python-build-standalone/releases/download/${tag}/cpython-${ver}+${tag}-x86_64-unknown-linux-gnu-install_only.tar.gz" "$TMP/python.tar.gz"; then
      TARBALL="$TMP/python.tar.gz"; break
    fi
  done
fi

[ -n "$TARBALL" ] && [ -f "$TARBALL" ] || {
  echo "ERROR: 拿不到 tarball。检查网络;或手动下载后设 PYPS_TARBALL=<路径> 重跑"
  exit 1
}

# ── 2. 临时目录解压验证,成功才替换 DEST ────────────────────────────
PYSRC="$TMP/pysrc"
mkdir -p "$PYSRC"
# install_only tarball 顶层是 python/ 目录
tar -xzf "$TARBALL" -C "$PYSRC" --strip-components=1
[ -x "$PYSRC/bin/python3" ] || { echo "ERROR: tarball 布局异常(无 bin/python3)"; exit 1; }
# glibc 不兼容会在 --version 就炸,此时不动旧安装
"$PYSRC/bin/python3" --version

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"
mv "$PYSRC" "$DEST"
PY="$DEST/bin/python3"

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
