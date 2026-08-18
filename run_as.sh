#!/usr/bin/env bash
#
# run_as.sh — 多人共享一台机器跑 ExploitGym 评测的入口。
#
# 每个组员用自己的名字(如拼音首字母)对应一份独立"槽位":
#   - 独占的 LLM proxy 端口 + 预算/key(内存态隔离)
#   - 独占的输出目录 out/<name>/run_agent/(互不覆盖、互不跳过)
#   - 独占的日志目录 logs/<name>/
# 共享(只读或按 agent_id 天然隔离,安全):
#   - Docker 镜像、data/runtime、data/tasks
#   - 一个 controller(端口 8666,脚本会自动拉起/复用)
#   - GLM 模型服务
#
# 用法:
#   bash run_as.sh <名字> [run_agent.py 的额外参数...]
#
# 例子:
#   bash run_as.sh wzk                                  # 跑默认 sample.txt
#   bash run_as.sh wzk --tasks-file data/task_ids/v1.txt --max-workers 4
#   bash run_as.sh wzk --first-n 1                      # 只跑 1 个冒烟
#   bash run_as.sh wzk --overwrite                      # 重跑已完成的任务
#   bash run_as.sh --stop wzk                           # 全停 wzk:runner→残留容器→proxy
#
# 安全机制(多用户场景,防止误杀别人/自己在跑的评测):
#   - 同名互斥:同一名字同时只允许一个会话(logs/<名字>/run.lock)。
#     第二个会拒绝启动;FORCE_RUN=1 可接管(先停旧的);并行请用不同名字。
#   - proxy 永不被自动杀:glm_config 变化(含 git pull 后 sha 变化)只警告不重启。
#     要应用新配置:先 --stop 再跑,或 FORCE_PROXY_RESTART=1(按 admin key 精确重启)。
#   - 所有 kill 都按唯一身份(admin key / pidfile+cmdline 复核)匹配,绝不按端口裸杀。
#   - 评测容器带 label exploitgym.owner=<名字>(env CYBERGYM_OWNER),--stop 只清自己的。
#
# 可用环境变量覆盖默认值(或写进 .glm_env 文件,已 gitignore):
#   GLM_BASE_URL (默认 https://api.360.cn/v1)
#   GLM_MODEL    (默认 deepseek/deepseek-v4-pro;改 provider/模型时配置会自动重生成)
#   MODEL_ALIAS  (默认 deepseek-v4-pro,run_agent 的 --model / 路由别名)
#   GLM_API_KEY  (调用 360 等需要鉴权的 provider 时必填,写进 .glm_env)
#   TASKS_FILE   (默认 data/task_ids/sample.txt)
#   AGENT        (默认 claude_code)
#   BUDGET       (默认 1000)
#   TIMEOUT      (默认 3600 秒)
#   MAX_WORKERS  (默认 1)
#   PROXY_PORT_BASE (默认 4001;第 N 个组员用 4000+N)
#   CONTROLLER_PORT (留空则按槽位自动派 8700+slot,各人独立,不复用 8666)
#   FORCE_RUN=1            同名接管:先停掉在跑的会话再启动
#   FORCE_PROXY_RESTART=1  启动前按 admin key 重启自己的 proxy(加载新 glm_config)
#   STOP_GRACE (默认 90)   --stop 给 runner 的 graceful 退出时间(秒),超时升级 SIGKILL

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────
#  可配置项
# ─────────────────────────────────────────────
# 若存在 .glm_env(已 gitignore),先 source 它 —— 组员把 GLM_API_KEY 等放进去,
# 直接 `bash run_as.sh <名字>` 即可,无需每次在命令行带环境变量。
# 语义:命令行 > .glm_env > 内置默认。先快照命令行已设的变量,source 后回填,
# 否则 .glm_env 里的旧 key 会悄悄覆盖命令行传入的新 key(proxy 装错 key → 1004)。
_ENV_KEYS=(GLM_PROVIDER GLM_BASE_URL GLM_MODEL MODEL_ALIAS GLM_API_KEY GLM_ANTHROPIC_BASE \
           TASKS_FILE AGENT BUDGET TIMEOUT MAX_WORKERS \
           PROXY_PORT_BASE CONTROLLER_PORT_BASE CONTROLLER_PORT \
           FORCE_PROXY_RESTART FORCE_RUN STOP_GRACE INTERACTIVE DIRECT)
declare -A _CLI_ENV=()
for _k in "${_ENV_KEYS[@]}"; do
  if [[ -n "${!_k+x}" ]]; then _CLI_ENV[$_k]=${!_k}; fi
