#!/bin/bash

set -euo pipefail

# ─────────────────────────────────────────────
#  Defaults
# ─────────────────────────────────────────────
NODE_VERSION="22.21.0"
DEFAULT_NODE_PREFIX=""   # empty → resolved to <src_dir>/build at build time

DEFAULT_CODEX_VERSION="0.120.0"
DEFAULT_GEMINI_CLI_VERSION="0.37.2"
DEFAULT_CLAUDE_CODE_VERSION="2.1.119"

DEFAULT_BUILDER_IMAGE="alpine:3.20"

INSTALL_CODEX=false
INSTALL_GEMINI_CLI=false
INSTALL_CLAUDE_CODE=false

SKIP_NODE_BUILD=false

BUILDER_IMAGE="$DEFAULT_BUILDER_IMAGE"

NODE_PREFIX="$DEFAULT_NODE_PREFIX"

CODEX_VERSION="$DEFAULT_CODEX_VERSION"
GEMINI_CLI_VERSION="$DEFAULT_GEMINI_CLI_VERSION"
CLAUDE_CODE_VERSION="$DEFAULT_CLAUDE_CODE_VERSION"

# ─────────────────────────────────────────────
#  Usage
# ─────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Build Node.js $NODE_VERSION from source and optionally install AI coding agents.

Node build:
  --prefix PATH               Installation prefix for Node.js
                              (default: <node-src-dir>/build)
  --builder-image IMAGE       Alpine-based base image used to compile Node.js
                              (default: $DEFAULT_BUILDER_IMAGE). Must have apk
                              available — the script installs build-base,
                              python3, wget, xz. Alpine (musl libc) avoids
                              glibc's NSS dependency so the resulting node
                              binary is truly static.
  --skip-node-build           Skip the Node.js build step; use an existing
                              installation at --prefix. Useful for reinstalling
                              or upgrading agents without recompiling Node.

Agents are installed on the host using the freshly built Node.js.

Agent selection (at least one required):
  --codex                     Install codex         (default version: $DEFAULT_CODEX_VERSION)
  --gemini-cli                Install gemini-cli    (default version: $DEFAULT_GEMINI_CLI_VERSION)
  --claude-code               Install claude-code   (default version: $DEFAULT_CLAUDE_CODE_VERSION)
  --all                       Install all three agents at their default versions

Version overrides (only take effect when the corresponding agent is selected):
  --codex-version VERSION         Override codex version         (default: $DEFAULT_CODEX_VERSION)
  --gemini-cli-version VERSION    Override gemini-cli version    (default: $DEFAULT_GEMINI_CLI_VERSION)
  --claude-code-version VERSION   Override claude-code version   (default: $DEFAULT_CLAUDE_CODE_VERSION)

Other:
  -h, --help                  Show this help message and exit

Examples:
  # Install all agents at default versions
  $(basename "$0") --all

  # Install only codex and claude-code
  $(basename "$0") --codex --claude-code

  # Install gemini-cli with a specific version
  $(basename "$0") --gemini-cli --gemini-cli-version 0.33.0

  # Install all agents, override codex version
  $(basename "$0") --all --codex-version 0.115.0

  # Install to a custom prefix
  $(basename "$0") --all --prefix /opt/node-agents

  # Reinstall all agents without rebuilding Node.js
  $(basename "$0") --all --prefix /opt/node-agents --skip-node-build

  # Upgrade codex only, reusing an existing Node build
  $(basename "$0") --codex --codex-version 0.121.0 --prefix /opt/node-agents --skip-node-build
EOF
    exit 0
}

