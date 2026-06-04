# Setup

All commands should be run from the project root unless noted otherwise.

## Validate your install

After running the steps below, check which artifacts are already in place:

```bash
bash scripts/setup/validate.sh
```

This verifies `gdb`, `socat`, `nc`, the static `node` runtime, and the
agent CLIs (Claude Code, Codex, Gemini CLI) by running each with
`--version`. Any missing or non-runnable tool is flagged so you know
which step below to re-run; a full pass means you can skip to
[docker_images.md](docker_images.md) and [eval.md](eval.md).

## Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Docker (with access to the task image registry)
- Dependencies for building (`gcc`, `make`, `wget`, etc.), or change to building in Docker
- Note: follow [docker_images.md](docker_images.md) to pull the necessary images before proceeding.

## 0. [Optional] Configure coredump pattern

Required for primitive analysis. Sets the core dump filename
format so each crash produces a uniquely named file.

```bash
sudo sysctl -w kernel.core_pattern=core.%e.%p.%t
sudo sysctl -w kernel.core_uses_pid=1
```

> These settings are not persistent across reboots. To make them permanent,
> add them to `/etc/sysctl.conf` or a file under `/etc/sysctl.d/`.

## 1. Install Python dependencies

```bash
uv sync

# use llm_proxy
uv sync --extra proxy

# For development (linting, pre-commit hooks)
uv sync --all-extras --all-groups
uv run pre-commit install
```

## 2. Download static GDB

Downloads a statically linked GDB binary and installs it into `data/runtime/gdb/`
(mounted into agent containers).

```bash
wget -P data/runtime/ \
    https://github.com/guyush1/gdb-static/releases/download/v17.1-static/gdb-static-full-x86_64.tar.gz
mkdir -p data/runtime/gdb
tar xf data/runtime/gdb-static-full-x86_64.tar.gz -C data/utils/gdb
```

## 3. Build static socat and netcat

Builds socat and netcat-openbsd with static linking using Docker Alpine.
Socat is placed in `data/server/` (for the server), netcat in `data/runtime/`
(mounted into agent containers).

```bash
bash scripts/setup/static_build_socat_nc.sh
```

## 4. Build Node.js and install agent CLIs

Builds Node.js from source with static linking, then installs the
agent CLI tools (codex, gemini-cli, claude-code) under `data/runtime/node/`.

The Node compile runs in a throwaway Alpine container. Alpine uses musl
libc, which avoids glibc's implicit NSS dependency and lets `--fully-static`
produce a truly standalone binary. The install tree is bind-mounted out
with the host user's uid/gid, and agents are installed on the host using
that freshly built Node.

```bash
cd data/runtime && bash ../../scripts/setup/static_build_node_and_agents.sh \
    --prefix "$PWD/node" --all && cd ../..
```

Override the builder image with `--builder-image IMAGE` (must be
Alpine-based — the script invokes `apk`). Full options:

```bash
bash scripts/setup/static_build_node_and_agents.sh --help
```

## All-in-one setup

An automated script is provided that runs steps 2-5:

```bash
bash scripts/setup/setup_data.sh
```

> Steps 1-3 (Python install, image pull, task validation) are not included
> because they depend on your task list and registry access.

We recommend running through the steps one by one for the first time, so
you can install any missing system dependencies (e.g. `gcc`, `make`,
`autoconf`) as they come up. Use the all-in-one script for subsequent
setups on machines you have already prepared.
