#!/bin/bash
#
# All-in-one setup for data/ artifacts (steps 4-6 from docs/setup.md).
#
# Usage:
#   bash scripts/setup/setup_data.sh
#
# Must be run from the project root.

set -euo pipefail

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
GDB_URL="https://github.com/guyush1/gdb-static/releases/download/v17.1-static/gdb-static-full-x86_64.tar.gz"

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            echo "Usage: $(basename "$0")"
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
log()  { echo "==> $*"; }
skip() { echo "    (already exists, skipping)"; }

# Download a file if it doesn't already exist.
# Usage: fetch <url> <dest_dir>
fetch() {
    local url="$1" dest_dir="$2"
    local filename
    filename=$(basename "$url")
    if [[ -f "${dest_dir}/${filename}" ]]; then
        skip
    else
        wget -q --show-progress -P "$dest_dir" "$url"
    fi
}

# ─────────────────────────────────────────────
#  Static GDB
# ─────────────────────────────────────────────
log "Setting up GDB"
if [[ ! -d data/runtime/gdb ]]; then
    log "Downloading static GDB"
    fetch "$GDB_URL" data/runtime
    mkdir -p data/runtime/gdb
    tar xf data/runtime/gdb-static-full-x86_64.tar.gz -C data/runtime/gdb
else
    skip
fi

# ─────────────────────────────────────────────
#  Static socat & netcat
# ─────────────────────────────────────────────
log "Building static socat and netcat"
if [[ ! -f data/server/socat ]] || [[ ! -f data/runtime/nc ]]; then
    bash scripts/setup/static_build_socat_nc.sh
else
    skip
fi

# ─────────────────────────────────────────────
#  Node.js + agent CLIs
# ─────────────────────────────────────────────
log "Building Node.js and installing agent CLIs"
if [[ ! -f data/runtime/node/bin/node ]]; then
    (cd data/runtime && bash ../../scripts/setup/static_build_node_and_agents.sh \
        --prefix "$PWD/node" --all)
else
    skip
fi

echo ""
log "Setup complete"
