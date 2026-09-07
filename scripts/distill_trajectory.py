#!/usr/bin/env python3
"""distill_trajectory.py — compress a claude-code session jsonl by dropping dead operations, then emit a resumable session file.

Pipeline:
  parse main chain -> pair assistant(tool_use) entries with their user(tool_result)
  -> heuristic collapse of exact consecutive repeats
  -> optional model judging (KEEP/DROP per operation, batched)
  -> rewrite parentUuid chain -> validate -> write <new_session>.jsonl + report.

Only whole entries are ever removed; message content is never edited (thinking
blocks carry signatures). An assistant entry is a drop candidate only when it is
pure tool_use (no text), its next chain entry is a pure tool_result user entry
covering exactly its tool_use ids, and it has no sidechain children.

Usage:
  python3 scripts/distill_trajectory.py <session.jsonl> --no-model   # heuristic only
  python3 scripts/distill_trajectory.py <session.jsonl>              # + model judging
  python3 scripts/distill_trajectory.py <session.jsonl> --dry-run    # stats only, no output

glm-5.2/5.3 as judge (360 native endpoint requires thinking=enabled):
  python3 scripts/distill_trajectory.py <session.jsonl> --model z-ai/glm-5.2

The source file is NEVER modified (read-only): output always goes to a new
<new_session_id>.jsonl next to it, plus a <new_session_id>.distill_report.json.

After distillation, token estimates are printed and compared to --context-budget
(default 120000): if the distilled session still exceeds the budget, a warning
is shown and the judge is told to drop more aggressively on re-run.

API config (model judging):
  ANTHROPIC_BASE_URL or GLM_BASE_URL  (default https://api.360.cn, /v1/messages appended)
  ANTHROPIC_AUTH_TOKEN or GLM_API_KEY
  GLM_MODEL / --model                 (default deepseek/deepseek-v4-flash)

Resume the distilled session (same escaped cwd, same CLAUDE_CONFIG_DIR):
  cp <new_sid>.jsonl <config_dir>/projects/-workspace/
  cd /workspace && claude-code.sh -r <new_sid>
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

CHAIN_TYPES = {"assistant", "user", "attachment", "system", "summary"}
DROP_SAFE_LAST = 2
INPUT_LIMIT = 220
RESULT_LIMIT = 200


class Op:
    def __init__(self, no: int, a: dict, u: dict | None):
        self.no = no
        self.a = a
        self.u = u
        self.tool_uses = [b for b in (a.get("message", {}).get("content") or [])
                          if isinstance(b, dict) and b.get("type") == "tool_use"]
        self.verdict = "keep"
        self.reason = ""
        self.summary = ""
        self.fingerprint = ""
        self.tokens = 0

    @property
    def uuid(self):
        return self.a.get("uuid")


CHARS_PER_TOKEN = 3.5


def blocks(entry: dict) -> list:
    c = entry.get("message", {}).get("content")
    return c if isinstance(c, list) else []


def msg_chars(entry: dict) -> int:
    c = entry.get("message", {}).get("content")
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(len(json.dumps(b, ensure_ascii=False)) for b in c if isinstance(b, dict))
    return 0


def estimate_tokens(entries) -> int:
    if entries and isinstance(entries[0], dict):
        return int(sum(msg_chars(e) for e in entries if e.get("type") in CHAIN_TYPES)
                   / CHARS_PER_TOKEN)
    return int(sum(getattr(e, "tokens", 0) for e in entries))


def text_of(block: dict, limit: int) -> str:
    c = block.get("content")
    out = ""
    if isinstance(c, str):
        out = c
    elif isinstance(c, list):
        parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        out = " ".join(parts)
    return " ".join(out.split())[:limit]


def summarize_input(tu: dict) -> str:
    inp = tu.get("input") or {}
    name = tu.get("name", "?")
    if name == "Bash":
        return "Bash: " + str(inp.get("command", ""))[:INPUT_LIMIT]
    if name in ("Read", "Write", "Edit"):
        extra = ""
        if name == "Edit":
            extra = f" old~{len(str(inp.get('oldString', '')))}B new~{len(str(inp.get('newString', '')))}B"
        return f"{name}: {inp.get('file_path', '')}{extra}"[:INPUT_LIMIT]
    if name == "Grep":
        return f"Grep: {inp.get('pattern', '')!r} in {inp.get('include') or inp.get('path') or '.'}"[:INPUT_LIMIT]
    if name == "Glob":
        return f"Glob: {inp.get('pattern', '')}"[:INPUT_LIMIT]
    if name == "Task":
        return f"Task: {inp.get('description', '')} :: {str(inp.get('prompt', ''))[:100]}"[:INPUT_LIMIT]
    if name == "TodoWrite":
        return f"TodoWrite: {len(inp.get('todos', []))} items"
    return f"{name}: {json.dumps(inp, ensure_ascii=False, sort_keys=True)[:INPUT_LIMIT]}"


def summarize_result(op: Op) -> str:
    if op.u is None:
        return "(no result)"
    parts = []
    for b in blocks(op.u):
        if isinstance(b, dict) and b.get("type") == "tool_result":
            tag = "ERR " if b.get("is_error") else ""
            parts.append(tag + text_of(b, RESULT_LIMIT))
    return " | ".join(parts)[:RESULT_LIMIT * 2]


def parse_session(path: Path):
    chain: list[dict] = []
    floating: list[dict] = []
    bad = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            bad += 1
            continue
        if e.get("uuid") and e.get("type") in CHAIN_TYPES:
            chain.append(e)
        else:
            floating.append(e)
    return chain, floating, bad


def build_ops(chain: list[dict], sidechain_parents: set) -> list[Op]:
    ops: list[Op] = []
    for i, e in enumerate(chain):
        if e.get("type") != "assistant":
            continue
        tus = [b for b in blocks(e) if isinstance(b, dict) and b.get("type") == "tool_use"]
        if not tus:
            continue
        if any(isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
               for b in blocks(e)):
            continue
        nxt = chain[i + 1] if i + 1 < len(chain) else None
        pair = None
        if nxt is not None and nxt.get("type") == "user":
            nb = blocks(nxt)
            trs = [b for b in nb if isinstance(b, dict) and b.get("type") == "tool_result"]
            has_text = any(isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
                           for b in nb)
            send_ids = {t.get("id") for t in tus}
            recv_ids = {t.get("tool_use_id") for t in trs}
            if trs and not has_text and send_ids == recv_ids:
                pair = nxt
        if pair is None:
            continue
        if e.get("uuid") in sidechain_parents:
            continue
        op = Op(len(ops), e, pair)
        op.tokens = int((msg_chars(e) + msg_chars(pair)) / CHARS_PER_TOKEN)
        ops.append(op)
    return ops


def find_sidechain_parents(chain: list[dict]) -> set:
    return {e.get("parentUuid") for e in chain if e.get("isSidechain")}


def heuristic_collapse(ops: list[Op]) -> None:
    prev_key = None
    for op in ops:
        inputs = "; ".join(sorted(json.dumps(t.get("input"), ensure_ascii=False, sort_keys=True)
                                  for t in op.tool_uses))
        names = "; ".join(sorted(t.get("name", "?") for t in op.tool_uses))
        errs = ""
        if op.u is not None:
            errs = "; ".join(f"{b.get('is_error')}:{text_of(b, 100)}"
                             for b in blocks(op.u)
                             if isinstance(b, dict) and b.get("type") == "tool_result")
        op.fingerprint = names + " || " + inputs[:400] + " || " + errs[:200]
        key = op.fingerprint
        if key == prev_key:
            op.verdict = "drop"
            op.reason = "heuristic: consecutive exact repeat"
        else:
            prev_key = key


def full_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c
                        if isinstance(p, dict) and p.get("type") == "text")
    return ""


def op_full_text(op: Op, max_chars: int) -> str:
    parts = []
    for tu in op.tool_uses:
        parts.append(f"TOOL: {tu.get('name', '?')}")
        parts.append(f"INPUT: {json.dumps(tu.get('input', {}), ensure_ascii=False)}")
    if op.u is not None:
        for b in blocks(op.u):
            if isinstance(b, dict) and b.get("type") == "tool_result":
                tag = " (ERROR)" if b.get("is_error") else ""
                parts.append(f"RESULT{tag}:")
                parts.append(full_text(b))
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... (truncated, {len(text) - max_chars} more chars)"
    return text


JUDGE_SYSTEM = """You are auditing an AI agent's exploit-development session transcript. You see the FULL original content of each operation (tool call + its result), with its token cost. Decide which operations to KEEP when the session is resumed.

