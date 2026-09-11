#!/usr/bin/env python3
"""汇总 out/ 下所有批次的成功题,跨批次按 task_id 去重。

用法:
  python3 scripts/summary_success.py                    # 扫 out/ 下全部
  python3 scripts/summary_success.py --root out         # 指定根目录
  python3 scripts/summary_success.py --detail           # 列出所有去重后的成功题
  python3 scripts/summary_success.py --diff             # 只列台账外的新增
  python3 scripts/summary_success.py --min 0.5          # 分数阈值(默认 > 0)

输出:
  - 每个批次的成功数 / 总任务数
  - 跨批次去重后的总成功数
  - 与 evol_loop/user_success.tsv 台账对比,显示台账外新增数
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = REPO_ROOT / "out"
DEFAULT_LEDGER = REPO_ROOT / "evol_loop" / "user_success.tsv"


def score_of(result_path: Path) -> float:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return sum(float(c.get("score", 0)) for c in data.get("checks", []))
    except Exception:  # noqa: BLE001
        return 0.0


def task_id_of(result_path: Path) -> str:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return data.get("task_id", str(result_path.parent.name))
    except Exception:  # noqa: BLE001
        return str(result_path.parent.name)


def load_ledger(ledger: Path) -> set[str]:
    known: set[str] = set()
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines()[1:]:
            if line.strip():
                known.add(line.split("\t")[0])
    return known


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help=f"out 根目录 (默认 {DEFAULT_OUT_ROOT})",
    )
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="台账 tsv 路径")
    ap.add_argument(
        "--min", type=float, default=0.0, help="成功阈值, score > 该值 (默认 > 0)"
    )
    ap.add_argument(
        "--detail", action="store_true", help="列出所有去重后的成功 task_id"
    )
    ap.add_argument("--diff", action="store_true", help="只列台账外的新增 task_id")
    args = ap.parse_args()

    if not args.root.is_dir():
        ap.error(f"目录不存在: {args.root}")

    batch_solved: dict[str, set[str]] = {}
    batch_total: dict[str, int] = {}
    all_solved: dict[str, str] = {}  # task_id -> first batch that solved it

    for batch_dir in sorted(args.root.iterdir()):
        run_dir = batch_dir / "run_agent"
        if not run_dir.is_dir():
            continue
        batch = batch_dir.name
        batch_solved[batch] = set()
        batch_total[batch] = 0
        for rj in sorted(run_dir.glob("**/result.json")):
            batch_total[batch] += 1
            s = score_of(rj)
            if s > args.min:
                tid = task_id_of(rj)
                batch_solved[batch].add(tid)
                if tid not in all_solved:
                    all_solved[tid] = batch

    known = load_ledger(args.ledger)
    new_tasks = {tid for tid in all_solved if tid not in known}

    print(f"{'批次':<22s} {'成功':>5s} {'总计':>5s}")
    print("-" * 36)
    for batch in sorted(batch_total):
        print(f"{batch:<22s} {len(batch_solved[batch]):>5d} {batch_total[batch]:>5d}")
    print("-" * 36)
    print(f"跨批次去重总成功: {len(all_solved)}")
    print(f"台账已有:          {len(known)}")
    print(f"台账外新增:        {len(new_tasks)}")
    print()

    if args.detail:
        print("=== 所有成功题 (去重) ===")
        for tid in sorted(all_solved):
            marker = "  " if tid in known else "+ "
            print(f"{marker}{tid}  [{all_solved[tid]}]")
        print()

    if args.diff:
        print(f"=== 台账外新增 ({len(new_tasks)} 题) ===")
        for tid in sorted(new_tasks):
            print(f"  + {tid}  [{all_solved[tid]}]")


if __name__ == "__main__":
    main()
