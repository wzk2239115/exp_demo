#!/usr/bin/env python3
"""check_fact.py — 已验证结论缓存,防重复验证同一事实(防审计死循环)。

env_check.sh 写入 /workspace/facts.json;本工具在其上增删查。
行动前先 query,已验证就别再验;新结论 add 进去。

用法:
    python3 /workspace/tools/check_fact.py query ptrace        # 查
    python3 /workspace/tools/check_fact.py add heap_layout "drr_class=112B->km128" step=15
    python3 /workspace/tools/check_fact.py list                # 全列
    python3 /workspace/tools/check_fact.py dup "grep cls_fw"   # 这个动作做过了吗
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

FACTS = Path(os.environ.get("FACTS_FILE", "/workspace/facts.json"))

def load() -> dict:
    if FACTS.is_file():
        try:
            return json.loads(FACTS.read_text())
        except Exception:
            return {}
    return {}

def save(d: dict) -> None:
    FACTS.parent.mkdir(parents=True, exist_ok=True)
    FACTS.write_text(json.dumps(d, ensure_ascii=False, indent=2))

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    d = load()

    if cmd == "query":
        key = sys.argv[2]
        v = d.get(key)
        if v is not None:
            print(f"[fact] {key} = {v}")
            sys.exit(0)  # 已验证,别再验
        else:
            print(f"[fact] {key} 未记录,需要验证")
            sys.exit(2)

    if cmd == "add":
        if len(sys.argv) < 4:
            print("add <key> <value> [step=N]"); sys.exit(1)
        key, val = sys.argv[2], sys.argv[3]
        meta = {"value": val, "t": time.time()}
        for a in sys.argv[4:]:
            if a.startswith("step="):
                meta["step"] = a[5:]
        d[key] = meta
        save(d)
        print(f"[fact] 记录 {key} = {val}")
        return

    if cmd == "list":
        if not d:
            print("(无已记录事实)"); return
        for k, v in d.items():
            if isinstance(v, dict):
                print(f"  {k} = {v.get('value', v)}")
            else:
                print(f"  {k} = {v}")
        return

    if cmd == "dup":
        # 这个动作/命令做过了吗(防死循环重复执行同一 grep/objdump)
        needle = sys.argv[2]
        actions = d.get("_actions", [])
        count = sum(1 for a in actions if needle in a.get("cmd", ""))
        if count >= 3:
            print(f"[fact] '{needle}' 已执行 {count} 次 → 收益递减,强制切换策略!")
            sys.exit(0)
        actions.append({"cmd": needle, "t": time.time()})
        d["_actions"] = actions[-50:]  # 只留最近 50 个动作
        save(d)
        print(f"[fact] '{needle}' 第 {count+1} 次")
        return

    print(__doc__); sys.exit(1)

if __name__ == "__main__":
    main()
