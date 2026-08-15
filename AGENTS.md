# AGENTS.md — ExploitGym 评测运维备忘

## 基础设施

- 评测服务器: `/data/wangzekai/exploitgym`(容器、controller、proxy 都在这台)
- 本地代码副本: `/home/wzk/projects/exploitgym`(fork: `git@github.com:wzk2239115/exploitgym.git`)
- **不要使用其他人的服务**(尤其 wuheyi 的 controller :8666 / proxy :4000)。
  每个评测槽位(`bash run_as.sh <name>`)用自己的 controller/proxy 端口,由 run_as.sh 自动分配拉起。
- 360 API key 在服务器 `.glm_env`;deepseek-flash 槽位用的是另一个 key(`fk3478068563....`)。
- 跑批期间不要再跑同名 `run_as.sh`(`ensure_proxy` 可能 pkill 掉在用的 proxy,cc 会话报 ConnectionRefused)。

## 模型路由(重要,少踩坑)

### 首选: 360 原生 Anthropic 端点 `api.360.cn/v1/messages`

360 有原生 Anthropic 协议端点(和 DeepSeek 官方 `api.deepseek.com/anthropic` 同理),
**服务端自己做协议转换,不经过 litellm 有 bug 的翻译层**。已验证(2026-08-15):

| 模型 | 非流式 | 流式 | 备注 |
|------|--------|------|------|
| deepseek/deepseek-v4-flash | ✓ | ✓ | thinking+text 块规范 |
| deepseek/deepseek-v4-pro | ✓ | - | |
| openai/gpt-5.5 | ✓ | - | |
| z-ai/glm-5.3 | ✓ | - | **必须带 `thinking` 参数**,否则 400 "该模型始终思考" |

用法: 跑评测时加 `GLM_PROVIDER=anthropic`。run_as.sh 生成 litellm 原生透传配置
(`model: anthropic/<GLM_MODEL>`,`api_base: https://api.360.cn`),不走 chat/completions 翻译。

### litellm 翻译层的坑(用 GLM_PROVIDER=anthropic 就能全绕开)

- "Content block not found": litellm `/v1/messages`→chat/completions 翻译路径,
  `delta.reasoning_content`(OpenAI 风格推理流,deepseek/gpt-5.5 都用)不被识别,
  被当 text 块发 delta → cc 报错。已打补丁 `_patch_streaming_reasoning_detection()`(commit cff1528),
  但翻译层还有块切换丢首字符等 bug(commit cd8bbc4 之后仍有),**优先用原生 anthropic 路由**。
- 块切换时触发块的 delta 被丢弃(streaming_iterator.py:325-362),只对 tool_use 例外 → 丢首字符。
- `thinking` 剥离中间件(server.py)现在只在 chat-completions 模式(`litellm.use_chat_completions_url_for_anthropic_messages=True`)
  下生效;原生 anthropic 路由时参数透传(commit cd8bbc4)。
- 360 `openai/` 模型前缀规则(仅翻译路径需要): chat completions 需三重 `openai/` 前缀,responses 双重。

## 跑批/续跑

- `run_agent.py` 自带断点续跑: out 目录里已有 `result.json` 的任务自动跳过(examples/run_agent.py:684)。
  续跑只要用**同一个 USER_NAME**(输出目录 `out/<name>/run_agent/`)+ 完整任务列表。
- 全量任务列表: `data/task_ids/v1.txt`(869 题)。
- deepseek 槽位 = deepseek-v4-pro + claude_code, 2026-08-07 起跑,结果在 `out/deepseek/run_agent/`。
- 超时按任务 7200s(2h)设置: `TIMEOUT=7200`。
- 别给正在续跑的 out 目录改名加日期后缀,会导致续跑找不到旧结果。

### 标准续跑命令

```bash
cd /data/wangzekai/exploitgym && git pull
# v4-pro 续跑(默认模型就是它)
GLM_PROVIDER=anthropic TASKS_FILE=data/task_ids/v1.txt MAX_WORKERS=6 TIMEOUT=7200 \
  bash run_as.sh deepseek
# v4-flash 新批
GLM_PROVIDER=anthropic GLM_API_KEY="fk3478068563.YwBSsMEzH_TyYVMYm5qPnQMrNIcll40wc182fade" \
GLM_MODEL=deepseek/deepseek-v4-flash MODEL_ALIAS=deepseek-v4-flash \
TASKS_FILE=data/task_ids/v1.txt MAX_WORKERS=6 TIMEOUT=7200 \
bash run_as.sh deepseek-flash
```

### 清理被 API bug 打死的失败任务(删 result.json 后续跑自动补)

```bash
cd out/<name>/run_agent
find . -name claude_code.rendered.log -exec grep -l "Content block not found" {} \; \
  | sed 's|/logs/claude_code.rendered.log||' | while read t; do rm -f "$t/result.json"; done
```

## 交互模式(手动打靶)

- `INTERACTIVE=1 bash run_as.sh <name>`,由 `scripts/interactive.py` 处理,容器默认进 `/workspace`。
- 容器内 cc 不在 PATH: `source /workspace/env.sh && /data/node/bin/claude-code.sh --verbose --permission-mode=bypassPermissions --disallowed-tools WebSearch,WebFetch`
  (proxy 默认禁 WebSearch/WebFetch,不禁用会 403 "web_search_blocked")。
- cc 会话记录在容器 `/logs`,proxy 挂了不丢;proxy 恢复后 `claude-code.sh -c` 续上。
- proxy 死了(日志见 `INFO: Shutting down` = 收到 SIGTERM): 重启见 run_as.sh ensure_proxy 逻辑,
  或手工 setsid 拉起同端口同 admin-key 的 proxy。

## 已知问题/待办

- litellm 翻译层 streaming 块切换丢首字符 bug 未修(绕开方案: 原生 anthropic 路由)。
- interactive.py 的 create_server `task_info` 应传 `entry_name`(如 `cybergym/arvo_1461`)而非
  `task_id`,否则 controller 400 "Unknown task_id"(影响交互模式的远程靶机,不影响本地分析)。
- gpt-5.5 / glm-5.2 等槽位评测重跑待原生 anthropic 路由验证。
