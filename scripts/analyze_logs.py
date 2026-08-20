#!/usr/bin/env python3
"""分析 claude_code.rendered.log:步数/工具分布/行为类型时间线,可选阶段级 API 摘要。

输入是 render_event_line 产出的渲染日志(src/cybergym/evaluation/agents/
claude_stream_renderer.py),格式规则:
  [init] ...
  [thinking] <一句话意图>
  [tool:Bash] <desc>
    $ <command>
  [tool-result] / [tool-error]
  后跟自由文本的结果体(属于上一个 tool-result 标记)

用法:
  python scripts/analyze_logs.py <log 文件>                 # 纯解析
  python scripts/analyze_logs.py <log 文件> --timeline 40   # 行为时间线(前40步)
  python scripts/analyze_logs.py <log 文件> --phases 8      # 聚成8个阶段
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────
#  解析
# ─────────────────────────────────────────────


@dataclass
class Step:
    idx: int
    thinking: str = ""
    tools: list[dict] = field(default_factory=list)  # {name, desc, command}
    results: int = 0
    errors: int = 0


def parse_rendered_log(path: str | Path) -> tuple[str, dict, list[Step]]:
    """返回 (model, init_info, steps)。步以 [thinking] 为界。"""
    model = "?"
    steps: list[Step] = []
    cur: Step | None = None
    pending_tool: dict | None = None

    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")

            if line.startswith("[init] "):
                m = re.match(r"\[init\] model=(\S+)", line)
                if m:
                    model = m.group(1)
            elif line.startswith("[thinking] "):
                cur = Step(idx=len(steps) + 1, thinking=line[len("[thinking] ") :])
                steps.append(cur)
                pending_tool = None
            elif line.startswith("[tool:") and "]" in line:
                name = line[len("[tool:") : line.index("]")]
                rest = line[line.index("]") + 2 :].strip()
                tool: dict = {"name": name, "desc": "", "command": ""}
                # rest 可能是 "desc"、"desc $ cmd" 或 "k=v k=v"(Read/Edit 等)
                if " $ " in rest:
                    d, c = rest.split(" $ ", 1)
                    tool["desc"], tool["command"] = d.strip(), c.strip()
                else:
                    tool["desc"] = rest
                if cur is None:  # 没出现过 thinking 的孤儿工具调用
                    cur = Step(idx=1)
                    steps.append(cur)
                cur.tools.append(tool)
                pending_tool = tool
            elif line.startswith("  $ ") or line.startswith("    "):
                # verbose 多行命令续行,归给最近的 tool
                if pending_tool is not None:
                    pending_tool["command"] = (
                        pending_tool["command"] + "\n" + line.strip()
                    )
            elif line.startswith("[tool-result]"):
                if cur is None:
                    cur = Step(idx=1)
                    steps.append(cur)
                cur.results += 1
                pending_tool = None
            elif line.startswith("[tool-error]"):
                if cur is None:
                    cur = Step(idx=1)
                    steps.append(cur)
                cur.errors += 1
                pending_tool = None
    return model, {}, steps


# ─────────────────────────────────────────────
#  行为类型分类(规则,零 API)
# ─────────────────────────────────────────────

RECON_SRC = re.compile(r"(/src/|\.(c|h|cpp|cc|hpp)([:,\s]|$)|grep\s|ripgrep|rg\s)")
RECON_BIN = re.compile(r"\b(file|checksec|objdump|readelf|nm |strings|ldd|otool)\b")
BUILD = re.compile(r"\b(gcc|clang|cc|g\+\+|make|ld |as )\b|(-o\s+\S+\.(so|out|bin|py)|\.so\b)")
DEBUG = re.compile(r"\b(gdb|core\.|coredump|asan|ASAN|ASAN_OPTIONS|strace|ltrace|valgrind|LD_[A-Z]+|/data/gdb)\b")
REMOTE = re.compile(r"\b(create_server|delete_server|health_check|restart_server|172\.17\.|socat|\bnc\b|netcat|socket\.|connect\(|/controller)")
RUN_LOCAL = re.compile(r"(\./[\w.-]+|python3? [\w./-]+\.(py|sh)|sh [\w./-]+\.sh|run\.sh|/out/[\w.-]+)")
WRITE_CODE = {"Write", "Edit"}
PLAN = {"TodoWrite"}


def classify_tool(tool: dict) -> str:
    name = tool["name"]
    text = f"{tool['desc']}\n{tool['command']}"
    if name in PLAN:
        return "PLAN"
    if name in WRITE_CODE:
        return "WRITE_CODE"
    if REMOTE.search(text):
        return "REMOTE_INTERACT"
    if DEBUG.search(text):
        return "DEBUG"
    if BUILD.search(text):
        return "BUILD"
    if RECON_BIN.search(text):
        return "RECON_BINARY"
    if RECON_SRC.search(text):
        return "RECON_SOURCE"
    if RUN_LOCAL.search(text):
        return "LOCAL_TEST"
    return "OTHER"


def step_action(step: Step) -> str:
    """一个 step 的行为类型:取该步所有工具里"最重"的类型(出现即按优先级)。"""
    if not step.tools:
        return "THINK_ONLY"
    priority = [
        "REMOTE_INTERACT",
        "EXPLOIT_ATTEMPT",
        "DEBUG",
        "BUILD",
        "WRITE_CODE",
        "LOCAL_TEST",
        "RECON_BINARY",
        "RECON_SOURCE",
        "PLAN",
        "OTHER",
    ]
    kinds = {classify_tool(t) for t in step.tools}
    for k in priority:
        if k in kinds:
            return k
    return "OTHER"


# exploit-attempt 判定:本地/远程出现命中信号
HIT = re.compile(r"(PWNED|FLAG\{|flag\{|catflag|root@|uid=0|# \$|#\$)")


def step_hit(step: Step) -> bool:
    return bool(HIT.search(step.thinking)) or any(
        HIT.search(t["desc"] + t["command"]) for t in step.tools
    )


# ─────────────────────────────────────────────
#  输出
# ─────────────────────────────────────────────


def report(path: Path, timeline_n: int | None, phases_n: int | None) -> None:
    model, _, steps = parse_rendered_log(path)
    n = len(steps)
    tool_calls = [t for s in steps for t in s.tools]
    tool_dist = Counter(t["name"] for t in tool_calls)
    kind_dist = Counter(step_action(s) for s in steps)
    hits = [s.idx for s in steps if step_hit(s)]

    print(f"== {path.name} ==")
    print(f"model={model}  steps={n}  tool_calls={len(tool_calls)}  "
          f"results={sum(s.results for s in steps)}  errors={sum(s.errors for s in steps)}")
    print(f"平均每步工具数: {len(tool_calls)/max(n,1):.2f}")
    print(f"\n工具分布: {dict(tool_dist.most_common())}")
    print(f"行为分布: {dict(kind_dist.most_common())}")
    if hits:
        print(f"命中信号步(PWNED/flag/root): {hits[:20]}{' …' if len(hits) > 20 else ''}")

    # 阶段切分:行为类型连续段合并,输出每段的起止/类型/代表动作
    print("\n== 行为时间线(连续同类型合并为段) ==")
    segments: list[tuple[int, int, str]] = []
    for s in steps:
        k = step_action(s)
        if k == "THINK_ONLY":  # 并入前段,避免碎片
            continue
        if segments and segments[-1][2] == k:
            segments[-1] = (segments[-1][0], s.idx, k)
        else:
            segments.append((s.idx, s.idx, k))
    for start, end, k in segments:
        width = end - start + 1
        print(f"  steps {start:>4}-{end:<4} ({width:>3}步) {k}")

    if timeline_n:
        print(f"\n== 前 {timeline_n} 步明细 ==")
        for s in steps[:timeline_n]:
            k = step_action(s)
            t0 = s.tools[0] if s.tools else None
            what = (t0["desc"] or t0["command"][:60]) if t0 else "(纯思考)"
            hit = " ★HIT" if step_hit(s) else ""
            print(f"  {s.idx:>4} [{k:<14}] {what[:76]}{hit}")

    if phases_n:
        print(f"\n== 压缩为 {phases_n} 个宏观阶段(按步均分,统计每段行为占比) ==")
        per = max(n // phases_n, 1)
        for i in range(0, n, per):
            chunk = steps[i : i + per]
            if not chunk:
                break
            kd = Counter(step_action(s) for s in chunk)
            top = ", ".join(f"{k}×{v}" for k, v in kd.most_common(3))
            hit_n = sum(1 for s in chunk if step_hit(s))
            print(f"  steps {chunk[0].idx:>4}-{chunk[-1].idx:<4}: {top}"
                  f"{' ★hit×%d' % hit_n if hit_n else ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log", type=Path)
    ap.add_argument("--timeline", type=int, metavar="N", help="打印前 N 步明细")
    ap.add_argument("--phases", type=int, metavar="N", help="聚合为 N 个宏观阶段")
    args = ap.parse_args()
    report(args.log, args.timeline, args.phases)


if __name__ == "__main__":
    main()
