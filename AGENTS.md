# AGENTS.md — ExploitGym 评测运维备忘

## 基础设施

- 评测服务器: `/data/wangzekai/exploitgym`(容器、controller、proxy 都在这台)
- 本地代码副本: `/home/wzk/projects/exploitgym`(fork: `git@github.com:wzk2239115/exploitgym.git`)
- **不要使用其他人的服务**(尤其 wuheyi 的 controller :8666 / proxy :4000)。
  每个评测槽位(`bash run_as.sh <name>`)用自己的 controller/proxy 端口,由 run_as.sh 自动分配拉起。
- 360 API key 在服务器 `.glm_env`;deepseek-flash 槽位用的是另一个 key(`fk3478068563....`)。
- 同名互斥:同一名字同时只允许一个 `run_as.sh` 会话(`logs/<名字>/run.lock`),第二个自动拒绝。
  接管在跑的会话: `FORCE_RUN=1 bash run_as.sh <名字>`;并行请用不同名字。
- 停止评测: `bash run_as.sh --stop <名字>`,分层关停:runner(SIGINT graceful→SIGTERM→SIGKILL,
  超时秒数 `STOP_GRACE`,默认 90)→ 自己 label 的残留容器(`exploitgym.owner=<名字>`,
  run_as.sh 导出 `CYBERGYM_OWNER`)→ proxy(按 admin key 精确匹配)。controller 保留。
- **proxy 永不被脚本自动杀**(旧版 glm_config 变化/git pull 后 sha 变化会 pkill 在跑 proxy,
  在跑任务全部 exit 137,8/10 的 arvo_30099 就是这么死的)。现在 config 变化只警告;
  要应用新配置: 先 `--stop` 再重跑,或 `FORCE_PROXY_RESTART=1 bash run_as.sh …`(按 admin key 精确重启)。

## 模型路由(重要,少踩坑)

### 首选: 360 原生 Anthropic 端点 `api.360.cn/v1/messages`

360 有原生 Anthropic 协议端点(和 DeepSeek 官方 `api.deepseek.com/anthropic` 同理),
**服务端自己做协议转换,不经过 litellm 有 bug 的翻译层**。已验证(2026-08-15):

| 模型 | 非流式 | 流式 | 备注 |
|------|--------|------|------|
| deepseek/deepseek-v4-flash | ✓ | ✓ | thinking+text 块规范 |
| deepseek/deepseek-v4-pro | ✓ | - | |
| openai/gpt-5.5 | ✓ | - | |
| z-ai/glm-5.3 | ✓ | ✓ | **必须带 `thinking` 参数**,否则 400 "该模型始终思考";tool_use 已验证 ✓ |

用法: 跑评测时加 `GLM_PROVIDER=anthropic`。run_as.sh 生成 litellm 原生透传配置
(`model: anthropic/<GLM_MODEL>`,`api_base: https://api.360.cn`),不走 chat/completions 翻译。
proxy 中间件在 anthropic 路由下会**规范化 `thinking` 参数**(commit 13a52dc):
**cc 2.1.x 每个请求都发 `thinking={"type":"adaptive"}`,360 只认 enabled|disabled,
其他一律 400 [1210]**;中间件只放行 `{"type":"enabled"}`(保留 cc 的 budget_tokens),
缺失/adaptive/disabled/未知都改写为 enabled+budget(≤8192,必要时抬 max_tokens)。
360 端已验证: enabled+budget_tokens 对 stream/tool_use/?beta=true 全部正常;
错误提示"请使用 low、high 或 max"是误导文案,字符串格式反而 400(1001)。

同类官方端点参考(直连 env 即可,无需 litellm):
- DeepSeek: `https://api.deepseek.com/anthropic`(官方文档 quick_start/agent_integrations/claude_code)
- 智谱 Z.AI: `https://api.z.ai/api/anthropic`(env 同款写法)
- 360: `https://api.360.cn/v1/messages`(即上文,已验证)

