#!/usr/bin/env bash
# build_wheelhouse.sh — 在任务镜像里构建 pwn 工具 wheelhouse,一次性、可复现。
#
# 产物落在 data/runtime/wheels/(宿主机),该目录随 runtime_dir 只读挂载到每个
# 任务容器的 /data/wheels —— 不改镜像,所有容器立即可见。
#
# 之后任务容器内离线安装(阶段二用,无需网络):
#   python3 /data/wheels/get-pip.py -q            # 装 pip(内嵌 wheel,离线可用)
#   python3 -m pip install --user --no-index --find-links /data/wheels pwntools ROPgadget ropper
#
# 用法(评测服务器上):
#   bash scripts/setup/build_wheelhouse.sh [镜像名]      # 缺省随便挑一个 cybergym 镜像
#   bash scripts/setup/build_wheelhouse.sh cybergym/nofuzz:CVE-2021-43848-vul.exp.none
#
# 不同家族镜像(v8/kernel)python 版本可能不同:多跑几次传不同镜像名即可,
# wheel 按 ABI tag 落同一个目录,安装时 pip 自动挑兼容的。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WHEELS="$ROOT/data/runtime/wheels"
mkdir -p "$WHEELS"

if [[ -n "${1:-}" ]]; then
  IMAGE="$1"
else
  IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -m1 '^cybergym/') \
    || { echo "找不到 cybergym 镜像,先跑 scripts/setup/pull_images.sh"; exit 1; }
fi
echo "[wheelhouse] 镜像: $IMAGE"
echo "[wheelhouse] 产物: $WHEELS"

# x86_64 宿主机上的原生镜像不需要 --platform;老 docker daemon 没开 experimental
# 时 --platform 直接报错。仅当宿主机不是 amd64 才显式指定。
PLATFORM_FLAG=()
if [[ "$(uname -m)" != "x86_64" ]]; then
  PLATFORM_FLAG=(--platform linux/amd64)
fi

# -i 必须带:heredoc 走 stdin 进容器,没有 -i 时容器里 bash 读到空脚本、
# 静默 rc=0 退出(上一版就是这么"成功"地什么都没干)
docker run --rm -i "${PLATFORM_FLAG[@]}" -v "$WHEELS:/wheels" "$IMAGE" bash -euxo pipefail <<'BUILD'
export DEBIAN_FRONTEND=noninteractive
# 国内网络走清华镜像;xenial 已 EOL,常规源已清空,必须用 old-releases(清华有镜像)
if grep -q xenial /etc/os-release 2>/dev/null; then
  APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn/ubuntu-old-releases/ubuntu
else
  APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn/ubuntu
fi
echo "deb $APT_MIRROR $(. /etc/os-release && echo $VERSION_CODENAME) main restricted universe multiverse" > /etc/apt/sources.list
apt-get update -qq >/dev/null
apt-get install -y -qq python3-pip curl >/dev/null

PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
echo "[wheelhouse] 容器 python: $PYV"

# py3.5 只认 pip<=20.3.4;新 python 会装最新版 —— get-pip 按 python 版本选 URL
# pip 下载走清华 PyPI 镜像(容器内有网时);xenial 的 get-pip 走官方 bootstrap
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
curl -fsSL "https://bootstrap.pypa.io/pip/${PYV}/get-pip.py" -o /tmp/get-pip.py \
  || curl -fsSL "https://mirrors.aliyun.com/pypi/get-pip/${PYV}/get-pip.py" -o /tmp/get-pip.py
python3 /tmp/get-pip.py -q -i "$PIP_INDEX" 2>/dev/null \
  || python3 /tmp/get-pip.py "pip==20.3.4" -q -i "$PIP_INDEX"
python3 -m pip --version

# 下载(含依赖)。pip>=9 尊重 python_requires,自动选当前 python 兼容的最新版;
# --prefer-binary 尽量拿 wheel 免得目标容器里编译。单个失败不连坐。
for pkg in pwntools ROPgadget ropper checksec.py; do
  python3 -m pip download --prefer-binary -i "$PIP_INDEX" -d /wheels "$pkg" \
    || echo "[wheelhouse] WARN: $pkg 下载失败(继续)"
done
cp -f /tmp/get-pip.py /wheels/get-pip.py

# 离线安装自检:模拟阶段二的无网络安装路径
python3 -m pip install --user --no-index --find-links /wheels pwntools ROPgadget >/dev/null
python3 - <<'CHECK'
from pwn import ELF
import subprocess, sys
ELF("/bin/ls", checksec=False)
print("[wheelhouse] pwntools import OK")
r = subprocess.run([sys.executable, "-m", "ROPgadget", "--binary", "/bin/ls"],
                   capture_output=True, text=True)
assert r.returncode == 0 and "gadgets" not in r.stderr.lower(), r.stderr[:300]
print("[wheelhouse] ROPgadget OK, 示例输出:")
print("\n".join(r.stdout.splitlines()[:2]))
CHECK
echo "[wheelhouse] 容器内自检通过"
BUILD

echo
echo "[wheelhouse] 完成。产物清单:"
ls -lh "$WHEELS" | head -30
echo
echo "[wheelhouse] 阶段二(任务容器内离线安装,无网络):"
echo "  python3 /data/wheels/get-pip.py -q"
echo "  python3 -m pip install --user --no-index --find-links /data/wheels pwntools ROPgadget ropper"
