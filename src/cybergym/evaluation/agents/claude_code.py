import logging
from pathlib import Path

import docker

from cybergym.evaluation.agents.claude_stream_renderer import render_stream
from cybergym.evaluation.types import AgentFnArguments
from cybergym.utils import container_credential_symlink, get_docker_client

logger = logging.getLogger(__name__)

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_CODE_BIN_PATH = "/data/node/bin/claude-code.sh"

VALID_EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max", "auto"}


def get_firewall_description(firewall_env: dict[str, str]) -> str:
    proxy_url = firewall_env.get("HTTPS_PROXY") or firewall_env.get("HTTP_PROXY")
    no_proxy = firewall_env.get("NO_PROXY") or firewall_env.get("no_proxy")

    if not proxy_url:
        raise ValueError(
            "Proxy URL not found in firewall_env (missing HTTPS_PROXY or HTTP_PROXY)"
        )

    lines = [
        "This container is on an internal Docker network with no direct internet route.",
        f"External HTTP/HTTPS traffic must go through the proxy at {proxy_url}.",
        "The allowlist is intended for routine package installation, such as PyPI and Ubuntu package repositories; other external domains and IPs are blocked.",
    ]
    if no_proxy:
        lines.append(
            f"`NO_PROXY` bypasses the proxy only for local addresses: {no_proxy}."
        )
    return "\n".join(f"- {line}" for line in lines)


def run_claude_code_with_container(args: AgentFnArguments) -> None:
    """Run Claude Code agent inside a container.

    Extra kwargs:
        - "claude_model": Claude model to use (default: claude-sonnet-4-6)
        - "reasoning_effort": one of "low", "medium", "high", "xhigh", "max",
          "auto". When set, exported to the container as
          ``CLAUDE_CODE_EFFORT_LEVEL``; unset means the CLI's own default.
    """
    claude_model = args.extra_kwargs.get("claude_model", DEFAULT_CLAUDE_MODEL)
    reasoning_effort = args.extra_kwargs.get("reasoning_effort")
    claude_code_bin = args.extra_kwargs.get("claude_code_bin", CLAUDE_CODE_BIN_PATH)
    if reasoning_effort is not None and reasoning_effort not in VALID_EFFORT_LEVELS:
        raise ValueError(
            f"Invalid reasoning_effort {reasoning_effort!r}; "
            f"expected one of {sorted(VALID_EFFORT_LEVELS)}"
        )

    if not args.api_key and not args.credential_path:
        raise ValueError("Either api_key or credential_path must be provided")

    if not args.container_id:
        raise ValueError("container_id is required")

    logger.info(
        "Starting Claude Code agent: model=%s, effort=%s, timeout=%ds",
        claude_model,
        reasoning_effort or "<cli default>",
        args.agent_timeout_seconds,
    )

    client = get_docker_client()
    container = client.containers.get(args.container_id)

    container.exec_run(["mkdir", "-p", "/logs", "/pocs"])

    cred_link_path: str | None = None
    if args.credential_path:
        resolved = Path(args.credential_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Credential file not found: {resolved}")
        cred_link_path = f"/logs/{resolved.name}"
        container_credential_symlink(
            args.container_id,
            host_file=resolved,
            link_path=cred_link_path,
        )
        logger.info("Symlinked credential file in container: %s", cred_link_path)

    prompt = args.task_description
    if args.firewall_env:
        prompt += f"\n\n---\n\nFirewall:\n{get_firewall_description(args.firewall_env)}"

    prompt_path = "/tmp/prompt.txt"
    container.exec_run(
        [
            "bash",
            "-c",
            f"cat > {prompt_path} << 'PROMPT_EOF'\n{prompt}\nPROMPT_EOF",
        ]
    )
    logger.debug("Wrote prompt to container")

    logger.info("Running Claude Code agent")
    extra_args = ""
    if args.disable_web_search:
        extra_args += "--disallowed-tools WebSearch,WebFetch"
    #  https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/claude_code.py
    claude_command = (
        f"cat {prompt_path} | timeout {args.agent_timeout_seconds} "
        f"{claude_code_bin} "
        "--verbose --output-format=stream-json "
        "--permission-mode=bypassPermissions "
        f"{extra_args} "
        f"2>&1 | tee /logs/claude_code.log"
    )
    env = {
        "ANTHROPIC_BASE_URL": args.api_base_url,
        "ANTHROPIC_API_KEY": args.api_key,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "ANTHROPIC_MODEL": claude_model,
        "IS_SANDBOX": "1",
        "CLAUDE_CONFIG_DIR": "/logs",
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_CODE_MAX_RETRIES": "10",
        "CLAUDE_CODE_EFFORT_LEVEL": reasoning_effort,
    }

    if args.firewall_env:
        env.update(args.firewall_env)

    env = {k: v for k, v in env.items() if v is not None}
    # When using custom base URL, set all model aliases to the same model
    if "ANTHROPIC_BASE_URL" in env and "ANTHROPIC_MODEL" in env:
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = env["ANTHROPIC_MODEL"]
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = env["ANTHROPIC_MODEL"]
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = env["ANTHROPIC_MODEL"]
        env["CLAUDE_CODE_SUBAGENT_MODEL"] = env["ANTHROPIC_MODEL"]

    # Use low-level API to stream output (for rendering) and capture exit code
    resp = client.api.exec_create(
        args.container_id,
        ["bash", "-c", claude_command],
        stdout=True,
        stderr=True,
        environment=env,
        workdir="/workspace",
    )
    exec_output = client.api.exec_start(resp["Id"], stream=True, socket=False)

    rendered_log_dir = args.out_dir / "logs"
    rendered_log_dir.mkdir(parents=True, exist_ok=True)
    rendered_log_path = rendered_log_dir / "claude_code.rendered.log"
    logger.info("Writing rendered Claude stream to %s", rendered_log_path)

    with rendered_log_path.open("w", encoding="utf-8") as rendered_log:
        render_stream(
            inp=exec_output,
            out=rendered_log,
            on_chunk=lambda chunk: logger.debug(chunk.rstrip()),
        )

    exit_code = client.api.exec_inspect(resp["Id"])["ExitCode"]
    logger.info("Claude Code exit code: %d", exit_code)

    if cred_link_path:
        container.exec_run(["rm", "-f", cred_link_path])

    logger.info("Claude Code agent execution completed")
