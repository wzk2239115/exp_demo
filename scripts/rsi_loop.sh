#!/usr/bin/env bash
# rsi_loop.sh — exp → eval → learn 闭环编排器
#
# 对一批任务反复迭代:每波 exp 是带约束前缀(PROMPT_PREFIX_DIR)的真实跑批,
# eval 用 agent_scorer 评 flag 路径是否消费目标漏洞,learn 把 off-target
# verdict 转成累积禁用清单约束,on-target 的题出列,直到波数耗尽/全部解决。
#
# 轨迹永远是真实行为:本脚本只改"下一波"的指令,绝不动历史轨迹。
#
# 用法:
#   RSI_ROUNDS=3 RSI_TIMEOUT=21600 RSI_WORKERS=50 \
#   GLM_PROVIDER=... GLM_API_KEY=... GLM_MODEL=... MODEL_ALIAS=... \
#   ANTHROPIC_API_KEY=<360 key> \
#   bash scripts/rsi_loop.sh <base> <初始任务清单> [波数]
#
# 参数(env):
#   RSI_ROUNDS            总波数(默认 3;第 1 波可由 RSI_FIRST_ROUND_DIR 指已有 exp)
#   RSI_TIMEOUT           每波任务超时秒(默认 21600=6h)
#   RSI_WORKERS           每波并发(默认 50)
#   RSI_SCORER_WORKERS    评分并发(默认 16)
#   RSI_SCORER_TIMEOUT    scorer 遍超时(默认 1800)
#   RSI_SCORER_JUDGE_TIMEOUT judge 遍超时(默认 1200)
#   RSI_SCORER_MODEL      评分模型(默认 deepseek/deepseek-v4.1-flash,直连 360)
#   RSI_SCORER_API_BASE   评分端点(默认 https://api.360.cn)
#   RSI_FIRST_ROUND_DIR   已有的第 1 波 exp out 目录(out/<name>/run_agent),
#                         给了则跳过第 1 波 exp;配合 RSI_FIRST_SCORES 可跳过评分
#   RSI_FIRST_SCORES      已有的第 1 波评分目录(含 */scorer_result.json)
#   RSI_DRY_RUN=1         只打印计划不执行
#   其余 GLM_*/AGENTS_DIR/ORIG_TASK_DESC 等 env 原样透传给每波 run_as.sh;
#   PROMPT_PREFIX_DIR 由本脚本强制指向约束目录(不要自己设)。
#
# 产物:
#   logs/<base>-rsi/pending_rN.txt   第 N 波任务清单(r1=初始)
#   logs/<base>-rsi/scores_rN/       第 N 波评分
#   logs/<base>-rsi/constraints/     累积约束(PROMPT_PREFIX_DIR 格式,含 __global__.txt 可选手工放入)
#   logs/<base>-rsi/ledger.txt       每波 on-target 出列记录
#   out/<base>-rN/                   第 N 波 exp 输出
#
# 断点续跑: 直接用同一 <base> 重跑本脚本 —— 每波完成后 pending_r(N+1).txt
# 存在即视为已完成,从第一个未完成波继续(exp 中断用同名槽位 resume)。

set -uo pipefail

BASE="${1:?用法: bash scripts/rsi_loop.sh <base> <初始任务清单> [波数] ; 例: bash scripts/rsi_loop.sh user-rsi data/task_ids/user_pending_0924.txt 3}"
TASKS="${2:?缺初始任务清单}"
ROUNDS="${3:-${RSI_ROUNDS:-3}}"

TIMEOUT="${RSI_TIMEOUT:-21600}"
WORKERS="${RSI_WORKERS:-50}"
S_WORKERS="${RSI_SCORER_WORKERS:-16}"
S_TIMEOUT="${RSI_SCORER_TIMEOUT:-1800}"
S_JTIMEOUT="${RSI_SCORER_JUDGE_TIMEOUT:-1200}"
S_MODEL="${RSI_SCORER_MODEL:-deepseek/deepseek-v4.1-flash}"
S_BASE="${RSI_SCORER_API_BASE:-https://api.360.cn}"
FIRST_DIR="${RSI_FIRST_ROUND_DIR:-}"
FIRST_SCORES="${RSI_FIRST_SCORES:-}"
DRY="${RSI_DRY_RUN:-0}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STATE="logs/${BASE}-rsi"
CONST="$STATE/constraints"
mkdir -p "$STATE" "$CONST"

log() { printf '\033[1;35m[rsi %s]\033[0m %s\n' "$(date +%m%d-%H:%M)" "$*"; }

[[ -f "$TASKS" ]] || { echo "任务清单不存在: $TASKS"; exit 1; }
[[ -n "${ANTHROPIC_API_KEY:-}" ]] || { echo "缺 ANTHROPIC_API_KEY (评分器直连 360 用)"; exit 1; }

