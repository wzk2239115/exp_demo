#!/usr/bin/env python3
"""check_fact.py — cache of verified facts; prevents re-verifying the same fact (audit dead loops).

env_check.sh writes /workspace/facts.json; this tool queries/adds to it.
Query before acting: if it's already verified, don't verify again; add new conclusions.

Usage:
    python3 /workspace/tools/check_fact.py query ptrace        # query a fact
    python3 /workspace/tools/check_fact.py add heap_layout "drr_class=112B->km128" step=15
    python3 /workspace/tools/check_fact.py list                # list all
    python3 /workspace/tools/check_fact.py dup "grep cls_fw"   # has this action been done before?
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
            sys.exit(0)  # verified; don't re-verify
        else:
            print(f"[fact] {key} not recorded; needs verification")
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
        print(f"[fact] recorded {key} = {val}")
        return

    if cmd == "list":
        if not d:
            print("(no recorded facts)"); return
        for k, v in d.items():
            if isinstance(v, dict):
                print(f"  {k} = {v.get('value', v)}")
            else:
                print(f"  {k} = {v}")
        return

    if cmd == "dup":
        # Has this action/command been done before? (prevents dead-looping the same grep/objdump)
        needle = sys.argv[2]
        actions = d.get("_actions", [])
        count = sum(1 for a in actions if needle in a.get("cmd", ""))
        if count >= 3:
            print(f"[fact] '{needle}' already executed {count} times -> diminishing returns; force a strategy switch!")
            sys.exit(0)
        actions.append({"cmd": needle, "t": time.time()})
        d["_actions"] = actions[-50:]  # keep only the last 50 actions
        save(d)
        print(f"[fact] '{needle}' occurrence {count+1}")
        return

    print(__doc__); sys.exit(1)

if __name__ == "__main__":
    main()
