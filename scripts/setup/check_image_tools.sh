#!/usr/bin/env bash
# 扫描已拉取的题目镜像,汇总 agent 常用工具的缺失情况。
#
# 背景:agent 直接跑在每道题自己的镜像里(user→cybergym/arvo、kernel→
# cybergym/kernelctf-target|syzbot-target、v8→cybergym/v8),工具链是否齐全
# 因镜像而异。宿主侧挂载件(gdb/claude-code 等)由 validate.sh 检查,本脚本
# 补上镜像内部这一层:逐镜像起一次性容器,统计每个工具被多少镜像缺失。
#
# 用法(项目根目录执行):
#   bash scripts/setup/check_image_tools.sh                 # 扫全部题目镜像
#   bash scripts/setup/check_image_tools.sh 'cybergym/v8'   # 只扫匹配的镜像
#
# 输出:每镜像一行(OK / MISSING+缺失清单 / UNRUNNABLE),末尾按工具汇总。
# 缺失清单来自上轮评测报告中 agent 实际伸手要过的工具(pahole/ROPgadget/
# capstone/debugfs 等都出现在弯路记录里);py:xxx 为 python3 模块。
#
# 注意:每镜像限时 60s、--rm 即起即删;几百个镜像约需十几分钟。

set -u

FILTER="${1:-^cybergym/(arvo|v8|kernelctf-target|syzbot-target|nofuzz):}"
TOOLS="gcc g++ make python3 pip3 gdb objdump readelf nm strings file pahole \
ROPgadget checksec qemu-system-x86_64 qemu-img curl wget socat nc ncat xxd \
cpio debugfs git perl patchelf strace ltrace"

# 容器内执行的一次性检查:输出 ALL_OK 或 MISS:工具清单
CHECK='
miss=""
for t in '"$TOOLS"'; do command -v $t >/dev/null 2>&1 || miss="$miss $t"; done
if command -v python3 >/dev/null 2>&1; then
  for m in pwn capstone keystone unicorn; do
    python3 -c "import $m" 2>/dev/null || miss="$miss py:$m"
  done
fi
if [ -z "$miss" ]; then echo ALL_OK; else echo "MISS:$miss"; fi'

declare -A MISS_COUNT
n=0
unrunnable=0

while IFS= read -r img; do
  n=$((n+1))
  out=$(timeout 60 docker run --rm --entrypoint bash "$img" -c "$CHECK" 2>/dev/null | tail -1)
  case "$out" in
    ALL_OK)
      echo "OK          $img"
      ;;
    MISS:*)
      echo "MISSING     $img ->$out"
      for t in ${out#MISS:}; do
        MISS_COUNT[$t]=$(( ${MISS_COUNT[$t]:-0} + 1 ))
      done
      ;;
    *)
      echo "UNRUNNABLE  $img"
      unrunnable=$((unrunnable+1))
      ;;
  esac
done < <(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "$FILTER" | sort)

echo
echo "===== 汇总(共 $n 个镜像,UNRUNNABLE $unrunnable 个) ====="
for t in $TOOLS py:pwn py:capstone py:keystone py:unicorn; do
  c=${MISS_COUNT[$t]:-0}
  if [ "$c" -gt 0 ]; then
    echo "$t: $c/$n 个镜像缺失"
  fi
done