done
if [[ -f "$PROJECT_ROOT/.glm_env" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.glm_env"
fi
for _k in "${!_CLI_ENV[@]}"; do
  export "$_k=${_CLI_ENV[$_k]}"
done
unset _k _ENV_KEYS _CLI_ENV

GLM_BASE_URL="${GLM_BASE_URL:-https://api.360.cn/v1}"
GLM_MODEL="${GLM_MODEL:-deepseek/deepseek-v4-pro}"
MODEL_ALIAS="${MODEL_ALIAS:-deepseek-v4-pro}"
GLM_API_KEY="${GLM_API_KEY:-dummy}"

AGENT="${AGENT:-claude_code}"
TASKS_FILE="${TASKS_FILE:-data/task_ids/sample.txt}"
BUDGET="${BUDGET:-1000}"
TIMEOUT="${TIMEOUT:-3600}"
MAX_WORKERS="${MAX_WORKERS:-1}"

CONTROLLER_PORT_BASE="${CONTROLLER_PORT_BASE:-8700}"
CONTROLLER_PORT="${CONTROLLER_PORT:-}"   # 留空则按槽位自动派(8700+slot-1),避免复用别人在 8666 上的 controller
PROXY_PORT_BASE="${PROXY_PORT_BASE:-4001}"

GLM_CONFIG=""   # 在 main 里按 per-user 设置(logs/<名字>/glm_config.yaml),避免多人/多模型共用一份互相覆盖
SLOTS_FILE="$PROJECT_ROOT/logs/user_slots.tsv"
# controller 的三个共享 secret(token salt / flag seed / api key)持久化到这里。
# controller 全组共用一个,所以这三个值也得全组一致;run_agent.py 必须读到它们才能
# 验证 token / flag。文件权限 600(能读到就能伪造 token)。
CONTROLLER_SECRETS_FILE=""   # 在 main 里按 per-user 设置(logs/<名字>/controller.secrets.env)

# ─────────────────────────────────────────────
#  小工具
# ─────────────────────────────────────────────
log()  { printf '\033[36m[run_as]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[run_as]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[run_as]\033[0m %s\n' "$*" >&2; exit 1; }

new_uuid() {
  cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid;print(uuid.uuid4())'
}

# 任一 HTTP 响应码(含 404)都算"端口在监听"
listening() {
  local code
  code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null) || code=000
  [[ "$code" != "000" ]]
}

bridge_ip() {
  local ip
  ip=$(ip -4 addr show docker0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}') || true
  [[ -n "$ip" ]] || die "无法获取 docker0 桥 IP,检查 docker 是否运行"
  echo "$ip"
}

# ─────────────────────────────────────────────
#  进程身份与安全 kill
#  多用户场景铁律:只按唯一身份(admin key / pidfile+cmdline 复核)杀进程,
#  绝不按端口/PID 裸杀 —— 端口可能撞车,PID 会复用,裸杀就是 8/10 那次事故。
# ─────────────────────────────────────────────
# pid 是否活着(zombie 视为已死,等父进程收尸不影响判断)
proc_alive() {
  local pid="$1"
  [[ -d "/proc/$pid" ]] || return 1
  grep -q '^State:[[:space:]]*Z' "/proc/$pid/status" 2>/dev/null && return 1
  return 0
}

# 校验 pid 的 cmdline 匹配 pattern(防 PID 复用误杀无辜进程)。
# pattern 按 ERE 解释 —— 与 pgrep -f 的匹配语义保持一致,否则 pgrep 匹配上、
# 复核却失败(比如 "cybergym.llm_proxy.*<key>" 里的 .* 在字面匹配下永远不中)。
pid_cmdline_matches() {
  local pid="$1" pattern="$2" cmd
  [[ -d "/proc/$pid" ]] || return 1
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null) || return 1
  [[ -z "$cmd" ]] && return 1
  printf '%s' "$cmd" | grep -qE -- "$pattern"
}

