# agent_tools — 给 agent 用的工具箱 + 指引

部署进容器(交互验证用):
```bash
# 起交互容器后,在宿主机跑(把工具+指引拷进容器 /workspace):
CNAME=interactive-xxx  # 你的容器名
docker cp scripts/agent_tools "$CNAME:/workspace/tools"
docker cp docs/agent_claude.md "$CNAME:/workspace/CLAUDE.md"
docker cp docs/exploit_roadmap.md "$CNAME:/workspace/exploit_roadmap.md"
docker exec -u0 "$CNAME" chmod +x /workspace/tools/*.sh /workspace/tools/*.py
# LD_PRELOAD 库在容器内构建:
docker exec -u0 -w /workspace/tools/ldpreload_toolbox "$CNAME" bash build.sh
```

agent 在 /workspace 跑 cc 时自动加载 CLAUDE.md(指引),卡住时读 exploit_roadmap.md(技法地图)。

## 工具清单

| 文件 | 干什么 | 对应卡点 |
|---|---|---|
| env_check.sh | 开局环境预检,输出 facts.json | 环境/工具、时间(省前20步) |
| remote_io.py | 远程交互封装+输出通道验证 | 远程交互未打通 |
| core_analyzer.py | ptrace 禁时读 core dump | 环境/工具限制 |
| check_fact.py | 已验证结论缓存,防重复验证 | 静态审计死循环 |
| ldpreload_toolbox/ | malloc/free 追踪(绕 ptrace) | 环境限制(166×最高频) |
| vm_lifecycle.sh | VM 起/等/传/清 | 内核题环境混乱 |

## 指引/地图

| 文件 | 干什么 |
|---|---|
| agent_claude.md | 流程纪律(B1-B4 skill + C1-C3 prompt),放 /workspace/CLAUDE.md |
| exploit_roadmap.md | 思路地图+冷门技法,放 /workspace/exploit_roadmap.md |
