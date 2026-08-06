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
#   bash run_as.sh --stop wzk                           # 停掉 wzk 的 proxy
#
# 可用环境变量覆盖默认值:
#   GLM_BASE_URL (默认 http://11.131.215.38:8000/v1)
#   GLM_MODEL    (默认 GLM52_Full,vLLM /v1/models 里的 id)
#   MODEL_ALIAS  (默认 glm-52-full,run_agent 的 --model)
#   GLM_API_KEY  (默认 dummy,vLLM 没设 key 就不用改)
#   TASKS_FILE   (默认 data/task_ids/sample.txt)
#   AGENT        (默认 claude_code)
#   BUDGET       (默认 1000)
#   TIMEOUT      (默认 3600 秒)
#   MAX_WORKERS  (默认 1)
#   PROXY_PORT_BASE (默认 4001;第 N 个组员用 4000+N)
#   CONTROLLER_PORT (默认 8666)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────
#  可配置项
# ─────────────────────────────────────────────
GLM_BASE_URL="${GLM_BASE_URL:-http://11.131.215.38:8000/v1}"
GLM_MODEL="${GLM_MODEL:-GLM52_Full}"
MODEL_ALIAS="${MODEL_ALIAS:-glm-52-full}"
GLM_API_KEY="${GLM_API_KEY:-dummy}"

AGENT="${AGENT:-claude_code}"
TASKS_FILE="${TASKS_FILE:-data/task_ids/sample.txt}"
BUDGET="${BUDGET:-1000}"
TIMEOUT="${TIMEOUT:-3600}"
MAX_WORKERS="${MAX_WORKERS:-1}"

CONTROLLER_PORT="${CONTROLLER_PORT:-8666}"
PROXY_PORT_BASE="${PROXY_PORT_BASE:-4001}"

GLM_CONFIG="$PROJECT_ROOT/glm_config.yaml"
SLOTS_FILE="$PROJECT_ROOT/logs/user_slots.tsv"
# controller 的三个共享 secret(token salt / flag seed / api key)持久化到这里。
# controller 全组共用一个,所以这三个值也得全组一致;run_agent.py 必须读到它们才能
# 验证 token / flag。文件权限 600(能读到就能伪造 token)。
CONTROLLER_SECRETS_FILE="$PROJECT_ROOT/logs/controller.secrets.env"

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
  if [[ -f "$GLM_CONFIG" ]]; then return 0; fi
  log "生成 $GLM_CONFIG"
  cat > "$GLM_CONFIG" <<EOF
model_list:
  - model_name: $MODEL_ALIAS
    litellm_params:
      model: openai/$GLM_MODEL
      api_base: "$GLM_BASE_URL"
      api_key: "os.environ/GLM_API_KEY"
      input_cost_per_token: 0.0
      output_cost_per_token: 0.0
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: openai/$GLM_MODEL
      api_base: "$GLM_BASE_URL"
      api_key: "os.environ/GLM_API_KEY"
      input_cost_per_token: 0.0
      output_cost_per_token: 0.0
litellm_settings:
  use_chat_completions_url_for_anthropic_messages: true