# 按 pattern 杀进程:pgrep 预筛 + cmdline 逐个复核,先 TERM 后 KILL(超时升级)。
# 返回 0=杀到过进程,1=没匹配到。
safe_pkill_wait() {
  local pattern="$1" timeout="${2:-10}" killed=() pid i alive
  for pid in $(pgrep -f -- "$pattern" 2>/dev/null); do
    pid_cmdline_matches "$pid" "$pattern" || continue
    kill -TERM "$pid" 2>/dev/null || true
    killed+=("$pid")
  done
  if [[ ${#killed[@]} -eq 0 ]]; then return 1; fi
  for ((i = 0; i < timeout * 10; i++)); do
    alive=0
    for pid in "${killed[@]}"; do
      if proc_alive "$pid"; then alive=1; fi
    done
    if [[ "$alive" -eq 0 ]]; then return 0; fi
    sleep 0.1
  done
  for pid in "${killed[@]}"; do
    if proc_alive "$pid"; then kill -KILL "$pid" 2>/dev/null || true; fi
  done
  return 0
}

# 递归收集 pid 的所有后代(含自身)
descendant_pids() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    descendant_pids "$child"
  done
  echo "$pid"
}

# 谁打开了 run.lock(诊断锁死/泄漏用;持有 fd 的进程 ≈ 持锁进程)
lock_holders() {
  local lockfile="$1" p f tgt
  for p in /proc/[0-9]*; do
    for f in "$p"/fd/*; do
      tgt=$(readlink "$f" 2>/dev/null) || continue
      [[ "$tgt" == "$lockfile" ]] && { echo "${p#/proc/}"; break; }
    done
  done
}

# ─────────────────────────────────────────────
#  槽位登记(每人一个稳定数字,决定端口)
# ─────────────────────────────────────────────
assign_or_get_slot() {
  local name="$1"
  mkdir -p "$(dirname "$SLOTS_FILE")"
  (
    flock 9
    local existing=""
    if [[ -f "$SLOTS_FILE" ]]; then
      existing=$(grep -P "^$name\t" "$SLOTS_FILE" | cut -f2 || true)
    fi
    if [[ -n "$existing" ]]; then
      echo "$existing"
      exit 0
    fi
    local max=0 v
    if [[ -f "$SLOTS_FILE" ]]; then
      while IFS=$'\t' read -r _ v; do
        v="${v:-0}"
        (( v > max )) && max=$v
      done < "$SLOTS_FILE"
    fi
    local new=$((max + 1))
    printf '%s\t%d\n' "$name" "$new" >> "$SLOTS_FILE"
    echo "$new"
  ) 9>"$SLOTS_FILE.lock"
}

# ─────────────────────────────────────────────
#  GLM 代理配置(全组共享一份)
# ─────────────────────────────────────────────
ensure_glm_config() {
  # 配置由 provider/agent/GLM_BASE_URL/GLM_MODEL/MODEL_ALIAS 派生,写进 marker;任一变化
  # 或缺 drop_params → 自动重生成。
  #   provider=anthropic       → 原生 Anthropic /v1/messages(GLM)
  #   provider=openai + codex  → /v1/responses(gpt-5.6-sol 只支持 responses API)
  #   provider=openai(默认)    → /v1/messages→chat/completions(claude_code)
  local provider="${GLM_PROVIDER:-openai}"
  # 把代码版本(git sha)写进 marker:git pull 之后旧 proxy 仍是老代码在跑,
  # 必须重启才能加载新逻辑。marker 变化 → 重生成配置 → ensure_proxy 重启。
  local git_sha
  git_sha=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)
  local marker="# src: v5 | provider=$provider | agent=$AGENT | $GLM_BASE_URL | $GLM_MODEL | $MODEL_ALIAS | git=$git_sha"
  if [[ -f "$GLM_CONFIG" ]] && grep -qF "$marker" "$GLM_CONFIG" && grep -q 'drop_params' "$GLM_CONFIG"; then
    return 0
  fi
  [[ -f "$GLM_CONFIG" ]] && log "$GLM_CONFIG 配置已变,重新生成"
  GLM_CONFIG_REGEN=1   # 通知 ensure_proxy:跑着的旧 proxy 要重启加载新配置
  log "生成 $GLM_CONFIG (provider=$provider, agent=$AGENT, model=$GLM_MODEL)"

  local model_line base_line settings_block extra_model_entry=""

  if [[ "$provider" == "anthropic" ]]; then
    # 原生 Anthropic:litellm 直连 /v1/messages,不做协议翻译
    model_line="      model: anthropic/$GLM_MODEL"
    base_line="      api_base: \"${GLM_ANTHROPIC_BASE:-https://api.360.cn}\""
    settings_block="litellm_settings:
  drop_params: true"
  elif [[ "$AGENT" == "codex" ]]; then
    # codex 走 /v1/responses。litellm 对 responses 只剥一次 openai/,
    # 所以 360 的 openai/gpt-5.6-sol 需要双前缀:openai/openai/gpt-5.6-sol
    if [[ "$GLM_MODEL" == openai/* ]]; then
      model_line="      model: openai/$GLM_MODEL"
    else
      model_line="      model: openai/$GLM_MODEL"
    fi
    base_line="      api_base: \"$GLM_BASE_URL\""
    settings_block="litellm_settings:
  drop_params: true"
    # codex 不需要 claude-sonnet-4-6 别名
    extra_model_entry="__SKIP__"
  else
    # claude_code 走 /v1/messages → chat/completions。
    # litellm 的 /v1/messages→openai 翻译路径对 "openai/" 前缀会多剥一次。
    if [[ "$GLM_MODEL" == openai/* ]]; then
      model_line="      model: openai/openai/$GLM_MODEL"
    else
      model_line="      model: openai/$GLM_MODEL"
    fi
    base_line="      api_base: \"$GLM_BASE_URL\""
    settings_block="litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true
  drop_params: true"
  fi

  # 构建 YAML(根据是否需要 claude-sonnet-4-6 别名)
  if [[ "$extra_model_entry" == "__SKIP__" ]]; then
    cat > "$GLM_CONFIG" <<EOF
$marker
model_list:
  - model_name: $MODEL_ALIAS
    litellm_params:
$model_line
$base_line
      api_key: "os.environ/GLM_API_KEY"
      input_cost_per_token: 0.0
      output_cost_per_token: 0.0
$settings_block
EOF
  else
    cat > "$GLM_CONFIG" <<EOF
$marker
model_list:
  - model_name: $MODEL_ALIAS
    litellm_params:
$model_line
$base_line
      api_key: "os.environ/GLM_API_KEY"
      input_cost_per_token: 0.0
      output_cost_per_token: 0.0
  - model_name: claude-sonnet-4-6
    litellm_params:
$model_line
$base_line
      api_key: "os.environ/GLM_API_KEY"
      input_cost_per_token: 0.0
      output_cost_per_token: 0.0
$settings_block
EOF
  fi
}

# ─────────────────────────────────────────────
#  共享 controller 的 secret(全组一致,持久化)
# ─────────────────────────────────────────────
# 从 controller 日志恢复某个 secret(兼容被 pre_run 起的 controller)
# 用法: recover_secret <logfile> <ENV_VAR>
recover_secret() {
  local logfile="$1" var="$2"
  [[ -f "$logfile" ]] || return 1
  grep -oP "^\s*${var}=\K\S+" "$logfile" 2>/dev/null | tail -1
}

write_secrets_file() {
  {
    printf "export CYBERGYM_SERVER_SALT='%s'\n" "${CYBERGYM_SERVER_SALT:-}"
    printf "export CYBERGYM_SERVER_FLAG_SEED='%s'\n" "${CYBERGYM_SERVER_FLAG_SEED:-}"
    printf "export CYBERGYM_SERVER_API_KEY='%s'\n" "${CYBERGYM_SERVER_API_KEY:-}"
  } > "$CONTROLLER_SECRETS_FILE"
  chmod 600 "$CONTROLLER_SECRETS_FILE"
}

# 保证三个 CYBERGYM_SERVER_* 已 export 并落盘(controller 与 run_agent 必须读到同一份)
ensure_controller_secrets() {
  local ctl_url="http://$BRIDGE:$CONTROLLER_PORT/"
  mkdir -p "$(dirname "$CONTROLLER_SECRETS_FILE")"

  # 1) 已有持久化文件 → 直接 source(全组复用)
  if [[ -f "$CONTROLLER_SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONTROLLER_SECRETS_FILE"
    log "controller secret 复用 $CONTROLLER_SECRETS_FILE"
    return 0
  fi

  # 2) controller 已在跑(自己之前起的,在本端口)→ 从它的日志恢复
  if listening "$ctl_url"; then
    local logfiles=(
      "$LOG_DIR/controller.log"
      "$LOG_DIR/controller/server_manager.log"
    )
    local var val lf found=0
    for var in CYBERGYM_SERVER_SALT CYBERGYM_SERVER_FLAG_SEED CYBERGYM_SERVER_API_KEY; do
      val=""
      for lf in "${logfiles[@]}"; do
        val=$(recover_secret "$lf" "$var") && [[ -n "$val" ]] && break || val=""
      done
      if [[ -n "$val" ]]; then
        export "$var=$val"; found=$((found + 1))
      else
        warn "未能从 controller 日志恢复 $var"
      fi
    done
    if (( found == 3 )); then
      write_secrets_file
      log "controller secret 从日志恢复并写入 $CONTROLLER_SECRETS_FILE"
      return 0
    fi
    die "controller 在跑但三个 secret 无法恢复($CONTROLLER_SECRETS_FILE 也不存在)。建议:停掉该 controller 让本脚本重新起,或用 pre_run.py 重启后重跑本脚本。"
  fi

  # 3) controller 没跑 → 生成新的(格式对齐 generate_secret:prefix-<uuid4>)
  export CYBERGYM_SERVER_SALT="cg-$(new_uuid)"
  export CYBERGYM_SERVER_FLAG_SEED="sf-$(new_uuid)"
  export CYBERGYM_SERVER_API_KEY="cybergym-$(new_uuid)"
  write_secrets_file
  log "controller secret 新生成并写入 $CONTROLLER_SECRETS_FILE"
}

# ─────────────────────────────────────────────
#  每人独占的 controller(独立端口+secret,绝不复用 8666 上别人的)
# ─────────────────────────────────────────────
ensure_controller() {
  local url="http://$BRIDGE:$CONTROLLER_PORT/"
  ensure_controller_secrets   # 先保证三个 CYBERGYM_SERVER_* 已 export

  if listening "$url"; then
    log "controller 复用中 :$CONTROLLER_PORT"
    return 0
  fi
  log "启动 $USER_NAME 的 controller :$CONTROLLER_PORT"
  mkdir -p "$LOG_DIR/controller"
  (
    flock 9
    if ! listening "$url"; then
      # 继承已 export 的 CYBERGYM_SERVER_*;setsid 让 Ctrl+C 不连坐;不带 --network,
      # 目标容器走默认桥,agent(默认桥)够得着。
      # 8>&- 9>&-:绝不能继承 run.lock(fd8) 和启动锁(fd9) —— controller 常驻,
      # 泄漏的锁 fd 会让同名互斥锁永久卡死
      setsid uv run -m cybergym.server \
        --host "$BRIDGE" --port "$CONTROLLER_PORT" \
        --log_dir "$LOG_DIR/controller" \
        8>&- 9>&- \
        > "$LOG_DIR/controller.log" 2>&1 < /dev/null &
      echo $! > "$LOG_DIR/controller.pid"
    fi
    for _ in $(seq 1 40); do
      listening "$url" && exit 0
      sleep 0.5
    done
    exit 1
  ) 9>"$LOG_DIR/controller.start.lock"
  listening "$url" || die "controller 启动失败,看 $LOG_DIR/controller.log"
  log "controller 已启动 :$CONTROLLER_PORT (pid $(cat "$LOG_DIR/controller.pid"))"
}

# ─────────────────────────────────────────────
#  每人的 LLM proxy(端口/预算/key 独占)
# ─────────────────────────────────────────────
ensure_proxy() {
  local health="http://$BRIDGE:$PROXY_PORT/health/liveliness"
  local root="http://$BRIDGE:$PROXY_PORT/"
  local admin_key_file="$LOG_DIR/admin.key"

  # FORCE_PROXY_RESTART=1:无条件按 admin key 重启自己的 proxy —— 换 GLM_API_KEY
  # 后必须用这个(key 藏在 proxy 进程环境里,复用旧 proxy = 用旧 key;config marker
  # 不含 key,不会自动触发)。按 admin key 精确匹配,不按端口裸杀。
  # 不强制时:glm_config 变了也【绝不】自动杀(在跑任务会被连坐,8/10 事故),
  # 只警告继续用旧配置。
  if [[ "${FORCE_PROXY_RESTART:-0}" == "1" ]] && { listening "$health" || listening "$root"; }; then
    local old_key=""
    if [[ -f "$admin_key_file" ]]; then
      old_key=$(cat "$admin_key_file" 2>/dev/null || true)
    fi
    if [[ -z "$old_key" ]]; then
      old_key=$(grep -oP 'Admin key for /budget endpoints:\s*\K\S+' "$LOG_DIR/llm_proxy.log" 2>/dev/null | tail -1 || true)
    fi
    if [[ -z "$old_key" ]]; then
      die "FORCE_PROXY_RESTART 找不到旧 proxy 的 admin key;先跑: bash run_as.sh --stop $USER_NAME 清场后重试"
    fi
    log "FORCE_PROXY_RESTART=1 → 按 admin key 重启 proxy(加载新 key/新配置)"
    safe_pkill_wait "cybergym.llm_proxy.*$old_key" 10
    rm -f "$LOG_DIR/proxy.pid" "$admin_key_file"
  elif [[ "${GLM_CONFIG_REGEN:-0}" == "1" ]] && { listening "$health" || listening "$root"; }; then
    warn "glm_config 已重新生成,但在跑的 proxy 继续用旧配置(不自动重启,避免打断在跑任务)
    应用新配置: FORCE_PROXY_RESTART=1 bash run_as.sh … 或先 bash run_as.sh --stop $USER_NAME 再重跑"
  fi

  if listening "$health" || listening "$root"; then
    if [[ -f "$admin_key_file" ]]; then
      CYBERGYM_ADMIN_KEY=$(cat "$admin_key_file")
    else
      CYBERGYM_ADMIN_KEY=$(grep -oP 'Admin key for /budget endpoints:\s*\K\S+' "$LOG_DIR/llm_proxy.log" 2>/dev/null | tail -1 || true)
    fi
    [[ -n "$CYBERGYM_ADMIN_KEY" ]] || die "proxy :$PROXY_PORT 已在跑但找不到 admin key,删 logs/$USER_NAME/llm_proxy.log 后重试,或换 PROXY_PORT_BASE"
    # 在跑的 proxy 必须持有这个 admin key:防 slots 表被重置导致端口撞车后
    # 误复用别人的 proxy(那会让任务打到别人的模型/key/预算上)
    if ! pgrep -f -- "cybergym.llm_proxy.*$CYBERGYM_ADMIN_KEY" >/dev/null 2>&1; then
      die "端口 :$PROXY_PORT 在监听,但对应进程不持有 $USER_NAME 的 admin key(槽位冲突/别人的 proxy?)。
  不要 kill 它。检查 logs/user_slots.tsv 是否被动过,或换 PROXY_PORT_BASE 重试。"
    fi
    log "proxy 复用中 :$PROXY_PORT (admin ${CYBERGYM_ADMIN_KEY:0:20}…)"
    return 0
  fi

  # 兜底:端口没在正常监听但已有 llm_proxy 进程绑着它(刚启动/挂死/别人的)→
  # 明确报冲突,不盲启(盲启会 bind 失败绕远路,还看不清是谁占的)
  if pgrep -f -- "cybergym.llm_proxy.* --port $PROXY_PORT " >/dev/null 2>&1; then
    die "端口 :$PROXY_PORT 已被某个 llm_proxy 进程占用但未正常监听(启动中/挂死/别人的):
$(pgrep -af -- "cybergym.llm_proxy.* --port $PROXY_PORT " 2>/dev/null | head -3 | sed 's/^/    /')
  如果是自己的挂死 proxy: bash run_as.sh --stop $USER_NAME 后重试" 
  fi

  CYBERGYM_ADMIN_KEY="cgym-admin-$USER_NAME-$(openssl rand -hex 8)"
  printf '%s' "$CYBERGYM_ADMIN_KEY" > "$admin_key_file"
  chmod 600 "$admin_key_file"
  export GLM_API_KEY

  log "启动 $USER_NAME 的 LLM proxy :$PROXY_PORT"
  # claude_code 走 /v1/messages(Anthropic 协议)。OpenAI 模型时 litellm 默认路由到
  # Responses API(360 不支持),此 env var 强制 /v1/messages → /chat/completions;
  # anthropic provider(原生透传)时必须为 false,否则会做双重协议转换、thinking 被剥。
  # (server.py setup_proxy 也会按 config 内容再设一次,这里保持 env 一致)
  if [[ "${GLM_PROVIDER:-openai}" == "anthropic" ]]; then
    export LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES=false
  else
    export LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES=true
  fi
  # setsid:把 proxy 放进独立会话,Ctrl+C 中断 run_as.sh 时不会被同进程组连坐杀掉
  # 8>&-:同样不能继承 run.lock 的 fd —— proxy 跨会话常驻,泄漏锁 fd 会把互斥锁
  # 卡死到 proxy 被 --stop 为止(而且旧版 --stop 又被锁堵住,死循环)
  setsid uv run -m cybergym.llm_proxy \
    --host "$BRIDGE" --port "$PROXY_PORT" \
    --admin-key "$CYBERGYM_ADMIN_KEY" \
    --config "$GLM_CONFIG" \
    --default-budget "$BUDGET" \
    8>&- \
    > "$LOG_DIR/llm_proxy.log" 2>&1 < /dev/null &
  echo $! > "$LOG_DIR/proxy.pid"

  for _ in $(seq 1 40); do
    listening "$root" && break
    sleep 0.5
  done
  listening "$root" || die "proxy 启动失败,看 $LOG_DIR/llm_proxy.log"
  log "proxy 已启动 :$PROXY_PORT"
}

stop_proxy() {
  # 优先按完整 admin key 匹配(唯一);找不到 key 才退回用户名前缀。
  # safe_pkill_wait 会逐个复核 cmdline,不会误杀别人的 proxy。
  local key="" pattern
  if [[ -f "$LOG_DIR/admin.key" ]]; then
    key=$(cat "$LOG_DIR/admin.key" 2>/dev/null || true)
  fi
  if [[ -z "$key" ]]; then
    key=$(grep -oP 'Admin key for /budget endpoints:\s*\K\S+' "$LOG_DIR/llm_proxy.log" 2>/dev/null | tail -1 || true)
  fi
  pattern="cybergym.llm_proxy.*cgym-admin-$USER_NAME"
  if [[ -n "$key" ]]; then
    pattern="cybergym.llm_proxy.*$key"
  fi
  if safe_pkill_wait "$pattern" 10; then
    rm -f "$PROJECT_ROOT/logs/$USER_NAME/proxy.pid"
    log "已停止 $USER_NAME 的 proxy"
  else
    warn "$USER_NAME 没有在跑的 proxy"
  fi
}

# ─────────────────────────────────────────────
#  --stop 分层关停:runner → 自己的残留容器 → proxy(controller 保留)
# ─────────────────────────────────────────────
# 优雅停掉评测 runner:SIGINT(等价 Ctrl+C,worker 会走 finally 做容器清理/收日志)
# → 超时 SIGTERM → 再超时 SIGKILL。
stop_runner() {
  local pidfile="$LOG_DIR/runner.pid"
  if [[ ! -f "$pidfile" ]]; then
    log "没有 runner.pid,$USER_NAME 没有在跑的 runner"
    return 0
  fi
  local pid
  pid=$(cat "$pidfile" 2>/dev/null || true)
  if [[ -z "$pid" ]]; then
    rm -f "$pidfile"
    return 0
  fi
  if ! proc_alive "$pid"; then
    log "runner (pid $pid) 已不在,清理 stale pidfile"
    rm -f "$pidfile"
    return 0
  fi
  # cmdline 复核:pid 复用后可能指向无辜进程,绝不能按裸 pid 杀
  if ! { pid_cmdline_matches "$pid" "run_agent.py" || pid_cmdline_matches "$pid" "interactive.py"; }; then
    warn "pid $pid 活着但不是 $USER_NAME 的 runner(cmdline 不匹配,可能 PID 复用),跳过"
    rm -f "$pidfile"
    return 0
  fi
  log "停止 runner (pid $pid): SIGINT(graceful,任务收尾可能要几十秒)…"
  local p all
  all=$(descendant_pids "$pid")
  for p in $all; do kill -INT "$p" 2>/dev/null || true; done
  local grace="${STOP_GRACE:-90}" i=0
  while proc_alive "$pid" && (( i < grace )); do
    sleep 1
    i=$((i + 1))
  done
  if proc_alive "$pid"; then
    warn "graceful 超时(${grace}s),升级 SIGTERM"
    kill -TERM "$pid" 2>/dev/null || true
    i=0
    while proc_alive "$pid" && (( i < 15 )); do
      sleep 1
      i=$((i + 1))
    done
    if proc_alive "$pid"; then
      warn "仍在运行,SIGKILL(强杀可能残留容器/丢部分日志)"
      all=$(descendant_pids "$pid")
      for p in $all; do kill -KILL "$p" 2>/dev/null || true; done
    fi
  fi
  rm -f "$pidfile"
  if proc_alive "$pid"; then
    warn "runner 未完全退出(pid $pid),手动检查: ps -fp $pid"
  else
    log "runner 已停止"
  fi
}

# 只清理自己 label 的评测容器(强杀 runner 后的兜底;正常 graceful 退出不会走到有残留)
clean_own_containers() {
  command -v docker >/dev/null 2>&1 || return 0
  local ids
  ids=$(docker ps -aq --filter "label=exploitgym.owner=$USER_NAME" 2>/dev/null || true)
  if [[ -z "$ids" ]]; then
    log "没有 $USER_NAME 的残留评测容器"
    return 0
  fi
  log "清理 $USER_NAME 的残留评测容器(label=exploitgym.owner):$(echo "$ids" | tr '\n' ' ')"
  # shellcheck disable=SC2086
  docker rm -f $ids >/dev/null 2>&1 || true
}

# --stop 的入口:先停 runner,再在 run.lock 保护下清理容器/proxy,
# 防止和"刚好同时新启动的同名会话"竞争。
stop_slot() {
  stop_runner
  # flock 只是尽量和"同时在启动的新会话"串行;抢不到也必须继续 —— 下面的清理
  # (容器按 label、proxy 按 admin key)只碰自己的资源。关键场景:旧版脚本起的
  # proxy 泄漏持有 run.lock 的 fd,不杀掉它锁永远解不开(--stop 不能被它堵死)。
  (
    flock -w 5 9 || warn "run.lock 5 秒没拿到(新会话启动中/旧 proxy 泄漏的 fd),继续按身份精确清理"
    clean_own_containers
    stop_proxy
  ) 9>>"$LOG_DIR/run.lock" || true
  local cpid
  if [[ -f "$LOG_DIR/controller.pid" ]]; then
    cpid=$(cat "$LOG_DIR/controller.pid" 2>/dev/null || true)
    if [[ -n "$cpid" ]] && proc_alive "$cpid"; then
      log "controller 仍在跑(pid $cpid,无状态服务,不影响别人;要停: kill $cpid)"
    fi
  fi
  log "$USER_NAME 停止完成"
}

# ─────────────────────────────────────────────
#  预检:所选 agent 的 CLI 工具是否真的可用
# ─────────────────────────────────────────────
# 之前出现过 claude-code 的 bin/claude.exe 是 500 字节占位、启动即崩、
# 每个任务 0.28 秒空跑拿 0 分的情况。这里在评测前先跑一遍 --version 把它挡住。
check_agent_tool() {
  local launcher
  case "$AGENT" in
    claude_code) launcher="claude-code.sh" ;;
    codex)       launcher="codex.sh" ;;
    gemini_cli)  launcher="gemini-cli.sh" ;;
    *) die "未知 AGENT=$AGENT(应为 claude_code / codex / gemini_cli)" ;;
  esac
  local bin="$PROJECT_ROOT/data/runtime/node/bin/$launcher"
  if [[ ! -x "$bin" ]]; then
    die "agent 工具不可用: $bin 不存在或不可执行。
  先跑: bash scripts/setup/setup_data.sh
  (claude-code 若报 claude.exe 占位,见 docs/setup.md 的修复说明)"
  fi

  log "预检 $AGENT ($launcher --version)…"
  local out rc
  out=$(timeout 60 "$bin" --version 2>&1) && rc=0 || rc=$?
  if [[ $rc -ne 0 ]]; then
    warn "$AGENT 自检失败 (exit=$rc):"
    printf '%s\n' "$out" | head -15 | sed 's/^/    /'
    die "请先修复该 agent 工具再重试。全量检查: bash scripts/setup/validate.sh"
  fi
  log "$AGENT 可用 → $(printf '%s' "$out" | head -1 | cut -c1-80)"
}

# ─────────────────────────────────────────────
#  端到端预检 API:host 发 hi + 容器里发 hi
# ─────────────────────────────────────────────
# host 能通不代表容器能通:agent 在容器里访问 $BRIDGE:$PROXY_PORT,宿主机防火墙
# (firewalld)很可能挡掉 docker 子网到该端口的流量,结果每个任务 ConnectionRefused、
# 3 分钟拿 0 分。所以容器侧也真发一个 hi —— 这正是 agent 的完整路径 container→proxy→GLM。
# 从 anthropic /v1/messages 响应里抽出模型回复文本(给预检展示用)
show_reply() {
  printf '%s' "$1" | python3 -c '
import sys, json
raw = sys.stdin.read()
try:
    d = json.loads(raw)
except Exception:
    print(raw[:200]); raise SystemExit
if isinstance(d, dict):
    if d.get("error"):
        print("ERROR:", json.dumps(d["error"], ensure_ascii=False)[:300]); raise SystemExit
    parts = []
    for b in d.get("content", []) or []:
        t = b.get("type")
        if t == "text": parts.append(b.get("text", ""))
        elif t == "thinking": parts.append("[think]" + (b.get("thinking") or "")[:60])
        elif t == "tool_use": parts.append("[tool_use:" + b.get("name", "") + "]")
    if parts: print(" ".join(parts)[:300]); raise SystemExit
print(raw[:200])
' 2>/dev/null || true
}

check_api() {
  log "端到端预检 API(host + 容器 各发一个 hi)…"
  local key
  key=$(curl -s -X POST "http://$BRIDGE:$PROXY_PORT/budget/generate_key" \
        -H "x-admin-key: $CYBERGYM_ADMIN_KEY" -H 'Content-Type: application/json' \
        -d "{\"max_budget\":0.01,\"allowed_models\":[\"$MODEL_ALIAS\"]}" \
      | python3 -c "import sys,json;print(json.load(sys.stdin).get('key',''))" 2>/dev/null || true)
  [[ -n "$key" ]] || die "无法从 proxy 生成测试 key;看 $LOG_DIR/llm_proxy.log"

  local body url success_pattern
  if [[ "$AGENT" == "codex" ]]; then
    # codex 走 responses API
    body='{"model":"'"$MODEL_ALIAS"'","input":"hi","max_output_tokens":8}'
    url="http://$BRIDGE:$PROXY_PORT/v1/responses"
    success_pattern='"status"'
  else
    # claude_code 走 messages API(纯 Anthropic 协议参数,不带 reasoning_effort 等
    # OpenAI 风格字段——原生 anthropic 路由下多余字段可能被上游 400)
    body='{"model":"'"$MODEL_ALIAS"'","max_tokens":64,"messages":[{"role":"user","content":"hi"}]}'
    url="http://$BRIDGE:$PROXY_PORT/v1/messages"
    success_pattern='"role":"assistant"'
  fi

  # 失败/成功都先清理测试 key 再下结论
  local hresp
  hresp=$(curl -s -X POST "$url" \
        -H "x-api-key: $key" -H 'content-type: application/json' \
        -H 'anthropic-version: 2023-06-01' -d "$body" 2>&1 || true)

  local creply=""
  if command -v docker >/dev/null 2>&1; then
    creply=$(docker run --rm alpine:3.20 sh -c "wget -q -O - \
        --header='x-api-key: $key' \
        --header='content-type: application/json' \
        --header='anthropic-version: 2023-06-01' \
        --post-data='$body' \
        '$url' 2>&1" || true)
  fi

  curl -s -X DELETE "http://$BRIDGE:$PROXY_PORT/budget/key/$key" \
        -H "x-admin-key: $CYBERGYM_ADMIN_KEY" >/dev/null 2>&1 || true

  if ! printf '%s' "$hresp" | grep -q "$success_pattern"; then
    warn "host→proxy→GLM 推理失败(没拿到模型回复):"
    printf '%s\n' "$hresp" | head -8 | sed 's/^/    /'
    die "确认 GLM 端点 $GLM_BASE_URL 可达、glm_config.yaml 里 $MODEL_ALIAS 配置正确"
  fi
  log "host→proxy→GLM 推理 OK,模型回复: $(show_reply "$hresp")"

  if [[ -z "$creply" ]]; then
    warn "跳过容器侧 hi 测试(docker 不可用)"
    return 0
  fi
  if printf '%s' "$creply" | grep -q "$success_pattern"; then
    log "container→proxy→GLM 真实推理 OK,模型回复: $(show_reply "$creply")"
  else
    warn "容器内发 hi 失败(容器→proxy→GLM,正是 agent 的路径):"
    printf '%s\n' "$creply" | head -8 | sed 's/^/    /'
    die "容器连不到 proxy 或被宿主机防火墙挡。放行 docker 子网后重试:
    firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=172.17.0.0/16 accept'
    firewall-cmd --reload"
  fi
}

# ─────────────────────────────────────────────
#  自动放行防火墙:容器→宿主机 proxy/controller
# ─────────────────────────────────────────────
# 设计成"零打扰":先无提权从容器测一下连通性,通了就立刻返回(组员日常跑不会
# 被索要 sudo)。只有测出不通、且 firewalld 在跑时,才 sudo 加一条 docker 子网
# 放行规则(永久 + reload)。规则加一次就长期生效,之后所有人再跑都直接跳过。
ensure_firewall_open() {
  local cout
  cout=$(docker run --rm alpine:3.20 sh -c "wget -S -q -O /dev/null -T 5 'http://$BRIDGE:$PROXY_PORT/' 2>&1 | head -3" 2>&1 || true)
  if printf '%s' "$cout" | grep -qi 'HTTP/'; then
    return 0   # 已通,不碰防火墙
  fi

  command -v firewall-cmd >/dev/null 2>&1 || return 0
  [[ "$(systemctl is-active firewalld 2>/dev/null || true)" == "active" ]] || return 0

  # 从 docker0 地址推 CIDR(默认 172.17.0.0/16,但有的机器网段不同)
  local cidr
  cidr=$(ip -o -4 addr show docker0 2>/dev/null | awk '{print $4; exit}')
  cidr="${cidr:-172.17.0.0/16}"

  log "容器连不到宿主机服务且 firewalld 在跑 → 放行 docker 子网 $cidr(只第一次需要 sudo)"
  if [[ $EUID -eq 0 ]]; then
    firewall-cmd --permanent --add-rich-rule="rule family=ipv4 source address=$cidr accept" \
      && firewall-cmd --reload \
      || die "firewalld 规则添加失败,请 root 手动执行:
    firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=$cidr accept'
    firewall-cmd --reload"
  else
    sudo firewall-cmd --permanent --add-rich-rule="rule family=ipv4 source address=$cidr accept" \
      && sudo firewall-cmd --reload \
      || die "firewalld 规则添加失败(需要 sudo 权限)。请管理员执行:
    firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=$cidr accept'
    firewall-cmd --reload"
  fi
  log "防火墙规则已添加"
}

# ─────────────────────────────────────────────
#  同名互斥锁
# ─────────────────────────────────────────────
# 同一名字同一时间只允许一个 run_as.sh 会话(评测或交互)。锁 fd 保持打开直到
# 进程组退出(exec 后仍持有),第二个同名会话会在 flock -n 处失败。
# FORCE_RUN=1:先 stop_runner 停旧的再接管。
# fd 8 故意不用 9(controller 启动子壳在用 9)。
acquire_run_lock() {
  local desc="$*" holders="" pid
  # >> 而不是 >:打不开锁的后来者不能截断文件抹掉持有者信息(旧版这里会清成 "pid 未知")
  exec 8>>"$LOG_DIR/run.lock"
  if flock -n 8; then
    printf 'pid=%s\nstarted=%s\ncmd=%s\n' "$$" "$(date '+%F %T')" "$desc" > "$LOG_DIR/run.lock"
    return 0
  fi
  for pid in $(lock_holders "$LOG_DIR/run.lock"); do
    holders="${holders:+$holders }$pid:$(cat /proc/$pid/comm 2>/dev/null)"
  done
  if [[ "${FORCE_RUN:-0}" == "1" ]]; then
    log "FORCE_RUN=1:接管 $USER_NAME 槽位(停旧 runner,必要时停旧 proxy)"
    stop_runner
    if ! flock -w 10 8; then
      warn "锁仍被占用(多半是旧版泄漏了 fd 的 proxy),按 admin key 停自己的 proxy 后再等锁"
      stop_proxy
      flock -w 10 8 || die "锁还是被占用(持有者: ${holders:-未知});bash run_as.sh --stop $USER_NAME 后重试"
    fi
    printf 'pid=%s\nstarted=%s\ncmd=%s\n' "$$" "$(date '+%F %T')" "$desc" > "$LOG_DIR/run.lock"
    return 0
  fi
  die "$USER_NAME 已有一个会话在跑(锁持有者: ${holders:-未知},详情: logs/$USER_NAME/run.lock)。
  并行请用别的名字;接管旧会话: FORCE_RUN=1 bash run_as.sh $USER_NAME …;全停: bash run_as.sh --stop $USER_NAME"
}

# ─────────────────────────────────────────────
#  参数解析
# ─────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  USER_NAME="${2:?用法: bash run_as.sh --stop <名字>}"
  LOG_DIR="$PROJECT_ROOT/logs/$USER_NAME"
  stop_slot
  exit 0
fi

USER_NAME="${1:?用法: bash run_as.sh <名字> [run_agent 额外参数...] ; 例: bash run_as.sh wzk}"
shift

BRIDGE="$(bridge_ip)"
check_agent_tool          # 工具不可用就别白起 controller/proxy 了

SLOT="$(assign_or_get_slot "$USER_NAME")"
PROXY_PORT=$((PROXY_PORT_BASE + SLOT - 1))
# controller 也按槽位派独立端口(默认 8700+slot-1),每人自己的,不复用别人在 8666 上的
[[ -z "${CONTROLLER_PORT:-}" ]] && CONTROLLER_PORT=$((CONTROLLER_PORT_BASE + SLOT - 1))

OUT_DIR="$PROJECT_ROOT/out/$USER_NAME/run_agent"
LOG_DIR="$PROJECT_ROOT/logs/$USER_NAME"
mkdir -p "$OUT_DIR" "$LOG_DIR"

# 同名互斥(必须在 ensure_glm_config/ensure_proxy 之前:那两步可能触发 proxy 重启逻辑)
acquire_run_lock "agent=${AGENT} tasks=${TASKS_FILE} model=${GLM_MODEL} args=$*"

# 容器打上归属 label(base.py 读 CYBERGYM_OWNER),--stop 只清理自己的容器
export CYBERGYM_OWNER="$USER_NAME"

# 每人一份 controller secret(独立 controller 用独立 secret)
CONTROLLER_SECRETS_FILE="$LOG_DIR/controller.secrets.env"

# 每人一份配置(而非项目根共用),这样两个 screen 跑不同模型不会互相覆盖
GLM_CONFIG="$LOG_DIR/glm_config.yaml"
ensure_glm_config

log "用户=$USER_NAME  槽位=$SLOT  proxy=:$PROXY_PORT  controller=:$CONTROLLER_PORT"
log "输出=$OUT_DIR"

ensure_controller
ensure_firewall_open   # 容器→controller/proxy 不通且 firewalld 在跑才加规则

if [[ "${DIRECT:-0}" == "1" && "$AGENT" == "codex" ]]; then
  # 直连模式:codex 直接打到 360,不经 litellm proxy(避免 responses 流式被 proxy 搞坏)
  export CODEX_DIRECT_BASE_URL="${GLM_BASE_URL%/}"
  export OPENAI_API_KEY="$GLM_API_KEY"
  log "DIRECT 模式:codex 直连 $CODEX_DIRECT_BASE_URL(跳过 proxy)"

  # 简单预检:直连 360 responses API
  rcode=$(curl -sS -o /dev/null -w '%{http_code}' \
    "${GLM_BASE_URL%/}/responses" \
    -H "Authorization: Bearer $GLM_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$GLM_MODEL\",\"input\":\"hi\",\"max_output_tokens\":4}" \
    2>/dev/null || echo "000")
  if [[ "$rcode" != "200" ]]; then
    die "直连 360 responses API 失败(HTTP $rcode)。检查 GLM_BASE_URL/GLM_MODEL/GLM_API_KEY"
  fi
  log "直连 360 responses API OK"

  log "开始评测(任务文件 $TASKS_FILE,agent=$AGENT,model=$GLM_MODEL,workers=$MAX_WORKERS,direct)"
  echo $$ > "$LOG_DIR/runner.pid"   # exec 不换 pid;--stop 由此找到 runner
  exec uv run examples/run_agent.py \
    --agent "$AGENT" \
    --model "$GLM_MODEL" \
    --use-api-key \
    --controller-url "http://$BRIDGE:$CONTROLLER_PORT" \
    --tasks-file "$TASKS_FILE" \
    --budget "$BUDGET" \
    --timeout "$TIMEOUT" \
    --max-workers "$MAX_WORKERS" \
    --out-dir "$OUT_DIR" \
    "$@"
fi

ensure_proxy
check_api            # host 推理 + 容器连通都过才放行,免得白跑

# 导出给 uv run 子进程(cybergym 代码会读)。
# 三个 CYBERGYM_SERVER_* 已由 ensure_controller 导出,run_agent.py 会强制校验它们。
export CYBERGYM_ADMIN_KEY
export GLM_API_KEY

# ─────────────────────────────────────────────
#  交互模式:不跑评测,直接进容器手动用 cc/codex
#  用法: INTERACTIVE=1 bash run_as.sh <名字> [task_id]
# ─────────────────────────────────────────────
if [[ "${INTERACTIVE:-0}" == "1" ]]; then
  export BRIDGE PROXY_PORT CONTROLLER_PORT MODEL_ALIAS BUDGET
  export EFFORT="${CLAUDE_CODE_EFFORT_LEVEL:-high}"
  echo $$ > "$LOG_DIR/runner.pid"   # exec 不换 pid;--stop 由此找到交互会话
  exec uv run python3 scripts/interactive.py "${1:-}" \
    --controller-url "http://$BRIDGE:$CONTROLLER_PORT" \
    --proxy-url "http://$BRIDGE:$PROXY_PORT" \
    --model "$MODEL_ALIAS" --effort "$EFFORT" \
    --budget "$BUDGET" --tasks-file "${TASKS_FILE:-}"
fi

log "开始评测(任务文件 $TASKS_FILE,agent=$AGENT,model=$MODEL_ALIAS,workers=$MAX_WORKERS)"
echo $$ > "$LOG_DIR/runner.pid"   # exec 不换 pid;--stop 由此找到 runner
exec uv run examples/run_agent.py \
  --agent "$AGENT" \
  --model "$MODEL_ALIAS" \
  --proxy-url "http://$BRIDGE:$PROXY_PORT" \
  --proxy-admin-key "$CYBERGYM_ADMIN_KEY" \
  --controller-url "http://$BRIDGE:$CONTROLLER_PORT" \
  --tasks-file "$TASKS_FILE" \
  --budget "$BUDGET" \
  --timeout "$TIMEOUT" \
  --max-workers "$MAX_WORKERS" \
  --out-dir "$OUT_DIR" \
  "$@"
