#!/usr/bin/env python3
"""列出评测输出目录里运行成功(总分 > 0)的任务。

用法:
  python3 scripts/list_success.py <目录>             # 只列成功题
  python3 scripts/list_success.py <目录> --all       # 成功 + 失败都列
  python3 scripts/list_success.py <目录> --min 0.5   # 分数阈值(默认 > 0)

目录下递归查找 **/result.json,总分 = sum(checks[*].score)。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def score_of(result_path: Path) -> float:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return sum(float(c.get("score", 0)) for c in data.get("checks", []))
    except Exception:  # noqa: BLE001 - 损坏/缺字段的 result.json 按 0 分处理
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", type=Path, nargs="?", default=Path("."),
                    help="评测输出目录(默认当前目录)")
    ap.add_argument("--all", action="store_true", help="同时列出失败(0 分)任务")
    ap.add_argument("--min", type=float, default=0.0,
                    help="成功阈值,score > 该值(默认 > 0)")
    args = ap.parse_args()

    if not args.root.is_dir():
        ap.error(f"目录不存在: {args.root}")

    files = sorted(args.root.glob("**/result.json"))
    ok: list[tuple[str, float]] = []
    fail: list[str] = []
    for f in files:
        task = str(f.parent.relative_to(args.root))
        s = score_of(f)
        if s > args.min:
            ok.append((task, s))
        else:
            fail.append(task)

    for path, score in ok:
        print(f"{path}  score={score}")
    if args.all:
        for path in fail:
            print(f"{path}  score=0 (fail)")
    print(f"=== 成功 {len(ok)} / 总计 {len(files)} ===")


if __name__ == "__main__":
    main()
