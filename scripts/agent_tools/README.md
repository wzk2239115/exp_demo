# agent_tools — toolbox + guidance for the agent

Deploy into the container (for interactive verification):
```bash
# After starting an interactive container, run on the host (copies tools + guidance
# into the container's /workspace):
CNAME=interactive-xxx  # your container name
docker cp scripts/agent_tools "$CNAME:/workspace/tools"
docker cp docs/agent_claude.md "$CNAME:/workspace/CLAUDE.md"
docker cp docs/exploit_roadmap.md "$CNAME:/workspace/exploit_roadmap.md"
docker exec -u0 "$CNAME" chmod +x /workspace/tools/*.sh /workspace/tools/*.py
# Build the LD_PRELOAD library inside the container:
docker exec -u0 -w /workspace/tools/ldpreload_toolbox "$CNAME" bash build.sh
```

When the agent runs cc in /workspace it auto-loads CLAUDE.md (the guide), and reads
exploit_roadmap.md (the technique map) when stuck.

## Tools

| File | What it does | Stuck point it addresses |
|---|---|---|
| env_check.sh | Startup environment pre-check; writes facts.json | Environment/tools, time (saves the first ~20 steps) |
| remote_io.py | Remote interaction wrapper + output-channel verification | Remote interaction not established |
| core_analyzer.py | Read core dumps when ptrace is banned | Environment/tool restrictions |
| check_fact.py | Cache of verified facts; prevents re-verification | Static-audit dead loops |
| ldpreload_toolbox/ | malloc/free tracing (bypasses ptrace) | Environment restrictions (166x most frequent) |
| vm_lifecycle.sh | VM start/wait/transfer/cleanup | Kernel-task environment confusion |
| skel/ | Per-vuln-class exploit skeletons (bof/uaf/heap/ghostscript); start by filling in a template | Low willingness to write code / low exploit completion |

## Guidance / maps

| File | What it does |
|---|---|
| agent_claude.md | Process discipline (B1-B4 skills + C1-C3 prompts); placed at /workspace/CLAUDE.md |
| exploit_roadmap.md | Idea map + obscure techniques; placed at /workspace/exploit_roadmap.md |
