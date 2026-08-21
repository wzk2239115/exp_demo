#!/usr/bin/env python3
"""把单题的复盘 report 蒸馏成一份英文 CLAUDE.md,供该题下一轮 agent 自动加载。

输入是 ``scripts/analyze_logs.py --report`` 产出的 *_report.md(中文,含「有效做法/
弯路与无效循环/关键决策点/失败成功归因/可操作的改进建议」等结构化小节,带 step 证据)。
输出是一份精炼的英文 CLAUDE.md,只编码:
  - 已验证的侦察事实(结构体大小/slab 桶/bug 触发条件/可用工具)
  - 上一轮观察到的反模式(带可识别的失败信号 + 进程级替代动作)
  - 错过的信号(已拿到但没利用的东西)
  - 环境备注(VM 启动/rootfs 提取/nsjail/网络限制)

硬约束(违反即毁掉价值):
  1. 只输出英文;
  2. 不得泄露漏洞利用技术/获胜原语/flag 路径/任何指向解法的步骤;
  3. 不得出现 CVE 号/commit hash/外部 writeup URL(免得 agent 直接抄公开方案);
  4. 全程以「带失败信号的启发式」呈现,绝不写成必须执行的步骤,保住 agent 探索能力。

用法:
  python scripts/distill_claude_md.py flash_reports/kernel_kernelctf_CVE-2023-3776_lts_report.md
  python scripts/distill_claude_md.py flash_reports -j 8            # 批量并行,断点续跑
  python scripts/distill_claude_md.py flash_reports -j 8 --force    # 忽略已有产物全部重跑

环境变量(同 analyze_logs.py):
  ANTHROPIC_BASE_URL  API 端点(默认 https://api.360.cn/v1/messages 直连,或走槽位 proxy)
  ANTHROPIC_API_KEY   key(必填)
  ANALYZE_MODEL       模型名(默认 deepseek/deepseek-v4-flash)
  DISTILL_MAX_TOKENS  输出上限(默认 2048)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

STEM_RE = re.compile(r"^(?P<stem>.+)_report\.md$")

SYSTEM_PROMPT = (
    "You distill an after-action review of an LLM agent's attempt at a single CTF "
    "pwn challenge into a concise English CLAUDE.md memory file. The agent will load "
    "this file at the start of its NEXT attempt at the SAME task. Goal: let it start "
    "smarter without spoiling the solution or suppressing its own exploration."
)

USER_PROMPT_TEMPLATE = """Below is a Chinese markdown after-action report for the task `{stem}`.
It contains structured sections (有效做法 / 弯路与无效循环 / 关键决策点 / 失败成功归因 / \
可操作的改进建议) with step-number evidence.

Produce a single English CLAUDE.md for the NEXT agent on THIS task.

HARD CONSTRAINTS (violating any defeats the purpose):
1. Output ONLY English markdown. No Chinese, no code fences around the whole file, no preamble.
2. Do NOT reveal the exploit technique, the winning primitive, the flag path, or any step toward the solution. If the report describes a successful attack chain, OMIT it entirely.
3. Do NOT mention CVE numbers, commit hashes, or external writeup URLs / author names that would let the agent shortcut to a published solution.
4. Concise: <= 30 lines of body. No tables. No preamble like "Here is...". Just the markdown.
5. Frame everything as heuristics with the failure signal to recognize, never as mandatory steps. The agent must remain free to form its own hypotheses.

ENCODE ONLY THESE:
- **Verified recon facts** worth reusing: struct sizes & their slab buckets (only if the run verified them with pahole/debugger, not guesses), the bug's high-level trigger condition, kernel/build config flags that matter, which tools are present or missing in the container. These save rediscovery, they do NOT solve.
- **Anti-patterns observed**: things the previous run wasted many steps on. For each: one line, the recognizable failure signal, and a process-level alternative ("switch technique", "reformulate the query", "read the downloaded file before spawning another search"). Never prescribe a specific exploit technique.
- **Missed signals**: things the run already obtained but failed to act on (e.g., a downloaded file it never opened). Phrase as "if you find X, act on it before Y".
- **Environment notes**: VM boot quirks, rootfs extraction method that worked, nsjail constraints, network restrictions.

Close with EXACTLY this line (no changes):
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.

OUTPUT STRUCTURE (use exactly these headings, omit a heading if empty):
# Prior-run notes for {stem}
## Verified recon facts
- ...
## Anti-patterns to avoid
- **<failure signal>**: <process-level alternative>
## Missed signals
- ...
## Environment notes
- ...
> These are heuristics distilled from one prior attempt. Trust your own evidence over these notes.

