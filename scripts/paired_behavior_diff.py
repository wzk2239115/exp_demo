#!/usr/bin/env python3
"""配对对比两轮 agent 日志的行为分布(同任务 r0 vs r1)。

用法:
  python3 scripts/paired_behavior_diff.py <round0> <round1_dir>

<round0> 可以是:
  - 日志目录(collect_rendered_logs.sh 导出的 <task_stem>.log)
  - TSV 文件(列: stem \\t steps \\t {行为:次数} JSON;
    用 analyze_logs 本地批量算,适合 r0 原始日志不在本机的场景)
<round1_dir> 是日志目录。按任务名配对,只统计两边都有的任务,输出:
  - 配对任务数
  - 两轮聚合行为分布(RECON_SOURCE 下降 = 侦察省了)
  - 每任务 RECON_SOURCE% 变化 top10(降最多/升最多)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_logs import parse_rendered_log, step_action  # noqa: E402


def behavior_pct(log_path: Path) -> tuple[Counter, int]:
    _, _, steps = parse_rendered_log(str(log_path))
    c = Counter(step_action(s) for s in steps)
    return c, len(steps)


def load_side(arg: str) -> dict[str, tuple[Counter, int]]:
    p = Path(arg)
    if p.is_file():
        out = {}
        for line in p.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            out[parts[0]] = (Counter(json.loads(parts[2])), int(parts[1]))
        return out
    return {q.stem: behavior_pct(q) for q in p.glob("*.log")}


def main() -> None:
    side0 = load_side(sys.argv[1])
    side1 = load_side(sys.argv[2])
    common = sorted(set(side0) & set(side1))
    print(f"paired tasks: {len(common)} (r0={len(side0)}, r1={len(side1)})")

    agg0: Counter = Counter()
    agg1: Counter = Counter()
    recon_delta = []
    for s in common:
        c0, n0 = side0[s]
        c1, n1 = side1[s]
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