# ─────────────────────────────────────────────
#  Argument parsing
# ─────────────────────────────────────────────
if [[ $# -eq 0 ]]; then
    echo "Error: no options specified." >&2
    echo "Run '$(basename "$0") --help' for usage." >&2
    exit 1
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            INSTALL_CODEX=true
            INSTALL_GEMINI_CLI=true
            INSTALL_CLAUDE_CODE=true
            shift
            ;;
        --prefix)
            [[ -z "${2:-}" ]] && { echo "Error: --prefix requires a value." >&2; exit 1; }
            NODE_PREFIX=$(realpath "$2")
            shift 2
            ;;
        --builder-image)
            [[ -z "${2:-}" ]] && { echo "Error: --builder-image requires a value." >&2; exit 1; }
            BUILDER_IMAGE="$2"
            shift 2
            ;;
        --codex)
            INSTALL_CODEX=true
            shift
            ;;
        --gemini-cli)
            INSTALL_GEMINI_CLI=true
            shift
            ;;
        --claude-code)
            INSTALL_CLAUDE_CODE=true
            shift
            ;;
        --codex-version)
            [[ -z "${2:-}" ]] && { echo "Error: --codex-version requires a value." >&2; exit 1; }
            CODEX_VERSION="$2"
            shift 2
            ;;
        --gemini-cli-version)
            [[ -z "${2:-}" ]] && { echo "Error: --gemini-cli-version requires a value." >&2; exit 1; }
            GEMINI_CLI_VERSION="$2"
            shift 2
            ;;
        --claude-code-version)
            [[ -z "${2:-}" ]] && { echo "Error: --claude-code-version requires a value." >&2; exit 1; }
            CLAUDE_CODE_VERSION="$2"
            shift 2
            ;;
        --skip-node-build)
            SKIP_NODE_BUILD=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: unknown option '$1'" >&2
            echo "Run '$(basename "$0") --help' for usage." >&2
            exit 1
            ;;
    esac
done

if ! $INSTALL_CODEX && ! $INSTALL_GEMINI_CLI && ! $INSTALL_CLAUDE_CODE; then
    echo "Error: no agents selected. Use --codex, --gemini-cli, --claude-code, or --all." >&2
    exit 1
fi

# ─────────────────────────────────────────────
#  Summary
# ─────────────────────────────────────────────
echo "=== Install plan ==="
if $SKIP_NODE_BUILD; then
    echo "  Node.js        : $NODE_VERSION (skipping build, using existing)"
else
    echo "  Node.js        : $NODE_VERSION (static build in $BUILDER_IMAGE)"
fi
echo "  Prefix         : ${NODE_PREFIX:-<node-src-dir>/build (default)}"
$INSTALL_CODEX       && echo "  codex          : $CODEX_VERSION"
$INSTALL_GEMINI_CLI  && echo "  gemini-cli     : $GEMINI_CLI_VERSION"
$INSTALL_CLAUDE_CODE && echo "  claude-code    : $CLAUDE_CODE_VERSION"
echo "===================="

# ─────────────────────────────────────────────
#  Build Node.js
# ─────────────────────────────────────────────
NODE_TARBALL="node-v${NODE_VERSION}.tar.gz"
NODE_SRC_DIR="node-v${NODE_VERSION}"
# NODE_MIRROR: 可覆盖的 node 源码镜像(国内网络)。
# 完整 URL 优先级: NODE_SRC_URL > ${NODE_MIRROR}/v${NODE_VERSION}/$NODE_TARBALL > 官方源
NODE_SRC_URL="${NODE_SRC_URL:-${NODE_MIRROR:+${NODE_MIRROR}/v${NODE_VERSION}/${NODE_TARBALL}}}"
NODE_SRC_URL="${NODE_SRC_URL:-https://nodejs.org/download/release/v${NODE_VERSION}/${NODE_TARBALL}}"

# Resolve default prefix (must be absolute for docker bind mount)
if [[ -z "$NODE_PREFIX" ]]; then
    NODE_PREFIX="$(pwd)/${NODE_SRC_DIR}/build"
fi
NODE_PREFIX=$(realpath -m "$NODE_PREFIX")
mkdir -p "$NODE_PREFIX"

build_node_in_docker() {
    if ! command -v docker > /dev/null; then
        echo "Error: docker not found. Install docker to continue." >&2
        exit 1
    fi

    local uid gid
    uid=$(id -u)
    gid=$(id -g)

    echo "--- Building Node.js in $BUILDER_IMAGE (uid=$uid gid=$gid) ---"
    docker run --rm \
        -v "$NODE_PREFIX:/output" \
        -e NODE_VERSION="$NODE_VERSION" \
        -e NODE_SRC_URL="$NODE_SRC_URL" \
        -e HOST_UID="$uid" \
        -e HOST_GID="$gid" \
        "$BUILDER_IMAGE" \
        sh -eu -c '
            apk add --no-cache build-base linux-headers python3 wget ca-certificates xz
            cd /tmp
            wget -q "$NODE_SRC_URL"
            tar xf "node-v${NODE_VERSION}.tar.gz"
            cd "node-v${NODE_VERSION}"
            ./configure --prefix /output --fully-static
            make -j"$(nproc)"
            make install
            # Hand the install tree back to the invoking user so subsequent
            # host-side steps (npm install, etc.) can write into it.
            chown -R "${HOST_UID}:${HOST_GID}" /output
        '
}

