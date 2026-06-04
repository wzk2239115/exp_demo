#!/bin/bash
#
# Validate that the runtime artifacts produced by docs/setup.md are
# present and runnable: gdb, socat, nc, node, and the agent CLIs.
#
# Usage:
#   bash scripts/setup/validate.sh
#
# Run from the project root. Exits non-zero if any check fails.

set -u

PASS=0
FAIL=0

green() { printf "\033[32m%s\033[0m" "$1"; }
red()   { printf "\033[31m%s\033[0m" "$1"; }
dim()   { printf "\033[2m%s\033[0m" "$1"; }

# Run `cmd` and report PASS (printing the first line of its output) or
# FAIL. `label` is the leftmost column, `path` is the file we also check
# exists.
#   check <label> <path> <cmd...>
check() {
    local label="$1" path="$2"
    shift 2

    printf "  %-18s " "$label"

    if [[ ! -x "$path" ]]; then
        red "MISSING"
        printf "  "
        dim "$path"
        echo
        FAIL=$((FAIL + 1))
        return
    fi

    local out
    out=$("$@" 2>&1)
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        red "FAIL   "
        printf "  exit=%d  " "$rc"
        dim "$path"
        echo
        FAIL=$((FAIL + 1))
        return
    fi

    green "OK     "
    printf "  %s  " "$(echo "$out" | head -1 | cut -c1-80)"
    dim "($path)"
    echo
    PASS=$((PASS + 1))
}

echo "==> Container runtime (data/runtime/ — mounted into agent containers)"
check "gdb"               data/runtime/gdb/gdb                     data/runtime/gdb/gdb --version
check "nc"                data/runtime/nc                          data/runtime/nc -h
check "node"              data/runtime/node/bin/node               data/runtime/node/bin/node --version
check "claude-code"       data/runtime/node/bin/claude-code.sh     data/runtime/node/bin/claude-code.sh --version
check "codex"             data/runtime/node/bin/codex.sh           data/runtime/node/bin/codex.sh --version
check "gemini-cli"        data/runtime/node/bin/gemini-cli.sh      data/runtime/node/bin/gemini-cli.sh --version

echo
echo "==> Challenge server (data/server/)"
check "socat"             data/server/socat             data/server/socat -V

echo
if [[ $FAIL -eq 0 ]]; then
    green "All $PASS checks passed."
    echo
    exit 0
else
    red "$FAIL check(s) failed"
    printf ", %d passed. " "$PASS"
    echo "See docs/setup.md to rebuild the missing artifact(s)."
    exit 1
fi
