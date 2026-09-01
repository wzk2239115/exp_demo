#!/usr/bin/env python3
"""配对对比两轮 agent 日志的行为分布(同任务 r0 vs r1)。

用法:
  python3 scripts/paired_behavior_diff.py <round0_log_dir> <round1_log_dir>

目录里是 collect_rendered_logs.sh 导出的 <task_stem>.log。按文件名(任务)
配对,只统计两边都有的任务,输出:
  - 配对任务数
  - 两轮聚合行为分布(RECON_SOURCE 下降 = 侦察省了)
  - 每任务 RECON_SOURCE% 变化 top10(降最多/升最多)
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_logs import parse_rendered_log, step_action  # noqa: E402


def behavior_pct(log_path: Path) -> tuple[Counter, int]:
    _, _, steps = parse_rendered_log(str(log_path))
    c = Counter(step_action(s) for s in steps)
    return c, len(steps)


def main() -> None:
    d0, d1 = (Path(sys.argv[1]), Path(sys.argv[2]))
    stems0 = {p.stem: p for p in d0.glob("*.log")}
    stems1 = {p.stem: p for p in d1.glob("*.log")}
    common = sorted(set(stems0) & set(stems1))
    print(f"paired tasks: {len(common)} (r0={len(stems0)}, r1={len(stems1)})")

    agg0: Counter = Counter()
    agg1: Counter = Counter()
    recon_delta = []
    for s in common:
        c0, n0 = behavior_pct(stems0[s])
        c1, n1 = behavior_pct(stems1[s])
        if n0 == 0 or n1 == 0:
            continue
        agg0.update(c0)
        agg1.update(c1)
        r0 = 100 * c0.get("RECON_SOURCE", 0) / n0
        r1 = 100 * c1.get("RECON_SOURCE", 0) / n1
        recon_delta.append((r1 - r0, s, r0, r1, n0, n1))

    for tag, agg in (("round0", agg0), ("round1", agg1)):
        t = sum(agg.values())
        print(f"\n== {tag} (steps={t})")
        for k, v in agg.most_common():
            print(f"  {k:16s} {100*v/t:5.1f}%")

    recon_delta.sort()
    print("\n== RECON_SOURCE% 下降最多 (r0 -> r1)")
    for dd, s, r0, r1, n0, n1 in recon_delta[:10]:
        print(f"  {s:40s} {r0:5.1f}% -> {r1:5.1f}%  ({n0}->{n1} steps)")
    print("\n== RECON_SOURCE% 上升最多 (r0 -> r1)")
    for dd, s, r0, r1, n0, n1 in recon_delta[-10:]:
        print(f"  {s:40s} {r0:5.1f}% -> {r1:5.1f}%  ({n0}->{n1} steps)")


if __name__ == "__main__":
    main()
