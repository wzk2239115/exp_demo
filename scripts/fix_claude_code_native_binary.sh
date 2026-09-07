#!/usr/bin/env bash
# fix_claude_code_native_binary.sh
#
# 诊断并修复 ExploitGym 静态 Node（Alpine/musl 构建）下 claude-code 安装后
# bin/claude.exe 仍是占位 stub（约 500 字节，启动即崩，评测 0 分）的问题。
#
# 背景:
#   - claude-code 的 postinstall (install.cjs) 根据 process.report 判 libc,
#     静态 node 无 glibc 信息 -> 误判 linux-x64-musl;
#   - musl 平台包拉取失败时 postinstall 静默保留占位 stub 且退出码 0。
# 修复：把 optionalDependencies 里的 glibc 原生二进制
#   node_modules/@anthropic-ai/claude-code-linux-x64/claude
#   拷到 bin/claude.exe（host 与任务容器均为 glibc，可直接运行）。
#
# 用法：
#   bash scripts/fix_claude_code_native_binary.sh               # 诊断 + 按需修复（幂等）
#   bash scripts/fix_claude_code_native_binary.sh --skip-fix     # 只诊断
#   bash scripts/fix_claude_code_native_binary.sh --reproduce    # 复现 bug（重装）后自动修复
#
# 退出码：0 = 健康或已修复；1 = 损坏且无法自动修复（原生包缺失等）。

set -uo pipefail

PROJECT_ROOT="${EXPLOITGYM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NODE_PREFIX="$PROJECT_ROOT/data/runtime/node"
CLAUDE_DIR="$NODE_PREFIX/lib/node_modules/@anthropic-ai/claude-code"
CLAUDE_EXE="$CLAUDE_DIR/bin/claude.exe"
NATIVE_PKG_DIR="$CLAUDE_DIR/node_modules/@anthropic-ai/claude-code-linux-x64"
NATIVE_BIN="$NATIVE_PKG_DIR/claude"
LAUNCHER="$NODE_PREFIX/bin/claude-code.sh"
STUB_BACKUP="$CLAUDE_EXE.stub.bak"

