# RUNBOOK — user 榜单提分作业规范（溯源 + 省时）

## 溯源要求（组内规定）

每次跑批的两个必记信息: **模型** + **方法**。落盘在 `evol_loop/user_success.tsv`
(每行一个通关任务: task_id / date / model / method / score / source)。

- **模型**: `scripts/update_success_ledger.py` 自动从任务 `config.json`
  的 `agent_extra_kwargs.claude_model` 提取, 不需要手填。
- **方法**: 跑完一批后手动扫台账时用 `--method` 标注。命名规范:

| method 标签 | 含义 |
|---|---|
| `assist-v0` | 无辅助基线(r0 flash) |
| `assist-v2.1` | fixdiff + checklist + playbook + CVE intel |
| `assist-v3` | v2.1 + 环境预制卡 + 范例 |
| `assist-v3-core` | 同 v3, 只跑核心 129 题 |
| `manual` | 人工解出 |

## 标准作业流

```bash
cd /data/wangzekai/exploitgym && git pull

# 0) (一次性) 生成 502 题环境预制卡, 并重生成 CLAUDE.md v3
python3 scripts/probe_task_env.py -j 4
python3 scripts/build_fixdiff_claude_md.py
git add evol_loop/1/env_cards evol_loop/1/claude_md_fixdiff && git commit -m "env cards + claude.md v3" && git push

# 1) 批跑完成后, 台账入账 + 生成下一批待跑清单(自动跳过已通关)
python3 scripts/update_success_ledger.py out/<槽位>/run_agent --method assist-v3
python3 scripts/gen_pending_tasks.py                # 全量待跑 -> data/task_ids/user_pending.txt
python3 scripts/gen_pending_tasks.py --core --output data/task_ids/user_core_pending.txt
git add evol_loop/user_success.tsv && git commit -m "ledger" && git push

# 2) 核心题换强模型 A/B (v4-pro, 单独槽位)
CLAUDE_MD_DIR=evol_loop/1/claude_md_fixdiff \
GLM_PROVIDER=anthropic GLM_API_KEY="<360 key>" \
GLM_MODEL=deepseek/deepseek-v4-pro MODEL_ALIAS=deepseek-v4-pro \
TASKS_FILE=data/task_ids/user_core_pending.txt MAX_WORKERS=6 TIMEOUT=7200 \
bash run_as.sh user-pro-core
# 完成后: --method assist-v3-core 入账

# 3) flash 继续扫非核心余量
TASKS_FILE=data/task_ids/user_pending.txt ... bash run_as.sh deepseek-flash-r2
```

## 关键事实速查

- 可武器化核心类型: heap-write(36) / uaf(30) / double-free(8) / stack-bof(39) ≈ 113 题
  + nofuzz 18; heap-read/msan/segv/timeout 类原语天然弱, 不投主力算力。
- ghostscript 36 题有已验证的 PS 级打法(%pipe%/OutputFile), 见
  `evol_loop/1/exemplars/ghostscript.md`, 已注入对应 CLAUDE.md。
- CVE intel 覆盖 176 题(osv_hits.json), r0 已通关 2 题(16541/16969)已在台账。
- 台账是唯一事实源: 跑批前 `gen_pending_tasks.py`, 永不重跑已通关题。
