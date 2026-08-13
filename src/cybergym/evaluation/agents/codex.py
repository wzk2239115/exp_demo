import logging
import os

from cybergym.evaluation.agents.codex_stream_renderer import render_stream
from cybergym.evaluation.agents.helper import (
    DefaultInstallAgent,
    IntermediateStatsLogger,
)
from cybergym.evaluation.types import AgentFnArguments
from cybergym.utils import container_credential_symlink, get_docker_client

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CODEX_MODEL = "gpt-5.3-codex"
DEFAULT_REASONING_EFFORT = "medium"
CODEX_BIN_PATH = "/data/node/bin/codex.sh"

# Disable websocket mode for litellm
# https://github.com/openai/codex/issues/13041#issuecomment-3981110494
HTTP_RESPONSES_CONFIG_TOML = """\
model_provider = "openai_http"

[model_providers.openai_http]
name = "OpenAI HTTP only"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
base_url = "{base_url}"
"""


def run_codex_with_container(args: AgentFnArguments) -> None:
    """Run Codex agent inside a container.

    Extra kwargs:
        - "codex_model": Codex model to use (default: gpt-5.3-codex)
        - "reasoning_effort": Codex reasoning effort level (default: medium)
    """
    codex_model = args.extra_kwargs.get("codex_model", DEFAULT_CODEX_MODEL)
    reasoning_effort = args.extra_kwargs.get(
        "reasoning_effort", DEFAULT_REASONING_EFFORT
    )

    if not args.api_key:
        logger.warning(
            "No api_key provided; assuming credentials are mounted in container"
        )

    if not args.container_id:
        raise ValueError("container_id is required")

    logger.info(
        "Starting Codex agent: model=%s, reasoning_effort=%s, timeout=%ds",
        codex_model,
        reasoning_effort,
        args.agent_timeout_seconds,
    )

    client = get_docker_client()
    container = client.containers.get(args.container_id)

    # Create directories for logs and POCs
    container.exec_run(["mkdir", "-p", "/logs", "/pocs"])

    prompt = args.task_description

    # Write prompt to container
    prompt_path = "/tmp/prompt.txt"
    container.exec_run(
        [
            "bash",
            "-c",
            f"cat > {prompt_path} << 'PROMPT_EOF'\n{prompt}\nPROMPT_EOF",
        ]
    )
    logger.debug("Wrote prompt to container")

    # Allow direct mode: bypass proxy and talk directly to the provider.
    # Set CODEX_DIRECT_BASE_URL when the provider's streaming doesn't work
    # through litellm's responses API handler (e.g. 360's gpt-5.6-sol).
    api_base_url = args.api_base_url or os.environ.get("CODEX_DIRECT_BASE_URL")

    # Update config
    if api_base_url:
        # codex sends to {base_url}/responses; litellm proxy handles /v1/responses
        base_url = args.api_base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        config_content = HTTP_RESPONSES_CONFIG_TOML.format(base_url=base_url)
        container.exec_run(
            [
                "bash",
                "-c",
                f"cat > /logs/config.toml << 'CONFIG_EOF'\n{config_content}\nCONFIG_EOF",
            ]
        )
        logger.debug("Updated Codex config for custom API base URL")

    # Configure authentication in container via symlink
    container_credential_symlink(
        args.container_id,
        content=f'{{\n"OPENAI_API_KEY": "{args.api_key}"\n}}',
        link_path="/logs/auth.json",
    )

    # Run Codex agent
    logger.info("Running Codex agent")
    extra_args = ""
    if args.disable_web_search:
        extra_args += ' -c web_search="disabled"'
    codex_command = f"""\
cat {prompt_path} | timeout {args.agent_timeout_seconds} {CODEX_BIN_PATH} exec \
    --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check \
    --model {codex_model} \
    --json \
    --enable unified_exec \
    -c model_reasoning_effort={reasoning_effort} \
    {extra_args} 2>&1 | tee /logs/codex.log"""

    env = {
        "CODEX_HOME": "/logs",
        "OPENAI_BASE_URL": api_base_url,
        "OPENAI_API_KEY": args.api_key,
    }
    if args.firewall_env:
        env.update(args.firewall_env)

    env = {k: v for k, v in env.items() if v is not None}

    # Use low-level API to stream output (for rendering) and capture exit code
    resp = client.api.exec_create(
        args.container_id,
        ["bash", "-c", codex_command],
        stdout=True,
        stderr=True,
        environment=env,
        workdir="/workspace",
    )
    exec_output = client.api.exec_start(resp["Id"], stream=True, socket=False)

    rendered_log_dir = args.out_dir / "logs"
    rendered_log_dir.mkdir(parents=True, exist_ok=True)
    rendered_log_path = rendered_log_dir / "codex.rendered.log"
    logger.info("Writing rendered Codex stream to %s", rendered_log_path)

    usage_dir = args.out_dir / "usage"
    if args.key_manager:
        usage_dir.mkdir(parents=True, exist_ok=True)
    on_chunk = IntermediateStatsLogger(
        agent_name="Codex",
        log=logger,
        api_key=args.api_key,
        key_manager=args.key_manager,
        usage_dir=usage_dir if args.key_manager else None,
    )

    with rendered_log_path.open("w", encoding="utf-8") as rendered_log:
        render_stream(
            inp=exec_output,
            out=rendered_log,
            on_chunk=on_chunk,
        )

    exit_code = client.api.exec_inspect(resp["Id"])["ExitCode"]
    logger.info("Codex exit code: %d", exit_code)

    container.exec_run(["rm", "-f", "/logs/auth.json"])

    logger.info("Codex agent execution completed")


class CodexAgent(DefaultInstallAgent):
    """Codex agent (uses the default, task-aware install phase)."""

    def run(self, args: AgentFnArguments) -> None:
        run_codex_with_container(args)
