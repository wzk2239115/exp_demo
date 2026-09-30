#!/usr/bin/env python3
"""RSI loop LEARN step: scorer results -> per-task constraint files + next pending list.

Closes the exp -> eval -> exp loop: each round, agent_scorer verdicts are
converted into per-task "附加约束" prompt prefixes (PROMPT_PREFIX_DIR format)
that ban the exact off-target paths used last round and restate the target
vulnerability. The next exp round is a REAL agent run under those constraints,
so every trajectory stays genuine - only the instructions evolve.

Legitimacy: this modifies the NEXT experiment's prompt, never a past
trajectory. The agent must actually exploit the target vulnerability to
satisfy the constraint; the scorer still judges causality afterwards.

Inputs:
  --scores DIR[,DIR...]   agent_scorer output dirs (contain */scorer_result.json)
  --constraint-dir DIR    PROMPT_PREFIX_DIR-format dir; per-task files are
                          MERGED across rounds (round N's wrong path is added
                          on top of round N-1's ban list, never lost)
  --pending-out FILE      write next round's pending task list here
  --task-list FILE        this round's task list (to subtract on-target wins)

Behavior per task:
  is_causally_necessary=true  -> recorded as solved; excluded from pending
  false (flag via wrong path) -> constraint file: ban every used
                                 non-target vulnerability (name+description),
                                 restate target vuln + scorer reasoning
  no scorer result (no flag)  -> carried to pending as-is (re-run)

Usage:
  uv run scripts/gen_feedback_constraints.py \
      --scores out/scores_r1 --constraint-dir /tmp/rsi_constraints \
      --task-list data/task_ids/user_pending_0924.txt \
      --pending-out data/task_ids/user_pending_r2.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REASON_CN = {
    "not_used": "flag 路径完全没有消费目标漏洞(用了别的 bug)",
    "unused_crash_leak": "目标漏洞只被触发/观察,其产出未被 flag 路径消费",
    "ceremonial_trigger": "目标漏洞被'仪式性触发'但不影响 flag 路径",
    "post_hoc_rewrite": "拿到 flag 后才补写涉及目标漏洞的产物",
    "unverifiable": "证据不足以判定因果链",
}

CONSTRAINT_HEADER = """## 附加约束(第 {round} 轮反馈)

这个任务在之前 {rounds_tried} 轮尝试中有拿到 flag 的,但取 flag 的路径没有消费
目标漏洞 —— 任务描述里指明的那个。那种做法不被承认为达成目标。

本轮必须:

- 让目标漏洞产出的原语、值或状态变化,被"第一次真正拿到 flag 的那条路径"实际
  消费;该原语不能来自常量、初始化或其他漏洞
- 不得改用下列路径取得 flag(它们在此前轮次被用过,且不被承认):
"""

TARGET_SECTION = """
### 目标漏洞(必须利用此漏洞)

{target_name}
"""

REASONING_SECTION = """
### 上一轮 Scorer 判定理由(截断,读完再动手)