# ── 波内三步 ──────────────────────────────────────────────
run_exp() {  # $1=波号  $2=pending 文件
  local r=$1 pend=$2 slot="${BASE}-r${r}"
  log "第 ${r} 波 EXP: 槽位=${slot} 任务=$(wc -l < "$pend") 并发=${WORKERS} 超时=${TIMEOUT}s"
  if [[ "$DRY" == "1" ]]; then echo "out/${slot}/run_agent" > "$STATE/exp_r${r}.txt"; return 0; fi
  # PROMPT_PREFIX_DIR 指向累积约束目录;其余 env(模型/防火墙默认/AGENTS_DIR...)
  # 由调用方环境透传。同名槽位已有 result.json 的任务自动跳过 → 波内断点续跑。
  PROMPT_PREFIX_DIR="$CONST" \
  TASKS_FILE="$(realpath "$pend")" \
  MAX_WORKERS="$WORKERS" TIMEOUT="$TIMEOUT" \
    bash run_as.sh "$slot"
  local rc=$?
  echo "out/${slot}/run_agent" > "$STATE/exp_r${r}.txt"
  if [[ $rc -ne 0 ]]; then
    log "WARN: 第 ${r} 波 exp 退出码 ${rc}(部分结果仍可评分;中断则重跑本脚本同 base 续)"
  fi
}

run_eval() {  # $1=波号
  local r=$1
  if [[ -n "$FIRST_SCORES" && $r == 1 ]]; then
    log "第 1 波 EVAL: 复用已有评分 ${FIRST_SCORES}"
    return 0
  fi
  local expdir="out/${BASE}-r${r}/run_agent"
  if [[ -n "$FIRST_DIR" && $r == 1 ]]; then expdir="$FIRST_DIR"; fi
  local scores="$STATE/scores_r${r}"
  log "第 ${r} 波 EVAL: 评分 ${expdir} (只评 flag=true, model=${S_MODEL})"
  if [[ "$DRY" == "1" ]]; then return 0; fi
  uv run agent_scorer/run_scorer.py "$expdir" \
    --scorer claude --model "$S_MODEL" --api-base-url "$S_BASE" \
    --success-only --output-dir "$scores" \
    --workers "$S_WORKERS" --timeout "$S_TIMEOUT" --judge-timeout "$S_JTIMEOUT"
}

learn_scores_dir() {  # $1=波号 → echo 实际评分目录
  local r=$1
  if [[ -n "$FIRST_SCORES" && $r == 1 ]]; then echo "$FIRST_SCORES"; else echo "$STATE/scores_r${r}"; fi
}

run_learn() {  # $1=波号
  local r=$1
  local sdir; sdir="$(learn_scores_dir "$r")"
  log "第 ${r} 波 LEARN: ${sdir} → 累积约束 + pending_r$((r+1))"
  if [[ "$DRY" == "1" ]]; then return 0; fi
  uv run scripts/gen_feedback_constraints.py \
    --scores "$sdir" --constraint-dir "$CONST" \
    --task-list "$STATE/pending_r${r}.txt" \
    --pending-out "$STATE/pending_r$((r+1)).txt" \
    --round $((r+1)) --ledger "$STATE/ledger.txt"
}

# ── 主循环 ────────────────────────────────────────────────
cp -f "$TASKS" "$STATE/pending_r1.txt"
TOTAL=$(wc -l < "$STATE/pending_r1.txt")
log "RSI 闭环启动: base=${BASE} 初始 ${TOTAL} 题, 计划 ${ROUNDS} 波"
log "exp env 透传: GLM_MODEL=${GLM_MODEL:-<未设!>} MODEL_ALIAS=${MODEL_ALIAS:-<未设!>} AGENTS_DIR=${AGENTS_DIR:-无} ORIG_TASK_DESC=${ORIG_TASK_DESC:-无}"

for ((r=1; r<=ROUNDS; r++)); do
  # 该波是否已完成(pending 下一波已生成)?
  if [[ -f "$STATE/pending_r$((r+1)).txt" ]]; then
    log "第 ${r} 波已完成(存在 pending_r$((r+1))),跳过"
    continue
  fi

  # EXP(第 1 波可跳:已有 exp)
  if [[ -z "$FIRST_DIR" || $r -gt 1 ]]; then
    run_exp "$r" "$STATE/pending_r${r}.txt"
  else
    log "第 1 波 EXP: 复用已有 ${FIRST_DIR}"
    echo "$FIRST_DIR" > "$STATE/exp_r${r}.txt"
  fi

  # EVAL
  run_eval "$r"

  # LEARN
  run_learn "$r"

  local_pend="$STATE/pending_r$((r+1)).txt"
  if [[ ! -f "$local_pend" ]]; then
    log "ERROR: learn 未生成 pending_r$((r+1))(异常/dry-run),闭环停止"
    break
  fi
  if [[ ! -s "$local_pend" ]]; then
    log "全部任务 on-target,提前完成 🎉 (ledger: $STATE/ledger.txt)"
    break
  fi
  log "第 ${r} 波结束: 剩余 pending $(wc -l < "$local_pend") 题 → 第 $((r+1)) 波"
done

log "RSI 闭环结束。汇总: ledger=$STATE/ledger.txt 约束=$CONST 各波评分=$STATE/scores_r*"
if [[ -f "$STATE/ledger.txt" ]]; then
  log "on-target 出列记录:"
  cat "$STATE/ledger.txt"
fi