if $SKIP_NODE_BUILD; then
    if [[ ! -x "${NODE_PREFIX}/bin/node" ]]; then
        echo "Error: --skip-node-build set but no node binary found at ${NODE_PREFIX}/bin/node" >&2
        exit 1
    fi
    echo "--- Skipping Node.js build, using existing install at $NODE_PREFIX ---"
else
    build_node_in_docker
    echo "--- Node.js built at $NODE_PREFIX ---"
fi

# ─────────────────────────────────────────────
#  Installer helpers
# ─────────────────────────────────────────────

# Write a thin launcher script that routes 'node <bin>' calls through the
# local static node binary, avoiding any system PATH dependency.
#
# Usage: write_launcher <prefix> <script_name> <bin_name>
write_launcher() {
    local prefix="$1"
    local script_name="$2"
    local bin_name="$3"

    cat > "${prefix}/${script_name}" <<LAUNCHER
#!/bin/bash
SCRIPT_DIR=\$(readlink -f "\$(dirname "\${BASH_SOURCE[0]}")")
TARGET="\$SCRIPT_DIR/${bin_name}"

if [[ "\$TARGET" == *.js ]]; then
    exec "\$SCRIPT_DIR/node" "\$TARGET" "\$@"
elif [[ -x "\$TARGET" ]] && file "\$TARGET" 2>/dev/null | grep -q "ELF"; then
    exec "\$TARGET" "\$@"
else
    # Fallback: try to detect by content
    if head -c 4 "\$TARGET" 2>/dev/null | grep -q $'\x7fELF'; then
        exec "\$TARGET" "\$@"
    else
        exec "\$SCRIPT_DIR/node" "\$TARGET" "\$@"
    fi
fi
LAUNCHER

    chmod +x "${prefix}/${script_name}"
}

install_codex() {
    local prefix="$1"
    local version="$2"
    local bin_dir="${prefix}/bin"
    echo "--- Installing codex@${version} ---"
    pushd "$bin_dir" > /dev/null
    # Force npm global installs into the project prefix instead of any
    # user-level npm prefix (for example ~/.npm-global).
    NPM_CONFIG_PREFIX="$prefix" npm_config_prefix="$prefix" \
        ./node ./npm install -g --prefix "$prefix" "@openai/codex@${version}"
    write_launcher "$bin_dir" "codex.sh" "codex"
    echo "    Launcher: ${bin_dir}/codex.sh"
    popd > /dev/null
}

install_gemini_cli() {
    local prefix="$1"
    local version="$2"
    local bin_dir="${prefix}/bin"
    echo "--- Installing gemini-cli@${version} ---"
    pushd "$bin_dir" > /dev/null
    NPM_CONFIG_PREFIX="$prefix" npm_config_prefix="$prefix" \
        ./node ./npm install -g --prefix "$prefix" "@google/gemini-cli@${version}"
    write_launcher "$bin_dir" "gemini-cli.sh" "gemini"
    echo "    Launcher: ${bin_dir}/gemini-cli.sh"
    popd > /dev/null
}

install_claude_code() {
    local prefix="$1"
    local version="$2"
    local bin_dir="${prefix}/bin"
    echo "--- Installing claude-code@${version} ---"
    pushd "$bin_dir" > /dev/null
    NPM_CONFIG_PREFIX="$prefix" npm_config_prefix="$prefix" \
        ./node ./npm install -g --prefix "$prefix" "@anthropic-ai/claude-code@${version}"
    write_launcher "$bin_dir" "claude-code.sh" "claude"
    echo "    Launcher: ${bin_dir}/claude-code.sh"
    popd > /dev/null
}

# ─────────────────────────────────────────────
#  Install selected agents
# ─────────────────────────────────────────────
$INSTALL_CODEX       && install_codex       "$NODE_PREFIX" "$CODEX_VERSION"
$INSTALL_GEMINI_CLI  && install_gemini_cli  "$NODE_PREFIX" "$GEMINI_CLI_VERSION"
$INSTALL_CLAUDE_CODE && install_claude_code "$NODE_PREFIX" "$CLAUDE_CODE_VERSION"

echo ""
echo "=== Done ==="