=== REPORT START ===
{report}
=== REPORT END ===
"""


def llm_complete(prompt: str, *, system: str = "", max_tokens: int = 2048) -> str:
    """Call an Anthropic-protocol endpoint (360 native / proxy). Mirrors analyze_logs.py."""
    base = os.environ.get(
        "ANTHROPIC_BASE_URL", "https://api.360.cn/v1/messages"
    ).rstrip("/")
    if not base.endswith("/v1/messages"):
        base = (
            base.rstrip("/") + "/v1/messages" if "/v1/" not in base else base
        )
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY required (360 key for direct, cgym- slot key for proxy)"
        )
    model = os.environ.get("ANALYZE_MODEL", "deepseek/deepseek-v4-flash")

    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        # 360's always-thinking models (deepseek/glm) eat all max_tokens on thinking
        # blocks and emit no visible text unless thinking is disabled.
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    req = urllib.request.Request(
        base,
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": key,
            "authorization": f"Bearer {key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    parts = [
        block.get("text", "")
        for block in data.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(p for p in parts if p).strip()
    if not text:
        raise SystemExit(
            f"model returned no text (stop_reason={data.get('stop_reason')}, "
            f"blocks={[b.get('type') for b in data.get('content', [])]})"
        )
    return text


def distill_one(report_path: Path, out_path: Path, max_tokens: int) -> None:
    report = report_path.read_text(encoding="utf-8", errors="replace")
    prompt = USER_PROMPT_TEMPLATE.format(stem=report_path.name, report=report)
    text = llm_complete(prompt, system=SYSTEM_PROMPT, max_tokens=max_tokens)
    out_path.write_text(text.lstrip() + "\n", encoding="utf-8")


def iter_reports(target: Path) -> list[Path]:
    if target.is_dir():
        return sorted(target.glob("*_report.md"))
    if target.name.endswith("_report.md"):
        return [target]
    # Convenience: accept a bare stem (e.g. "kernel_kernelctf_CVE-2023-3776_lts")
    cand = target.with_name(target.name + "_report.md")
    if cand.is_file():
        return [cand]
    raise SystemExit(f"Not a report file or dir: {target}")


def out_path_for(report_path: Path, out_dir: Path) -> Path:
    m = STEM_RE.match(report_path.name)
    stem = m.group("stem") if m else report_path.stem
    return out_dir / f"{stem}.CLAUDE.md"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "target",
        type=Path,
        help="A *_report.md file, or a directory of them (batch mode).",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        metavar="DIR",
        help="Output dir (default: same as the report file). Batch mode: required if target is a dir, defaults to target.",
    )
    ap.add_argument(
        "-j",
        "--parallel",
        type=int,
        default=1,
        help="Batch concurrency (default 1).",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if <stem>.CLAUDE.md already exists.",
    )
    args = ap.parse_args()
    if not args.target.exists():
        ap.error(f"Path does not exist: {args.target}")

    reports = iter_reports(args.target)
    if not reports:
        ap.error(f"No *_report.md found under {args.target}")

    if args.target.is_dir():
        # Default to a sibling "<stem>_claude_md" dir so flash_reports/ stays clean
        # (flash_reports -> flash_claude_md). Override with --out-dir.
        default_out = args.target.parent / (
            args.target.name.removesuffix("_reports") + "_claude_md"
        )
        out_dir = args.out_dir or default_out
    else:
        out_dir = args.out_dir or args.target.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    max_tokens = int(os.environ.get("DISTILL_MAX_TOKENS", "2048"))
    jobs = [(r, out_path_for(r, out_dir)) for r in reports]

    if args.parallel <= 1:
        done = skipped = failed = 0
        for r, o in jobs:
            if o.exists() and not args.force:
                skipped += 1
                continue
            print(f"[distill] {r.name} -> {o.name}")
            try:
                distill_one(r, o, max_tokens)
                done += 1
            except Exception as e:
                failed += 1
                print(f"[distill] FAIL {r.name}: {e}", file=sys.stderr)
        print(f"[distill] done={done} skipped={skipped} failed={failed}")
        return

    # Parallel
    todo = [(r, o) for r, o in jobs if not o.exists() or args.force]
    skipped = len(jobs) - len(todo)
    done = failed = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(distill_one, r, o, max_tokens): (r, o) for r, o in todo}
        for fut in as_completed(futs):
            r, o = futs[fut]
            try:
                fut.result()
                done += 1
                print(f"[distill] ok  {o.name}")
            except Exception as e:
                failed += 1
                print(f"[distill] FAIL {r.name}: {e}", file=sys.stderr)
    print(f"[distill] done={done} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