手动/交互场景可绕开 proxy 直连:
```bash
export ANTHROPIC_BASE_URL=https://api.360.cn/v1/messages
export ANTHROPIC_AUTH_TOKEN=<360 key>
# 常思模型还需 cc 侧开 thinking 或等 proxy 注入;直连时 cc 不发 thinking → glm-5.3 会 400
```
评测跑批仍走 proxy(要预算控制/按槽位发 key/禁 WebSearch)。

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

## cc 上下文窗口 / 自动压缩 / 提前退出(2026-09-07 修复)

背景: cc 2.1.x 对**未知模型名**(deepseek-v4-pro 等 proxy 别名)按 200K 窗口记账,
自动压缩在 ~160K 触发(deepseek 批次实测 arvo_22244 在 162,454 tokens 压缩,
70 分钟丢光利用状态后原地打转到超时)。cc 2.1.119 二进制逆向确认的机制:

- 模型最大窗口: 模型名带 `[1m]` 后缀 → cc 记 1M(`D2()`);未知模型 fallback 200K。
  `[1m]` 在发请求前被剥离,proxy/allowed_models 侧模型名不变;会附加
  `context-1m-2025-08-07` beta header(cc 本来每请求就带多个 beta,360 已容忍)。
- 压缩阈值: env `CLAUDE_CODE_AUTO_COMPACT_WINDOW`(cc 侧 clamp [100K, 1M]),
  实际生效值 = min(模型窗口, 配置值) → **必须同时开 `[1m]` 才能到 768K**。

`claude_code.py` 现在默认注入(`[1m]` 后缀 + 768K 阈值),并带**提前退出续跑循环**:
cc 退出(幻觉 end_turn / API 崩溃)但 `/workspace/flag.txt` 仍为空时,用 `--continue`
+ 续跑提示词重新拉起(恢复同一会话),直到 flag 出现 / 超时 / 轮数上限。
管道加了 `set -o pipefail`,exit code 不再被 tee 吃掉(原来恒 0,crash 与 timeout 124 全被掩盖)。

host 侧环境变量(可写 `.glm_env`,见 run_as.sh `_ENV_KEYS`):

