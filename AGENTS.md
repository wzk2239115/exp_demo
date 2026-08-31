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
  ./node ./npm install -g --prefix "$R" --include=optional @anthropic-ai/claude-code@2.1.119
# glibc 原生包 + 直连二进制(注意: 二进制在包根目录,没有 bin/ 子目录)
PATH="$R/bin:$PATH" NPM_CONFIG_PREFIX="$R" npm_config_prefix="$R" \
  ./node ./npm install -g --prefix "$R" --include=optional @anthropic-ai/claude-code-linux-x64@2.1.119
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
