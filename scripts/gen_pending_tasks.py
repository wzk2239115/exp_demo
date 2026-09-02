#!/usr/bin/env python3
"""生成"待跑" user 任务清单: 全量 user 任务 - 台账中已通关的任务。

省时机制: 已通关的靶场不再进 TASKS_FILE, 跑批自动跳过。

用法:
  python3 scripts/gen_pending_tasks.py                     # user_v1.txt - 已通关 -> data/task_ids/user_pending.txt
  python3 scripts/gen_pending_tasks.py --core              # 只保留可武器化核心类型(heap-write/uaf/double-free/stack-bof)
  python3 scripts/gen_pending_tasks.py --output别的文件
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL = REPO_ROOT / "data/task_ids/user_v1.txt"
DEFAULT_LEDGER = REPO_ROOT / "evol_loop/user_success.tsv"
DEFAULT_CRASH = REPO_ROOT / "evol_loop/1/crash_types.tsv"
DEFAULT_OUT = REPO_ROOT / "data/task_ids/user_pending.txt"
CORE_TYPES = {"heap-write", "uaf", "double-free", "stack-bof"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", type=Path, default=DEFAULT_FULL)
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--crash-types", type=Path, default=DEFAULT_CRASH)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--core", action="store_true",
                    help="只保留核心可武器化类型 (heap-write/uaf/double-free/stack-bof)")
    ap.add_argument("--exclude-file", type=Path, default=None,
                    help="额外剔除清单(如其他模型已解的题,一行一个 task_id)")
    args = ap.parse_args()

    def norm(t: str) -> str:
        return t.replace(":", "_").replace("/", "_")

    solved_n: set[str] = set()
    if args.ledger.is_file():
        for line in args.ledger.read_text().splitlines()[1:]:
            if line.strip():
                solved_n.add(norm(line.split("\t")[0]))

    extra_excl: set[str] = set()
    if args.exclude_file and args.exclude_file.is_file():
        for line in args.exclude_file.read_text().splitlines():
            if line.strip():
                extra_excl.add(norm(line.strip()))

    ctype: dict[str, str] = {}
    if args.crash_types.is_file():
        for line in args.crash_types.read_text().splitlines()[1:]:
            p = line.split("\t")
            if len(p) >= 2:
                ctype[p[0]] = p[1]

    tasks = [l.strip() for l in args.full.read_text().splitlines() if l.strip()]
    kept, skipped, dropped_noncore = [], 0, 0
    for t in tasks:
        if norm(t) in solved_n or norm(t) in extra_excl:
            skipped += 1
            continue
        if args.core:
            entry = t.removeprefix("user:")
            if ctype.get(entry) not in CORE_TYPES and not entry.startswith("nofuzz/"):
                dropped_noncore += 1
                continue
        kept.append(t)

    args.output.write_text("\n".join(kept) + "\n")
    print(f"total={len(tasks)} kept={len(kept)} already-solved-skipped={skipped}"
          + (f" non-core-dropped={dropped_noncore}" if args.core else ""))
    print(f"-> {args.output}")


if __name__ == "__main__":
    main()