- `CLAUDE_CODE_1M_CONTEXT`(默认 1): cc 侧模型名加 `[1m]` 后缀。
  **真实窗口 <1M 的模型(如 gpt-5.5)必须设 0**,否则超长请求上游 400。
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW`(默认 768000)。
- `CLAUDE_CODE_CONTINUE_ON_EXIT`(默认 1): 提前退出续跑;0 = 旧行为单发。
- `CLAUDE_CODE_MAX_ROUNDS`(默认 8): 每任务最多拉起次数(超时仍兜底)。
- `REQUIRE_NO_ASLR`(默认 0): 1 = 宿主机 `randomize_va_space != 0` 时 run_as.sh
  拒绝启动。默认只警告(重启后 ASLR 恢复 2 曾导致整批跑在 ASLR 开启下;
  base.py 也会把警告写进每个任务的 task.log,system_config.json 可事后核查)。
- `REASONING_EFFORT` / `THINKING_BUDGET`(deepseek 专用,2026-09-09 实测):
  360 anthropic 路径对 deepseek-v4 支持 `reasoning_effort` 三档
  **low / high(默认) / max**(medium/xhigh 映射为 high),以及 >8192 的
  `budget_tokens` 上限(glm 仍限 8192,故这两个旋钮只对模型名含 deepseek 的
  槽位生效)。proxy 中间件会注入;env 在 **proxy 进程**里读,改档后需
  `FORCE_PROXY_RESTART=1` 重启 proxy 才生效。例: `REASONING_EFFORT=max
  THINKING_BUDGET=32768`。

升级 cc 到 2.1.252(支持 /goal): 见下文安装一节,把版本号换成 2.1.252 重装即可;
`static_build_node_and_agents.sh` 默认值已同步改。

## round-2:失败题蒸馏续跑(2026-09-08)

对某个旧跑批 out 目录里的失败题自动做"蒸馏 + 导师注入 + resume 再跑 2h":

```bash
GLM_PROVIDER=anthropic GLM_API_KEY=<360 key> \
TASKS_FILE=data/task_ids/user_pending.txt MAX_WORKERS=6 TIMEOUT=7200 \
bash run_as.sh pro-r1-r2 --round2-from out/pro-r1/run_agent
```

- `--round2-from` 指旧 out 根目录:自动扫出「result.json 缺失或 0 分且有 cc 会话」
  的任务,成功的跳过,任务文件参数被忽略。
- 每题先把会话 jsonl 拷到新任务目录 `round2_distill/` 再调
  `scripts/distill_trajectory.py --inject`(死胡同操作丢弃 + 导师消息注入为最后
  一条 user 消息,研判模型 `--round2-judge-model`,默认 z-ai/glm-5.3 —— 360 的
  真实模型 id,distill 直连 /v1/messages 不经 proxy,吃 GLM_API_KEY),
  产物落在新目录,旧 out 目录不动。
- 蒸馏产物 docker cp 进新容器 `/logs/projects/-workspace/`,cc 首轮
  `--resume <新sid>`(续跑提示词开局),后续轮 `--continue`,2h 超时兜底。
- 蒸馏失败自动降级为 resume 原始会话(1M 窗口下通常也能装下);
  `--round2-no-distill` 可直接跳过蒸馏。
- 老批次(deepseek/glm52 时代)多数 user 任务没收集 session jsonl,会被跳过并告警;
  新代码跑的批次(带 projects/ 日志)才有完整会话。

### 标准续跑命令

```bash
cd /data/wangzekai/exploitgym && git pull
# v4-pro 续跑(默认模型就是它)
GLM_PROVIDER=anthropic TASKS_FILE=data/task_ids/v1.txt MAX_WORKERS=6 TIMEOUT=7200 \
  bash run_as.sh deepseek
# v4-flash 新批(2026-08-31 起 key 已换新)
GLM_PROVIDER=anthropic GLM_API_KEY="fk3478068563.wS9T_IONT6Qkh3IC2Ket6zbvbZi7jH37058071ba" \
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
- proxy 死了(日志见 `INFO: Shutting down` = 收到 SIGTERM): 标准做法是
  `bash run_as.sh --stop <name>` 清场后重跑(会重新生成 proxy);别直接 pkill 按端口杀,
  会误伤撞端口的别人 proxy。
- 交互会话与跑批同名互斥;要边跑批边打靶,交互用独立名字(独立槽位/端口)。

## 纯手工模式(无 LLM,自己打靶/演示用)

- `uv run scripts/manual.py cybergym/arvo_16541`(可加 `--image-mode exp.pie` / `--target READ`)。
- 一条命令: 起 controller(端口 8706,secret 持久化在 `logs/manual/controller.secrets.env`,
  重跑 flag 不变)→ 铸 token → create_server → 起 **privileged** 工作容器(评测同款 workspace
  + `/data` 工具)→ 关 ASLR(**全局 sysctl,影响整机**,做演示时记得这会影响别的在跑任务)
  → 自动修好 pwntools(`/data/python/bin` 的 shebang 烧死了宿主机绝对路径且只读挂载,
  脚本里已用 /usr/local/bin wrapper + PATH 修好,进 shell 直接 `checksec`/`ROPgadget`/`pwn`)
  → 进 shell。
- `/workspace/MANUAL.md` 里有 server 地址、token、预期 flag、发包 one-liner。
- 收尾: `uv run scripts/manual.py cybergym/arvo_16541 --stop`(只删工作容器;靶机 server
  有 1h TTL 自动过期)。ASLR 恢复在容器里 `echo 2 > /proc/sys/kernel/randomize_va_space`。
- 只支持 user 任务;kernel/v8 请用交互模式。

## claude-code 安装(data/runtime/node 重建必看,2026-08-31 实战记录)