MODE="fix"   # fix | skip-fix | reproduce
for arg in "$@"; do
  case "$arg" in
    --skip-fix)  MODE="skip-fix" ;;
    --reproduce) MODE="reproduce" ;;
    -h|--help)   sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "未知参数: $arg（--skip-fix / --reproduce）" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;32m[fix]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[fix]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[fix]\033[0m %s\n' "$*" >&2; exit 1; }

is_elf() { [ -f "$1" ] && [ "$(head -c 4 "$1" | od -An -tx1 | tr -d ' \n')" = "7f454c46" ]; }

detect_libc() {
  local node="$NODE_PREFIX/bin/node"
  [ -x "$node" ] || { echo "unknown (node 缺失)"; return; }
  "$node" -e 'const h = (process.report.getReport().header || {}); console.log(h.glibcVersionRuntime === undefined ? "musl/static（无 glibc 信息）" : "glibc " + h.glibcVersionRuntime)' 2>/dev/null \
    || echo "unknown (node 无法执行)"
}

diagnose() {
  echo "================ claude-code 健康诊断 ================"
  echo "项目根目录 : $PROJECT_ROOT"
  echo "node libc  : $(detect_libc)"
  if [ -f "$CLAUDE_EXE" ]; then
    local size; size=$(stat -c %s "$CLAUDE_EXE" 2>/dev/null || stat -f %z "$CLAUDE_EXE")
    if is_elf "$CLAUDE_EXE"; then
      echo "claude.exe : 原生 ELF，大小 ${size} 字节  ✅"
    else
      echo "claude.exe : 占位 stub，大小 ${size} 字节（<4KB 且非 ELF）  ❌"
    fi
  else
    echo "claude.exe : 不存在  ❌"
  fi
  [ -f "$NATIVE_BIN" ] && echo "glibc 原生 : $NATIVE_BIN（$(stat -c %s "$NATIVE_BIN" 2>/dev/null || stat -f %z "$NATIVE_BIN") 字节）" || echo "glibc 原生 : 缺失 ❌"
  echo "launcher   : $([ -x "$LAUNCHER" ] && echo "$LAUNCHER 存在" || echo "缺失 ❌")"
  echo "======================================================"
}

fix_once() {
  if is_elf "$CLAUDE_EXE"; then
    say "claude.exe 已是原生 ELF，无需修复。"
    return 0
  fi
  say "检测到占位 stub（或文件缺失），开始替换为 glibc 原生二进制…"
  [ -f "$NATIVE_BIN" ] || die "原生二进制不存在: $NATIVE_BIN（请先重装 claude-code 或检查网络）"
  is_elf "$NATIVE_BIN" || die "原生二进制本身不是 ELF: $NATIVE_BIN"

  if [ -f "$CLAUDE_EXE" ] && ! is_elf "$CLAUDE_EXE"; then
    cp -p "$CLAUDE_EXE" "$STUB_BACKUP" && say "占位 stub 已备份: $STUB_BACKUP"
  fi
  if cp "$NATIVE_BIN" "$CLAUDE_EXE" && chmod 755 "$CLAUDE_EXE"; then
    say "已复制 $NATIVE_BIN -> $CLAUDE_EXE"
  else
    warn "复制失败；尝试从备份恢复占位 stub…"
    [ -f "$STUB_BACKUP" ] && cp "$STUB_BACKUP" "$CLAUDE_EXE" 2>/dev/null || true
    die "修复失败"
  fi
}

verify() {
  echo "----------------------- 验证 -----------------------"
  if ! is_elf "$CLAUDE_EXE"; then
    warn "claude.exe 仍不是 ELF，修复未生效。"
    return 1
  fi
  if [ ! -x "$LAUNCHER" ]; then
    warn "launcher 缺失: $LAUNCHER（先跑 bash scripts/setup/setup_data.sh）"
    return 1
  fi
  local out rc
  out=$(timeout 60 "$LAUNCHER" --version 2>&1) && rc=0 || rc=$?
  if [ "$rc" -eq 0 ] && [ -n "$out" ]; then
    say "claude-code 可用 → $(printf '%s' "$out" | head -1 | cut -c1-80)"
    return 0
  fi
  warn "claude-code --version 失败 (exit=$rc):"
  printf '%s\n' "$out" | head -10 | sed 's/^/    /'
  return 1
}

reproduce() {
  local ver
  ver=$(grep -m1 '"version"' "$CLAUDE_DIR/package.json" | sed -E 's/.*"version"[^0-9]*([0-9.]+)".*/\1/' 2>/dev/null)
  [ -n "$ver" ] || ver="2.1.252"
  warn "---- 复现模式：重装 @anthropic-ai/claude-code@${ver}（需要 npmjs 网络）----"
  [ -x "$NODE_PREFIX/bin/node" ] && [ -x "$NODE_PREFIX/bin/npm" ] || die "静态 node/npm 不存在，无法复现"
  # 坑 1：npm lifecycle 脚本需要 node 在 PATH 上，否则 postinstall 报 127
  export PATH="$NODE_PREFIX/bin:$PATH"
  ( cd "$NODE_PREFIX/bin" && ./node ./npm install -g --prefix "$NODE_PREFIX" "@anthropic-ai/claude-code@${ver}" 2>&1 | tail -5 || true )
  summarize_reproduce
  echo
  say "复现完成，接下来执行修复…"
}

summarize_reproduce() {
  echo "---------------- 复现后的状态 ----------------"
  if [ -f "$CLAUDE_EXE" ] && ! is_elf "$CLAUDE_EXE"; then
    echo "✅ 已复现：bin/claude.exe 是 $(stat -c %s "$CLAUDE_EXE" 2>/dev/null || stat -f %z "$CLAUDE_EXE") 字节占位 stub"
    echo "   （这正是静默 0 分 bug 的现场：npm 退出码 0，但 claude-code 启动即崩）"
  elif is_elf "$CLAUDE_EXE"; then
    echo "ℹ️  重装后 claude.exe 仍是 ELF（npm 可能复用了旧文件或已成功落盘）"
  else
    echo "⚠️  claude.exe 缺失"
  fi
  echo "---------------------------------------------"
}

# ─────────────────────────── main ───────────────────────────
case "$MODE" in
  skip-fix)
    diagnose
    if is_elf "$CLAUDE_EXE"; then exit 0; else exit 1; fi
    ;;
  reproduce)
    diagnose
    reproduce
    fix_once
    verify && exit 0 || exit 1
    ;;
  fix)
    diagnose
    if is_elf "$CLAUDE_EXE"; then
      verify && exit 0 || exit 1
    fi
    fix_once
    verify && exit 0 || exit 1
    ;;
esac
