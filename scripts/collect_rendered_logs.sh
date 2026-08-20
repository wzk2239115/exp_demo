#!/usr/bin/env bash
# collect_rendered_logs.sh — 从评测输出目录收集 claude_code.rendered.log,
# 按靶场名(任务目录名)重命名,集中导出到一个扁平目录。
#
# 用法:
#   bash scripts/collect_rendered_logs.sh <out_root> [目标目录] [--status success|fail|all]
#
# 例子:
#   # 收集 deepseek-flash 槽全部任务(默认导出到 ./collected_logs)
#   bash scripts/collect_rendered_logs.sh out/deepseek-flash/run_agent
#
#   # 只收成功的任务,导出到指定目录
#   bash scripts/collect_rendered_logs.sh out/deepseek-flash/run_agent ./flash_logs --status success
#
#   # 多个槽位一起收(重复文件自动加后缀,不覆盖)
#   bash scripts/collect_rendered_logs.sh out/deepseek-flash/run_agent ./all_logs
#   bash scripts/collect_rendered_logs.sh out/deepseek/run_agent ./all_logs
#
# 产物命名: <任务目录名>.log   (如 user_cybergym_arvo_1832.log)
#   同名冲突(多槽位同任务)时: <任务目录名>.<槽位名>.log
#
# 可选 --status success|fail|all(默认 all):
#   success = result.json 总分 > 0;fail = 有 result.json 且总分 = 0;
#   all     = 有 rendered.log 就收(含无 result.json 的中断任务)
set -euo pipefail

OUT_ROOT="${1:?用法: bash scripts/collect_rendered_logs.sh <out_root> [目标目录] [--status success|fail|all]}"
DEST="collected_logs"
STATUS="all"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --status) STATUS="${2:?--status 需要值: success|fail|all}"; shift 2 ;;
    *) DEST="$1"; shift ;;
  esac
done

mkdir -p "$DEST"

score_of() {  # -> "0.0"/"1.0"/... 或空(无 result.json)
  python3 - "$1" <<'PY' 2>/dev/null || true
import json, sys
with open(sys.argv[1]) as f:
    print(sum(c["score"] for c in json.load(f)["checks"]))
PY
}

count=0 skipped=0
shopt -s nullglob
for log in "$OUT_ROOT"/*/*/logs/claude_code.rendered.log; do
  task_dir="${log%/logs/claude_code.rendered.log}"
  name="$(basename "$task_dir")"
  slot="$(basename "$(dirname "$(dirname "$task_dir")")")"

  if [[ "$STATUS" != "all" ]]; then
    s=$(score_of "$task_dir/result.json")
    if [[ "$STATUS" == "success" ]]; then
      [[ -n "$s" && "$(python3 -c "print(float('$s')>0)" 2>/dev/null)" == "True" ]] || { skipped=$((skipped+1)); continue; }
    else  # fail
      [[ -n "$s" && "$(python3 -c "print(float('$s')==0)" 2>/dev/null)" == "True" ]] || { skipped=$((skipped+1)); continue; }
    fi
  fi

  dst="$DEST/$name.log"
  if [[ -e "$dst" ]]; then  # 多槽位同任务:加槽位名后缀
    dst="$DEST/$name.$slot.log"
  fi
  cp "$log" "$dst"
  count=$((count+1))
done

echo "已收集 $count 个日志 → $DEST/ (按状态过滤跳过 $skipped 个)"