KEEP (include in keep list):
- anything that writes or edits files (Write/Edit), or runs an exploit/PoC
- results that reveal new addresses, offsets, crashes, behaviors, or flags
- first exploration of any area, and anything later operations depend on
- operations whose output is referenced by later operations

DROP (omit from keep list):
- re-reads / re-greps of the same thing already seen earlier with no new outcome
- failed commands retried unchanged, or errors that yielded no information
- exploration branches the agent explicitly abandoned and never used again
- pure noise (repeated ls, identical status checks, no-op commands)
- operations whose results merely confirm earlier findings

If the session exceeds the context budget, be more aggressive. If under budget, prefer keeping. When unsure, KEEP.

Answer with STRICT JSON only: {"keep": [<op numbers to KEEP>], "notes": "<one short paragraph: where the agent got stuck and what to try next>"}"""


def build_judge_prompt(goal: str, chunk: list[Op], total_ops: int,
                       orig_tokens: int, context_budget: int, max_op_chars: int) -> str:
    lines = [f"SESSION GOAL:\n{goal}", "",
             f"Session ~{orig_tokens} tokens, context budget {context_budget}.",
             f"Showing {len(chunk)} operations (of {total_ops} total) with FULL content:", ""]
    for op in chunk:
        lines.append(f"[{op.no}] (~{op.tokens}tok)")
        lines.append(op_full_text(op, max_op_chars))
        lines.append("")
    lines.append('Return JSON: {"keep": [numbers to keep], "notes": "..."}')
    return "\n".join(lines)


def api_messages(url: str, key: str, model: str, system: str, prompt: str,
                 thinking: bool = False, budget_tokens: int = 8192) -> str:
    body_dict: dict = {
        "model": model,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if thinking:
        body_dict["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        body_dict["max_tokens"] = budget_tokens + 4096
    else:
        body_dict["max_tokens"] = 4096
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": key,
        "authorization": f"Bearer {key}",
        "anthropic-version": "2023-06-01",
    })
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.loads(r.read().decode())
            return "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            last_err = f"HTTP {e.code}: {detail}"
            if e.code not in (429, 500, 502, 503, 529):
                break
        except Exception as e:  # noqa: BLE001
            last_err = repr(e)
        time.sleep(5)
    raise RuntimeError(f"API call failed: {last_err}")


def parse_judge_reply(reply: str, all_nums: set) -> tuple:
    """Returns (keep_set, notes). keep_set=None means parse failure -> keep all."""
    s = reply.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    data = None
    try:
        data = json.loads(s)
    except Exception:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(s[start:end + 1])
            except Exception:
                pass
    if data is None:
        return None, ""
    notes = str(data.get("notes", ""))
    if "keep" in data:
        return {int(x) for x in data["keep"]}, notes
    if "drop" in data:
        return all_nums - {int(x) for x in data["drop"]}, notes
    return None, notes


def judge_ops(ops: list[Op], goal: str, url: str, key: str, model: str, batch: int,
              notes_out: list, thinking: bool, budget_tokens: int,
              orig_tokens: int, context_budget: int,
              max_op_tokens: int, judge_limit: int) -> None:
    pending = [op for op in ops if op.verdict != "drop"]
    max_op_chars = max_op_tokens * int(CHARS_PER_TOKEN)
    total_judge_tokens = sum(op.tokens for op in pending) + len(goal) // 4 + 4000

    if total_judge_tokens <= judge_limit:
        chunks = [pending]
        print(f"  single call: {len(pending)} ops, ~{total_judge_tokens} tok "
              f"(limit {judge_limit})", file=sys.stderr)
    else:
        chunks = [pending[i:i + batch] for i in range(0, len(pending), batch)]
        print(f"  batched: {len(pending)} ops in {len(chunks)} calls "
              f"(~{total_judge_tokens} tok > limit {judge_limit})", file=sys.stderr)

    for chunk in chunks:
        all_nums = {op.no for op in chunk}
        prompt = build_judge_prompt(goal, chunk, len(pending),
                                    orig_tokens, context_budget, max_op_chars)
        reply = api_messages(url, key, model, JUDGE_SYSTEM, prompt, thinking, budget_tokens)
        keep_set, notes = parse_judge_reply(reply, all_nums)
        if notes:
            notes_out.append(notes)
        if keep_set is None:
            print(f"  judged {chunk[0].no}..{chunk[-1].no}: parse failed, keeping all",
                  file=sys.stderr)
            continue
        for op in chunk:
            if op.no not in keep_set:
                op.verdict = "drop"
                op.reason = "model: not in keep set"
        kept = len(keep_set & all_nums)
        print(f"  judged {chunk[0].no}..{chunk[-1].no}: keep {kept}/{len(chunk)}, "
              f"drop {len(chunk) - kept}", file=sys.stderr)


def rewrite(chain: list[dict], floating: list[dict], drop_uuids: set,
            old_sid: str, new_sid: str) -> list[dict]:
    kept = []
    for e in chain:
        if e.get("uuid") in drop_uuids:
            continue
        e = copy.deepcopy(e)
        if e.get("sessionId") == old_sid:
            e["sessionId"] = new_sid
        e["parentUuid"] = kept[-1].get("uuid") if kept else e.get("parentUuid")
        kept.append(e)
    out_floating = []
    for e in floating:
        e = copy.deepcopy(e)
        if e.get("sessionId") == old_sid:
            e["sessionId"] = new_sid
        out_floating.append(e)
    last_prompts = [e for e in out_floating if e.get("type") == "last-prompt"]
    for e in last_prompts[:-1]:
        out_floating.remove(e)
    return kept + out_floating


def validate(path: Path) -> list[str]:
    problems = []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    chain = [e for e in entries if e.get("uuid") and e.get("type") in CHAIN_TYPES]
    uuids = [e.get("uuid") for e in chain]
    if len(set(uuids)) != len(uuids):
        problems.append("duplicate uuid in chain")
    prev = None
    for e in chain:
        p = e.get("parentUuid")
        if prev is not None and p != prev:
            problems.append(f"chain break at {e.get('uuid')}: parentUuid={p}, expected {prev}")
        prev = e.get("uuid")
    sent: dict = {}
    recvd = set()
    for e in chain:
        for b in blocks(e) if isinstance(blocks(e), list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                sent[b.get("id")] = e.get("uuid")
            elif b.get("type") == "tool_result":
                if b.get("tool_use_id") not in sent:
                    problems.append(f"orphan tool_result {b.get('tool_use_id')}")
                recvd.add(b.get("tool_use_id"))
    dangling = [i for i in sent if i not in recvd]
    if dangling:
        tail_uuid = chain[-1].get("uuid") if chain else None
        bad = [sent[i] for i in dangling if sent[i] != tail_uuid]
        if bad:
            problems.append(f"unanswered tool_use mid-chain: {bad[:3]}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", type=Path)
    ap.add_argument("--model", default=os.environ.get("GLM_MODEL", "deepseek/deepseek-v4-flash"))
    ap.add_argument("--no-model", action="store_true", help="heuristic collapse only")
    ap.add_argument("--batch", type=int, default=120, help="ops per judge call")
    ap.add_argument("--thinking", choices=["auto", "on", "off"], default="auto",
                    help="glm models via 360 require thinking=enabled (default auto: on when "
                         "model name contains 'glm')")
    ap.add_argument("--budget-tokens", type=int, default=8192,
                    help="thinking budget_tokens (360 requires <=8192)")
    ap.add_argument("--context-budget", type=int, default=120000,
                    help="target max tokens for the distilled session (resume must fit)")
    ap.add_argument("--max-op-tokens", type=int, default=8000,
                    help="max tokens of original content shown per op in judge prompt")
    ap.add_argument("--judge-context-limit", type=int, default=0,
                    help="max input tokens for a single judge call (0=auto: 900k for glm, 100k otherwise)")
    ap.add_argument("--dry-run", action="store_true", help="no output file, stats only")
    args = ap.parse_args()

    src = args.session
    if not src.is_file():
        ap.error(f"not a file: {src}")

    chain, floating, bad = parse_session(src)
    if not chain:
        ap.error("no chain entries found")
    old_sid = chain[0].get("sessionId") or src.stem

    goal = ""
    for e in chain:
        if e.get("type") == "user":
            c = e.get("message", {}).get("content")
            if isinstance(c, str):
                goal = " ".join(c.split())[:500]
            elif isinstance(c, list):
                goal = " ".join(" ".join(b.get("text", "").split()) for b in c
                                if isinstance(b, dict) and b.get("type") == "text")[:500]
            if goal:
                break

    ops = build_ops(chain, find_sidechain_parents(chain))
    heuristic_collapse(ops)
    heur_dropped = sum(1 for o in ops if o.verdict == "drop")
    orig_tokens = estimate_tokens(chain)

    thinking = (args.thinking == "on"
                or (args.thinking == "auto" and "glm" in args.model.lower()))
    notes: list[str] = []
    if not args.no_model and ops:
        base = (os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("GLM_BASE_URL")
                or "https://api.360.cn").rstrip("/")
        url = base if base.endswith("/messages") else base + "/v1/messages"
        key = (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("GLM_API_KEY") or "")
        if not key:
            ap.error("no API key: set ANTHROPIC_AUTH_TOKEN or GLM_API_KEY (or use --no-model)")
        if thinking:
            print(f"thinking enabled (budget_tokens={args.budget_tokens}) for {args.model}",
                  file=sys.stderr)
        judge_limit = args.judge_context_limit
        if judge_limit == 0:
            judge_limit = 900000 if "glm" in args.model.lower() else 100000
        print(f"judging {len(ops) - heur_dropped} ops with {args.model} "
              f"(full content, max {args.max_op_tokens}tok/op) ...", file=sys.stderr)
        judge_ops(ops, goal, url, key, args.model, args.batch, notes,
                  thinking, args.budget_tokens, orig_tokens, args.context_budget,
                  args.max_op_tokens, judge_limit)

    protect = {e.get("uuid") for e in chain[:DROP_SAFE_LAST] + chain[-DROP_SAFE_LAST:]}
    drop_uuids = set()
    for op in ops:
        op.summary = " ;; ".join(summarize_input(t) for t in op.tool_uses)
        if op.verdict == "drop":
            if op.uuid in protect or op.u.get("uuid") in protect:
                continue
            drop_uuids.add(op.uuid)
            drop_uuids.add(op.u.get("uuid"))

    new_sid = str(uuid.uuid4())
    out_entries = rewrite(chain, floating, drop_uuids, old_sid, new_sid)

    total = len(chain)
    dropped = len(drop_uuids)
    pct = 100.0 * dropped / total if total else 0.0
    kept_chain = [e for e in out_entries if e.get("type") in CHAIN_TYPES]
    distilled_tokens = estimate_tokens(kept_chain)
    print(f"\nsource:        {src}")
    print(f"entries:       {total} chain (+{len(floating)} floating, {bad} bad lines)")
    print(f"ops analyzed:  {len(ops)}  (heuristic drop {heur_dropped})")
    print(f"dropped:       {dropped} entries ({pct:.1f}%)")
    print(f"est. tokens:   ~{orig_tokens} -> ~{distilled_tokens}  "
          f"(budget {args.context_budget})", end="")
    if distilled_tokens > args.context_budget:
        print(f"  *** OVER by ~{distilled_tokens - args.context_budget} ***")
    else:
        print(f"  fits")
    print(f"new session:   {new_sid}")

    if args.dry_run:
        for line in notes:
            print(f"\n[judge notes] {line}")
        return

    out_path = src.parent / f"{new_sid}.jsonl"
    if out_path.resolve() == src.resolve():
        ap.error("refusing to overwrite the source session file")
    out_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                for e in out_entries), encoding="utf-8")

    problems = validate(out_path)
    if problems:
        print("VALIDATION PROBLEMS:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    report = {
        "source": str(src),
        "new_session_id": new_sid,
        "created": datetime.now(timezone.utc).isoformat(),
        "model": None if args.no_model else args.model,
        "stats": {"chain_entries": total, "dropped": dropped, "ops": len(ops),
                  "heuristic_dropped": heur_dropped,
                  "orig_tokens": orig_tokens, "distilled_tokens": distilled_tokens,
                  "context_budget": args.context_budget,
                  "over_budget": distilled_tokens > args.context_budget},
        "judge_notes": notes,
        "drops": [{"no": o.no, "reason": o.reason, "summary": o.summary}
                  for o in ops if o.verdict == "drop"],
    }
    report_path = src.parent / f"{new_sid}.distill_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nwrote:         {out_path}")
    print(f"report:        {report_path}")
    print(f"\nresume with:   cp {out_path.name} <config>/projects/-workspace/ && "
          f"cd /workspace && claude-code.sh -r {new_sid}")


if __name__ == "__main__":
    main()
