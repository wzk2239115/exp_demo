#!/usr/bin/env python3
"""RSI 闭环效果仪表盘。

用法:
  python3 scripts/rsi_status.py <base>            # 例: python3 scripts/rsi_status.py user-rsi
  python3 scripts/rsi_status.py <base> --running  # 附带在跑波次的容器数

读取 logs/<base>-rsi/ (pending_r*.txt, exp_r*.txt, scores_r*/, constraints/,
ledger.txt) 与各波 exp 输出目录, 输出:

  每波:  任务数 | flag数 | 已评 | on-target | 该波出列
  累计:  on-target 总出列(ledger), 当前 pending 规模
  约束效果: 最新完成波里, 有约束题(前波 off-target) vs 无约束题(前波无 flag)
            的 flag 重获率对比 —— 这就是"约束是否在起作用"的直接读数。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def flag_captured(result_json: Path) -> bool:
    try:
        d = json.loads(result_json.read_text(encoding="utf-8"))
        return sum(float(c.get("score", 0)) for c in d.get("checks", [])) > 0
    except Exception:  # noqa: BLE001
        return False


def wave_stats(exp_dir: Path, tasks: list[str]) -> dict[str, bool]:
    """Map task_id -> flag captured, for one wave's exp output."""
    out = {}
    for t in tasks:
        fam = t.split(":", 1)[0]
        d = exp_dir / fam / t.replace(":", "_").replace("/", "_")
        rj = d / "result.json"
        if rj.is_file():
            out[t] = flag_captured(rj)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="RSI base 名, 例 user-rsi")
    ap.add_argument("--running", action="store_true",
                    help="附带在跑波次的 docker 容器数")
    args = ap.parse_args()

    state = Path(f"logs/{args.base}-rsi")
    if not state.is_dir():
        print(f"状态目录不存在: {state}")
        return 1

    rounds = 1
    while (state / f"pending_r{rounds + 1}.txt").is_file():
        rounds += 1

    ledger_total = 0
    ledger: dict[str, int] = {}
    if (state / "ledger.txt").is_file():
        for line in (state / "ledger.txt").read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                ledger[parts[0]] = len(parts) - 1
                ledger_total += len(parts) - 1

    print(f"══ RSI 闭环 [{args.base}] ══")
    print(f"{'波':<4} {'任务':>5} {'flag':>5} {'已评':>5} {'on-tgt':>7} {'出列':>5}")
    prev_stats: dict[str, bool] | None = None
    prev_constrained: set[str] | None = None
    latest_done = 0

    for r in range(1, rounds + 1):
        pend_f = state / f"pending_r{r}.txt"
        if not pend_f.is_file():
            break
        tasks = [l.strip() for l in pend_f.read_text().splitlines() if l.strip()]
        exp_f = state / f"exp_r{r}.txt"
        exp_dir = Path(exp_f.read_text().strip()) if exp_f.is_file() else None

        if exp_dir is None or not exp_dir.is_dir():
            print(f"r{r:<3} {len(tasks):>5} {'-':>5} {'-':>5} {'-':>7} {'-':>5}  (exp 未开始/无记录)")
            continue

        stats = wave_stats(exp_dir, tasks)
        flagged = sum(1 for v in stats.values() if v)

        scores_dir = state / f"scores_r{r}"
        on_target = scored = 0
        if scores_dir.is_dir():
            for f in scores_dir.glob("*/scorer_result.json"):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    scored += 1
                    if d.get("target_vulnerability", {}).get("is_causally_necessary"):
                        on_target += 1
                except Exception:  # noqa: BLE001
                    pass
        exited = ledger.get(f"round{r}", 0)
        print(f"r{r:<3} {len(tasks):>5} {flagged:>5} {scored:>5} {on_target:>7} {exited:>5}"
              + ("  ← 本波在跑/未评完" if scored < flagged else ""))

        if scored >= flagged and flagged > 0:
            latest_done = r
            prev_stats = stats
            prev_constrained = set()
            cons_dir = state / "constraints"
            if cons_dir.is_dir():
                prev_constrained = {
                    p.stem.replace("_", ":", 1).replace("_", "/", 1)
                    for p in cons_dir.glob("*.txt")
                    # 只算本波前已存在的约束是近似;此处按文件存在计
                }

    print(f"\n累计 on-target 出列: {ledger_total} (ledger.txt)")
    for k, v in ledger.items():
        print(f"  {k}: {v}")

    # 约束效果: 最新完成波里 有约束 vs 无约束 的 flag 重获率
    cur_pend = state / f"pending_r{rounds}.txt"
    if cur_pend.is_file():
        n = sum(1 for l in cur_pend.read_text().splitlines() if l.strip())
        print(f"当前 pending_r{rounds}: {n} 题")

    if prev_stats is not None and prev_constrained is not None:
        cons_hit = cons_tot = 0
        free_hit = free_tot = 0
        for t, ok in prev_stats.items():
            if t in prev_constrained:
                cons_tot += 1
                cons_hit += ok
            else:
                free_tot += 1
                free_hit += ok
        if cons_tot and free_tot:
            print(f"\n约束效果(第 {latest_done} 波):")
            print(f"  有约束题 flag 重获率: {cons_hit}/{cons_tot} = {cons_hit/cons_tot:.0%}")
            print(f"  无约束题 flag 重获率: {free_hit}/{free_tot} = {free_hit/free_tot:.0%}")
            print("  (有约束率低 = 禁用清单生效;两者都高 = 约束太弱/模型换路了)")

    if args.running:
        for r in range(1, rounds + 2):
            owner = f"{args.base}-r{r}"
            try:
                n = subprocess.run(
                    ["docker", "ps", "--filter", f"label=exploitgym.owner={owner}", "-q"],
                    capture_output=True, text=True, timeout=10,
                ).stdout.split()
                if n:
                    print(f"[running] r{r}: {len(n)} 容器在跑")
            except Exception:  # noqa: BLE001
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
