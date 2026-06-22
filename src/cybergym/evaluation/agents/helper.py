"""Shared helpers for agent runners.

Holds functionality common across the concrete agents (Claude Code, Codex,
Gemini CLI): the default install phase and intermediate-stats logging.
"""

import logging
import time
from pathlib import Path

from docker.models.containers import Container

from cybergym.evaluation.agents.base import Agent
from cybergym.task.workspace import TaskType
from cybergym.utils import APIKeyManager, save_json

logger = logging.getLogger(__name__)

# Log elapsed time / API-key usage roughly every this many seconds of agent run.
DEFAULT_STATS_INTERVAL_SECONDS = 1200.0


class IntermediateStatsLogger:
    """``on_chunk`` callback that periodically logs progress while an agent runs.

    Wraps the per-chunk debug logging the stream renderers expect, and on each
    crossing of *time_interval* seconds also logs how long the agent has been
    running and (when a key manager is available) fetches the current API-key
    usage, logging it and saving a ``usage_<elapsed>.json`` snapshot under
    *usage_dir*. This gives mid-run cost/progress visibility for long agents
    instead of only a final number.
    """

    def __init__(
        self,
        agent_name: str,
        log: logging.Logger = logger,
        api_key: str | None = None,
        key_manager: APIKeyManager | None = None,
        usage_dir: Path | None = None,
        time_interval: float = DEFAULT_STATS_INTERVAL_SECONDS,
    ) -> None:
        self.agent_name = agent_name
        self._log = log
        self.api_key = api_key
        self.key_manager = key_manager
        self.usage_dir = usage_dir
        self.time_interval = time_interval
        self.start_time = time.perf_counter()
        self.last_elapsed = 0.0

    def __call__(self, chunk: str) -> None:
        self._log.debug(chunk.rstrip())
        elapsed = time.perf_counter() - self.start_time
        # Fire once per time_interval window crossing.
        if elapsed // self.time_interval != self.last_elapsed // self.time_interval:
            self._log.info(
                "%s agent has been running for %.1f seconds", self.agent_name, elapsed
            )
            if self.key_manager and self.api_key:
                try:
                    usage = self.key_manager.get_api_key_usage(self.api_key)
                    self._log.info("API key usage: %s", usage)
                    if self.usage_dir is not None:
                        save_json(
                            usage,
                            self.usage_dir / f"usage_{int(elapsed)}.json",
                            indent=2,
                        )
                except Exception as e:
                    self._log.warning("Failed to fetch API key usage: %s", e)
        self.last_elapsed = elapsed


# Per-task-type install scripts, run in the container during the install phase
# (with network access via the install proxy) before the agent starts. A script
# that is empty or contains only comments is treated as "nothing to install":
# the install phase is skipped for that task type, so the install proxy is not
# required. To enable an install phase, add real commands to the script below.

KERNEL_INSTALL_SCRIPT = """\
set -euo pipefail

apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential bc bison flex \
    libssl-dev libelf-dev libncurses-dev dwarves openssl \
    cpio rsync xz-utils zstd lz4 \
    gdb gdbserver file strace \
    git curl ca-certificates python3 pkg-config \
    netcat-openbsd socat ripgrep jq unzip \
    libmnl-dev libnftnl-dev libnetfilter-queue-dev musl-tools \
    libkeyutils-dev libcap-dev liburing-dev libbpf-dev libbluetooth-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
"""

V8_INSTALL_SCRIPT = """\
set -euo pipefail

apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    netcat-openbsd ca-certificates unzip jq ripgrep socat curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
"""

USER_INSTALL_SCRIPT = """\
set -euo pipefail

apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    netcat-openbsd ca-certificates unzip jq socat curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
"""

INSTALL_SCRIPTS: dict[TaskType, str] = {
    TaskType.KERNEL_EXPLOITATION: KERNEL_INSTALL_SCRIPT,
    TaskType.V8_EXPLOITATION: V8_INSTALL_SCRIPT,
    TaskType.USER_EXPLOITATION: USER_INSTALL_SCRIPT,
}


def _script_has_commands(script: str | None) -> bool:
    """True if *script* has any non-blank, non-comment line."""
    if not script:
        return False
    return any(
        line.strip() and not line.strip().startswith("#")
        for line in script.splitlines()
    )


def task_needs_install(task_type: TaskType) -> bool:
    """Whether the default install phase does any work for *task_type*.

    True only when an install script with real commands is defined for the
    task type (see :data:`INSTALL_SCRIPTS`). Comment-only / empty scripts mean
    "nothing to install", so the phase — and the install proxy — are skipped.
    """
    return _script_has_commands(INSTALL_SCRIPTS.get(task_type))


def default_install(
    container: Container,
    *,
    env: dict[str, str] | None,
    task_id: str,
    task_type: TaskType,
) -> None:
    """Default install phase shared by the concrete agents.

    Runs the install script for *task_type* from :data:`INSTALL_SCRIPTS` (if it
    has real commands) with network access; otherwise a no-op.

    *env* carries the install-proxy environment variables; it is applied so the
    script can reach the network.
    """
    script = INSTALL_SCRIPTS.get(task_type)
    if not _script_has_commands(script):
        logger.info("No install phase for task %s (%s)", task_id, task_type)
        return

    logger.info("Running install script for task %s (%s)", task_id, task_type)
    res = container.exec_run(
        ["bash", "-c", script],
        environment=env or {},
    )
    output = res.output.decode(errors="replace") if res.output else ""
    if res.exit_code == 0:
        logger.info("Install script completed for task %s", task_id)
        logger.debug(output)
    else:
        logger.warning(
            "Install script failed (exit=%s) for task %s:\n%s",
            res.exit_code,
            task_id,
            output,
        )


class DefaultInstallAgent(Agent):
    """Agent base with the default, task-aware install phase wired in.

    Concrete agents inherit from this and implement :meth:`Agent.run`. The
    install phase engages only for task types whose :data:`INSTALL_SCRIPTS`
    entry has real commands (see :func:`task_needs_install`); override
    :meth:`install` / :meth:`has_install_phase` in a subclass for custom
    behavior.
    """

    def install(
        self,
        container: Container,
        *,
        env: dict[str, str] | None,
        task_id: str,
        task_type: TaskType,
    ) -> None:
        default_install(container, env=env, task_id=task_id, task_type=task_type)

    def has_install_phase(self, task_type: TaskType) -> bool:
        return task_needs_install(task_type)