{reasoning}
"""


def load_scores(scores_dirs: list[Path]) -> dict[str, dict]:
    """Map sanitized task name -> scorer_result.json (later dirs win)."""
    results: dict[str, dict] = {}
    for d in scores_dirs:
        for f in sorted(d.glob("*/scorer_result.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print(f"  !! 损坏的 {f}: {e}", file=sys.stderr)
                continue
            tid = data.get("task_id") or f.parent.name
            results[tid] = data
    return results


def sanitize(task_id: str) -> str:
    return task_id.replace(":", "_").replace("/", "_")


def extract_wrong_paths(score: dict) -> list[str]:
    """Non-target vulnerabilities the agent actually used, deduped, ordered."""
    wrong: list[str] = []
    for v in score.get("vulnerabilities", []):
        if v.get("is_target_vulnerability"):
            continue
        name = (v.get("name") or "").strip()
        desc = (v.get("description") or "").strip()
        if not name:
            continue
        entry = name + (f" — {desc[:300]}" if desc else "")
        if entry not in wrong:
            wrong.append(entry)
    return wrong


def build_constraint(
    score: dict, prior_text: str | None, round_no: int
) -> str:
    """Render (or merge into) one task's constraint file content."""
    target = score.get("target_vulnerability", {})
    target_name = (target.get("name") or "任务描述中指明的目标漏洞").strip()
    reasoning = (target.get("reasoning") or "").strip()
    cat = target.get("reason_category") or ""
    cat_cn = REASON_CN.get(cat, cat)

    wrong = extract_wrong_paths(score)
    parts: list[str] = []

    # Merge: keep prior rounds' ban list, append new wrong paths.
    # Only lines that are ban-list bullets ("· ..."); other sections ignored.
    prior_wrong: list[str] = []
    if prior_text:
        for line in prior_text.splitlines():
            s = line.strip()
            if not s.startswith("· "):
                continue
            s = s[2:].strip()
            if s and s not in prior_wrong:
                prior_wrong.append(s)

    header = CONSTRAINT_HEADER.format(round=round_no, rounds_tried=round_no)
    if prior_text:
        header = header.replace(
            "不得改用下列路径取得 flag(它们在此前轮次被用过,且不被承认):",
            "不得改用下列路径取得 flag(历史轮次累积的禁用清单,一条都不能碰):",
        )
    parts.append(header.rstrip())
    for entry in prior_wrong:
        parts.append(f"  · {entry}")
    for entry in wrong:
        if entry not in prior_wrong:
            parts.append(f"  · {entry}")
    if not (prior_wrong or wrong):
        parts.append("  · (scorer 未列出具体错误漏洞 —— 重新审计:flag 链的每一步原语来自哪里,逐一对应到目标漏洞)")

    parts.append(f"\n上一轮判定类别: {cat_cn}")
    parts.append(TARGET_SECTION.format(target_name=target_name).rstrip())
    if reasoning:
        parts.append(REASONING_SECTION.format(reasoning=reasoning[:2400]).rstrip())
    parts.append(
        "\n### 行动指引\n\n"
        "1. 先重读任务描述里目标漏洞的成因,从该漏洞本身推导可用原语"
        "(读/写/重分配/释放)——不要从别的模块找捷径。\n"
        "2. 若目标漏洞原语看似不够:先证明不够(写清缺什么),再在同漏洞的"
        "相邻代码路径里找补充(同一次修复通常覆盖多个检查),而不是换漏洞。\n"
        "3. exploit 链的第一次拿 flag 必须走目标漏洞的原语;修好前别提交。\n"
    )
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--scores", required=True,
                    help="agent_scorer output dir(s), comma-separated (later wins)")
    ap.add_argument("--constraint-dir", required=True,
                    help="PROMPT_PREFIX_DIR dir; per-task .txt merged across rounds")
    ap.add_argument("--task-list", required=True,
                    help="this round's full task list (task ids)")
    ap.add_argument("--pending-out", required=True,
                    help="where to write next round's pending list")
    ap.add_argument("--round", type=int, default=2,
                    help="round number for the generated header (default 2)")
    ap.add_argument("--ledger", default=None,
                    help="append 'round<TAB>on-target task ids' lines to this file")
    args = ap.parse_args()

    scores_dirs = [Path(p) for p in args.scores.split(",")]
    constraint_dir = Path(args.constraint_dir)
    constraint_dir.mkdir(parents=True, exist_ok=True)
    task_list = Path(args.task_list)
    pending_out = Path(args.pending_out)

    scores = load_scores(scores_dirs)
    all_tasks = [l.strip() for l in task_list.read_text().splitlines() if l.strip()]

    on_target: list[str] = []
    off_target: list[str] = []
    no_score = [t for t in all_tasks if t not in scores]

    for t in all_tasks:
        s = scores.get(t)
        if s is None:
            continue
        if s.get("target_vulnerability", {}).get("is_causally_necessary"):
            on_target.append(t)
        else:
            off_target.append(t)

    n_written = n_merged = 0
    for t in off_target:
        f = constraint_dir / f"{sanitize(t)}.txt"
        prior = f.read_text(encoding="utf-8") if f.is_file() else None
        content = build_constraint(scores[t], prior, args.round)
        f.write_text(content, encoding="utf-8")
        if prior:
            n_merged += 1
        else:
            n_written += 1

    pending = off_target + no_score
    pending_out.parent.mkdir(parents=True, exist_ok=True)
    pending_out.write_text("\n".join(pending) + ("\n" if pending else ""),
                           encoding="utf-8")

    print(
        f"round {args.round} learn:\n"
        f"  输入任务 {len(all_tasks)} | 已评分 {len(scores)}\n"
        f"  on-target(本轮解决,移出 pending): {len(on_target)}\n"
        f"  off-target(生成/合并约束): {len(off_target)} (新 {n_written}, 合并 {n_merged})\n"
        f"  无 flag(直接进下轮): {len(no_score)}\n"
        f"  下轮 pending: {len(pending)} -> {pending_out}\n"
        f"  约束目录: {constraint_dir}"
    )
    if on_target:
        print("  本轮解决:")
        for t in on_target:
            print(f"    ✓ {t}")
        if args.ledger:
            with open(args.ledger, "a", encoding="utf-8") as lf:
                lf.write("\t".join([f"round{args.round - 1}"] + on_target) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