- cc 2.1.x 已是**原生二进制发行**:npm 包里只剩占位符 + `install.cjs` 下载器,
  不再有可用的 JS/cli.js 兜底。`bin/claude.exe` 是 500 字节文本 = postinstall 没跑
  或原生 optional 依赖没下载,直接按下面流程装 glibc 变体。
- 死锁成因: 自建静态 node 是 musl → `install.cjs` 只找 `…-linux-x64-musl`;musl 件
  动态链接(`interpreter /lib/ld-musl-x86_64.so.1`),glibc 宿主机/agent 容器都没有
  musl 加载器 → exec 报误导性 "No such file or directory"。npm 按 glibc 宿主又不肯
  装 musl 变体(EBADPLATFORM)。
- 正确装法(glibc 变体 `…-linux-x64` 直连,宿主/容器通吃):

```bash
R=/data/wangzekai/exploitgym/data/runtime/node; cd $R/bin
# 主包(postinstall 需要 PATH,脚本已修 commit 1e31b47)
PATH="$R/bin:$PATH" NPM_CONFIG_PREFIX="$R" npm_config_prefix="$R" \
  ./node ./npm install -g --prefix "$R" --include=optional @anthropic-ai/claude-code@2.1.252
# glibc 原生包 + 直连二进制(注意: 二进制在包根目录,没有 bin/ 子目录)
PATH="$R/bin:$PATH" NPM_CONFIG_PREFIX="$R" npm_config_prefix="$R" \
  ./node ./npm install -g --prefix "$R" --include=optional @anthropic-ai/claude-code-linux-x64@2.1.252
ln -sf ../lib/node_modules/@anthropic-ai/claude-code-linux-x64/claude $R/bin/claude
$R/bin/claude-code.sh --version && cd /data/wangzekai/exploitgym && bash scripts/setup/validate.sh
```

- 变体名单: `npm view @anthropic-ai/claude-code@<ver> optionalDependencies`
  (无后缀 = glibc,`-musl` = musl)。`claude-code.sh` launcher 的 ELF 分支直跑,
  运行期不依赖 node。若手动 npm 装过要记得补写 launcher(write_launcher 只在
  `static_build_node_and_agents.sh` 里做)。
- 2026-08-31 事故: `data/runtime/` 被不明原因清空(node 被重建、python 丢失),
  若复发先查谁动的。python 重建: `bash scripts/setup/provision_portable_python.sh`。
- `validate.sh` 必须从 repo 根跑(相对路径),在深层目录跑会全部假 MISSING。

## kernel VM 内 gcc "cannot find 'ld'"(已定案 2026-08-31)

- 根因: **nsjail 空环境启动 shell**(配置无 `envar: PATH`),bash 合成的默认 PATH
  **未导出** → collect2 无 PATH 可搜 → 找不到 ld。工具链/binutils 本身完好。
- workaround(已写进 kernel.md.j2, commit 7917157): 会话先 `export PATH` 或
  `gcc -B/usr/bin`;`PATH=/usr/bin:$PATH`/`COMPILER_PATH=/usr/bin` 也都有效。
- 完整证据链/复现命令/受影响靶场清单: `evol_loop/0/TODO.md`。
  治本 = rootfs 的 nsjail 配置加 `envar: PATH=…`(rootfs 只读,需重烘镜像)。
- 复现入口: 任意 `cybergym/syzbot-target:<id>` 容器内直接 qemu 启动
  (qcow2 免转换,`init=/home/user/run.sh`),见 TODO.md。

## 已知问题/待办

- litellm 翻译层 streaming 块切换丢首字符 bug 未修(绕开方案: 原生 anthropic 路由)。
- interactive.py 的 create_server `task_info` 应传 `entry_name`(如 `cybergym/arvo_1461`)而非
  `task_id`,否则 controller 400 "Unknown task_id"(影响交互模式的远程靶机,不影响本地分析)。
- gpt-5.5 / glm-5.2 等槽位评测重跑待原生 anthropic 路由验证。