EOF
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

  # 2) controller 已在跑(被 pre_run 或别人起的)→ 从日志恢复
  if listening "$ctl_url"; then
    local logfiles=(
      "$PROJECT_ROOT/logs/controller.log"
      "$PROJECT_ROOT/logs/controller/server_manager.log"
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
#  共享 controller(全组一个,自动拉起/复用)
# ─────────────────────────────────────────────
ensure_controller() {
  local url="http://$BRIDGE:$CONTROLLER_PORT/"
  ensure_controller_secrets   # 先保证三个 CYBERGYM_SERVER_* 已 export

  if listening "$url"; then
    log "controller 复用中 :$CONTROLLER_PORT"
    return 0
  fi
  log "controller 未运行,启动共享实例……"
  mkdir -p "$PROJECT_ROOT/logs/controller"
  (
    flock 9
    if ! listening "$url"; then
      # 继承已 export 的 CYBERGYM_SERVER_* 给 controller 子进程
      nohup uv run -m cybergym.server \
        --host "$BRIDGE" --port "$CONTROLLER_PORT" \
        --log_dir "$PROJECT_ROOT/logs/controller" \
        > "$PROJECT_ROOT/logs/controller.log" 2>&1 &
      echo $! > "$PROJECT_ROOT/logs/controller.pid"
    fi
    for _ in $(seq 1 40); do
      listening "$url" && exit 0
      sleep 0.5
    done
    exit 1
  ) 9>"$PROJECT_ROOT/logs/controller.start.lock"
  listening "$url" || die "controller 启动失败,看 logs/controller.log"
  log "controller 已启动 :$CONTROLLER_PORT (pid $(cat "$PROJECT_ROOT/logs/controller.pid"))"
}

# ─────────────────────────────────────────────
#  每人的 LLM proxy(端口/预算/key 独占)
# ─────────────────────────────────────────────
ensure_proxy() {
  local health="http://$BRIDGE:$PROXY_PORT/health/liveliness"
  local root="http://$BRIDGE:$PROXY_PORT/"
  local admin_key_file="$LOG_DIR/admin.key"

  if listening "$health" || listening "$root"; then
    if [[ -f "$admin_key_file" ]]; then
      CYBERGYM_ADMIN_KEY=$(cat "$admin_key_file")
    else
      CYBERGYM_ADMIN_KEY=$(grep -oP 'Admin key for /budget endpoints:\s*\K\S+' "$LOG_DIR/llm_proxy.log" 2>/dev/null | tail -1 || true)
    fi
    [[ -n "$CYBERGYM_ADMIN_KEY" ]] || die "proxy :$PROXY_PORT 已在跑但找不到 admin key,删 logs/$USER_NAME/llm_proxy.log 后重试,或换 PROXY_PORT_BASE"
    log "proxy 复用中 :$PROXY_PORT (admin ${CYBERGYM_ADMIN_KEY:0:20}…)"
    return 0
  fi

  CYBERGYM_ADMIN_KEY="cgym-admin-$USER_NAME-$(openssl rand -hex 8)"
  printf '%s' "$CYBERGYM_ADMIN_KEY" > "$admin_key_file"
  chmod 600 "$admin_key_file"
  export GLM_API_KEY

  log "启动 $USER_NAME 的 LLM proxy :$PROXY_PORT"
  nohup uv run -m cybergym.llm_proxy \
    --host "$BRIDGE" --port "$PROXY_PORT" \
    --admin-key "$CYBERGYM_ADMIN_KEY" \
    --config "$GLM_CONFIG" \
    --default-budget "$BUDGET" \
    > "$LOG_DIR/llm_proxy.log" 2>&1 &
  echo $! > "$LOG_DIR/proxy.pid"

  for _ in $(seq 1 40); do
    listening "$root" && break
    sleep 0.5
  done
  listening "$root" || die "proxy 启动失败,看 $LOG_DIR/llm_proxy.log"
  log "proxy 已启动 :$PROXY_PORT"
}

stop_proxy() {
  local pidfile="$PROJECT_ROOT/logs/$USER_NAME/proxy.pid"
  if [[ -f "$pidfile" ]] && kill "$(cat "$pidfile")" 2>/dev/null; then
    log "已停止 $USER_NAME 的 proxy (pid $(cat "$pidfile"))"
    rm -f "$pidfile"
  else
    warn "$USER_NAME 没有在跑的 proxy(或 pid 文件缺失)"
  fi
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
#  端到端预检 API:host 真实推理 + 容器视角连通
# ─────────────────────────────────────────────
# host 能通不代表容器能通:agent 在容器里访问 $BRIDGE:$PROXY_PORT,宿主机防火墙
# (firewalld)很可能挡掉 docker 子网到该端口的流量,结果每个任务 ConnectionRefused、
# 3 分钟拿 0 分。这里两段都测,任一失败就 die。
check_api() {
  log "端到端预检 API(host 推理 + 容器连通)…"
  local key resp
  key=$(curl -s -X POST "http://$BRIDGE:$PROXY_PORT/budget/generate_key" \
        -H "x-admin-key: $CYBERGYM_ADMIN_KEY" -H 'Content-Type: application/json' \
        -d "{\"max_budget\":0.01,\"allowed_models\":[\"$MODEL_ALIAS\"]}" \
      | python3 -c "import sys,json;print(json.load(sys.stdin).get('key',''))" 2>/dev/null || true)
  [[ -n "$key" ]] || die "无法从 proxy 生成测试 key;看 $LOG_DIR/llm_proxy.log"

  resp=$(curl -s -X POST "http://$BRIDGE:$PROXY_PORT/v1/messages" \
        -H "x-api-key: $key" -H 'content-type: application/json' \
        -H 'anthropic-version: 2023-06-01' \
        -d "{\"model\":\"$MODEL_ALIAS\",\"max_tokens\":8,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" 2>&1 || true)
  curl -s -X DELETE "http://$BRIDGE:$PROXY_PORT/budget/key/$key" \
        -H "x-admin-key: $CYBERGYM_ADMIN_KEY" >/dev/null 2>&1 || true

  if ! printf '%s' "$resp" | grep -q '"role":"assistant"'; then
    warn "proxy→GLM 推理预检失败(没拿到模型回复):"
    printf '%s\n' "$resp" | head -8 | sed 's/^/    /'
    die "确认 GLM 端点 $GLM_BASE_URL 可达、glm_config.yaml 里 $MODEL_ALIAS→openai/$GLM_MODEL 正确"
  fi
  log "host→proxy→GLM 推理 OK"

  if command -v docker >/dev/null 2>&1; then
    local cout
    # 任意 HTTP 状态行(含 404)都说明端口可达;只有 refused/timeout 才算不通
    cout=$(docker run --rm alpine:3.20 sh -c "wget -S -q -O /dev/null -T 5 'http://$BRIDGE:$PROXY_PORT/' 2>&1 | head -3" 2>&1 || true)
    if printf '%s' "$cout" | grep -qi 'HTTP/'; then
      log "container→proxy 连通 OK"
    else
      warn "容器内连不到 proxy $BRIDGE:$PROXY_PORT:"
      printf '%s\n' "$cout" | head -4 | sed 's/^/    /'
      die "很可能是宿主机防火墙挡了容器→proxy。放行 docker 子网后重试:
    firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=172.17.0.0/16 accept'
    firewall-cmd --reload"
    fi
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
#  参数解析
# ─────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  USER_NAME="${2:?用法: bash run_as.sh --stop <名字>}"
  stop_proxy
  exit 0
fi

USER_NAME="${1:?用法: bash run_as.sh <名字> [run_agent 额外参数...] ; 例: bash run_as.sh wzk}"
shift

BRIDGE="$(bridge_ip)"
check_agent_tool          # 工具不可用就别白起 controller/proxy 了
ensure_glm_config

SLOT="$(assign_or_get_slot "$USER_NAME")"
PROXY_PORT=$((PROXY_PORT_BASE + SLOT - 1))

OUT_DIR="$PROJECT_ROOT/out/$USER_NAME/run_agent"
LOG_DIR="$PROJECT_ROOT/logs/$USER_NAME"
mkdir -p "$OUT_DIR" "$LOG_DIR"

log "用户=$USER_NAME  槽位=$SLOT  proxy=:$PROXY_PORT  controller=:$CONTROLLER_PORT"
log "输出=$OUT_DIR"

ensure_controller
ensure_proxy
ensure_firewall_open   # 容器→proxy 不通且 firewalld 在跑才加规则(日常不打扰)
check_api            # host 推理 + 容器连通都过才放行,免得白跑

# 导出给 uv run 子进程(cybergym 代码会读)。
# 三个 CYBERGYM_SERVER_* 已由 ensure_controller 导出,run_agent.py 会强制校验它们。
export CYBERGYM_ADMIN_KEY
export GLM_API_KEY

log "开始评测(任务文件 $TASKS_FILE,agent=$AGENT,model=$MODEL_ALIAS,workers=$MAX_WORKERS)"
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
