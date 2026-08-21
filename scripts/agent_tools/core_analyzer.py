#!/usr/bin/env python3
"""core_analyzer.py — ptrace 被禁时的离线调试。

收集 core dump,用 gdb 批处理提取关键信息(读 core 不需要 ptrace):
崩溃指令、寄存器、栈回溯、堆顶、memcpy/strcpy 参数。
省掉手动 gdb 重复劳动(上一轮有题花 50+ 步手动 gdb)。

用法(容器内):
    python3 /workspace/tools/core_analyzer.py /out/vuln /tmp/core.vuln.1234
    # 或自动找最新 core:
    python3 /workspace/tools/core_analyzer.py /out/vuln
"""
from __future__ import annotations
import glob, os, subprocess, sys, time

GDB = "/data/gdb/gdb"
if not os.path.isfile(GDB):
    for p in ["gdb", "gdb-multiarch"]:
        r = subprocess.run(["which", p], capture_output=True, text=True)
        if r.returncode == 0:
            GDB = r.stdout.strip()
            break

def find_core(binary: str) -> str | None:
    """自动找最新 core 文件(匹配 binary 名或 .core.*)。"""
    name = os.path.basename(binary)
    patterns = [
        f"core.{name}.*", f"core.*.{name}.*", "core.*", "/tmp/core*",
    ]
    best = None
    best_mtime = 0
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                m = os.path.getmtime(f)
                if m > best_mtime:
                    best, best_mtime = f, m
            except OSError:
                pass
    return best

def analyze(binary: str, core: str) -> str:
    """gdb 批处理提取崩溃现场。"""
    cmds = "; ".join([
        "set pagination off",
        "set print pretty on",
        "bt full",           # 栈回溯
        "info registers",    # 寄存器
        "x/i $pc",           # 崩溃指令
        "x/16gx $sp",        # 栈顶 16 个 qword
        "x/16gx $rdi",       # rdi 指向(many bugs: dest ptr)
        "x/16gx $rsi",       # rsi 指向(src ptr for memcpy)
        "info proc mappings",# 内存映射(看 libc/heap base,破 ASLR)
        "maintenance info sections",  # section bases
    ])
    r = subprocess.run(
        [GDB, "-q", "-batch", "-ex", cmds, binary, core],
        capture_output=True, text=True, timeout=60,
    )
    out = r.stdout + ("\n[gdb stderr]\n" + r.stderr if r.stderr.strip() else "")
    # 提取关键指针(破 ASLR)
    lines = []
    for line in out.splitlines():
        low = line.lower()
        if any(k in low for k in ["0x7f", "libc", "stack", "heap", "ld-", "ld.so", "/out/"]):
            lines.append(line)
    if lines:
        out += "\n\n===== 关键地址(破 ASLR 用) =====\n" + "\n".join(lines[:20])
    return out

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    binary = sys.argv[1]
    if not os.path.isfile(binary):
        print(f"binary 不存在: {binary}", file=sys.stderr); sys.exit(1)
    core = sys.argv[2] if len(sys.argv) > 2 else find_core(binary)
    if not core:
        print("找不到 core dump。先确保 coredump 开启:", file=sys.stderr)
        print("  ulimit -c unlimited; sysctl kernel.core_pattern=core.%e.%p.%t",
              file=sys.stderr)
        print("  (ASAN: ASAN_OPTIONS=disable_coredump=0:abort_on_error=1)", file=sys.stderr)
        sys.exit(1)
    print(f"[core_analyzer] binary={binary} core={core}")
    print(f"[core_analyzer] gdb={GDB}")
    if not os.path.isfile(GDB):
        print("gdb 不可用!装 gdb-multiarch 或把静态 gdb 放 /data/gdb/gdb", file=sys.stderr)
        sys.exit(1)
    result = analyze(binary, core)
    print(result)
    # 写文件供后续参考
    out_file = f"{core}.analysis.txt"
    with open(out_file, "w") as f:
        f.write(result)
    print(f"\n[core_analyzer] 分析写入 {out_file}")

if __name__ == "__main__":
    main()
