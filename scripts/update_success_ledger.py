#!/usr/bin/env python3
"""Update the user-task success ledger from eval output directories.

组内溯源要求: 每个通关任务记录 (task_id, 模型, 方法, 分数, 日期, 结果来源)。
模型自动从任务的 config.json (agent_extra_kwargs.claude_model) 提取;
方法用 --method 显式标注(命名规范见 evol_loop/1/RUNBOOK.md)。

用法:
  # 扫描一个 out 根目录(批跑完/中断后执行), 方法标签必填:
  python3 scripts/update_success_ledger.py out/deepseek-flash-r1/run_agent --method assist-v2.1
  # 多个根目录一起扫:
  python3 scripts/update_success_ledger.py out/a/run_agent out/b/run_agent --method assist-v3
  # 只看会新增什么(干跑):
  ... --dry-run

台账: evol_loop/user_success.tsv (已存在的条目按 task_id 去重, 不覆盖)。
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "evol_loop" / "user_success.tsv"


def scan_root(root: Path) -> list[dict]:
    rows = []
    for rj in root.glob("*/*/result.json"):
        try:
            r = json.loads(rj.read_text())
        except Exception:
            continue
        score = sum(float(c.get("score", 0)) for c in r.get("checks", []))
        if score <= 0:
            continue
        cfg_p = rj.parent / "config.json"
        model = "?"
        if cfg_p.is_file():
            try:
                cfg = json.loads(cfg_p.read_text())
                model = (
                    cfg.get("agent_extra_kwargs", {}).get("claude_model")
                    or cfg.get("agent_extra_kwargs", {}).get("gemini_model")
                    or cfg.get("agent_extra_kwargs", {}).get("model")
                    or "?"
                )
            except Exception:
                pass
        date = datetime.date.fromtimestamp(
            rj.stat().st_mtime
        ).isoformat()
        rows.append({
            "task_id": r.get("task_id", str(rj.parent.name)),
            "date": date,
            "model": model,
            "method": "?",
            "score": score,
            "source": str(rj.parent),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path, help="out/<name>/run_agent 目录")
    ap.add_argument("--method", required=True, help="方法标签, 如 assist-v2.1 / assist-v3 (溯源必填)")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    known: set[str] = set()
    if args.ledger.is_file():
        for line in args.ledger.read_text().splitlines()[1:]:
            if line.strip():
                known.add(line.split("\t")[0])
    header = "task_id\tdate\tmodel\tmethod\tscore\tsource"
    new = []
    for root in args.roots:
        for row in scan_root(root):
            row["method"] = args.method
            if row["task_id"] not in known:
                new.append(row)
                known.add(row["task_id"])
    new.sort(key=lambda r: r["task_id"])
    for r in new:
        print(f"  + {r['task_id']:42s} {r['model']:22s} {r['method']:12s} score={r['score']}")
    print(f"新增 {len(new)} 条" + ("(dry-run, 未写入)" if args.dry_run else ""))
    if new and not args.dry_run:
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        if not args.ledger.is_file():
            args.ledger.write_text(header + "\n")
        with args.ledger.open("a") as f:
            for r in new:
                f.write(
                    f"{r['task_id']}\t{r['date']}\t{r['model']}\t{r['method']}"
                    f"\t{r['score']}\t{r['source']}\n"
                )
        print(f"-> {args.ledger}")


if __name__ == "__main__":
    main()
