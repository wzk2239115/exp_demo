import json
import logging
import os
from pathlib import Path

from docker.models.containers import Container

import docker
from cybergym.evaluation.agents.claude_code import get_firewall_description
from cybergym.evaluation.agents.gemini_stream_renderer import render_stream
from cybergym.evaluation.types import AgentFnArguments
from cybergym.utils import container_credential_symlink, get_docker_client

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
GEMINI_BIN_PATH = "/data/node/bin/gemini-cli.sh"
DEFAULT_VERTEX_LOCATION = "global"


def _resolve_vertex_project(adc_file: Path) -> str | None:
    """Read quota_project_id from an ADC credentials file."""
    try:
        data = json.loads(adc_file.read_text())
        return data.get("quota_project_id") or data.get("project_id")
    except Exception:
        return None


NO_WEB_POLICY = """\
[[rule]]
toolName = ["google_web_search", "web_fetch"]
decision = "deny"
priority = 500
"""


def _write_no_web_policy_to_container(
    container: Container, gemini_cli_home: str
) -> None:
    policy_dir = f"{gemini_cli_home}/.gemini/policies"
    container.exec_run(
        [
            "bash",
            "-c",
            f"mkdir -p {policy_dir} && cat > {policy_dir}/no_web.toml << 'POLICY_EOF'\n{NO_WEB_POLICY}\nPOLICY_EOF",
        ]
    )
    logger.info("Wrote no-web policy to container: %s", f"{policy_dir}/no_web.toml")


def run_gemini_cli_with_container(args: AgentFnArguments) -> None:
    """Run Gemini CLI agent inside a container.

    Extra kwargs:
        - "gemini_model": Gemini model to use (default: gemini-3.1-pro-preview)
    """
    gemini_model = args.extra_kwargs.get("gemini_model", DEFAULT_GEMINI_MODEL)

    use_vertex = bool(args.credential_path)

    if not args.api_key and not use_vertex:
        logger.warning(
            "No api_key or credential_path provided; assuming credentials are mounted in container"
        )

    if not args.container_id:
        raise ValueError("container_id is required")

    logger.info(
        "Starting Gemini CLI agent: model=%s, timeout=%ds",
        gemini_model,
        args.agent_timeout_seconds,
    )

    client = get_docker_client()
    container = client.containers.get(args.container_id)

    container.exec_run(["mkdir", "-p", "/logs", "/pocs"])

    cred_link_path: str | None = None
    vertex_project: str | None = None
    vertex_location: str | None = None
    if use_vertex:
        resolved = Path(args.credential_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Credential file not found: {resolved}")
        cred_link_path = f"/logs/{resolved.name}"
        container_credential_symlink(
            args.container_id,
            host_file=resolved,
            link_path=cred_link_path,
        )
        logger.info("Symlinked ADC credential file in container: %s", cred_link_path)

        vertex_project = (
            args.extra_kwargs.get("vertex_project")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or _resolve_vertex_project(resolved)
        )
        vertex_location = (
            args.extra_kwargs.get("vertex_location")
            or os.environ.get("GOOGLE_CLOUD_LOCATION")
            or DEFAULT_VERTEX_LOCATION
        )
        if not vertex_project:
            raise ValueError(
                "Vertex AI project not resolved. Set via agent_extra_kwargs['vertex_project'], "
                "GOOGLE_CLOUD_PROJECT env var, or `gcloud auth application-default set-quota-project <id>`."
            )
        logger.info(
            "Vertex AI mode: project=%s location=%s", vertex_project, vertex_location
        )

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

    logger.info("Running Gemini CLI agent")
    gemini_command = (
        f"cat {prompt_path} | timeout {args.agent_timeout_seconds} "
        f"{GEMINI_BIN_PATH} "
        f"-p '' "
        f"--yolo "
        "--output-format stream-json "
        f"-m {gemini_model} "
        f"2>&1 | tee /logs/gemini.log"
    )

    env: dict[str, str | None] = {
        "GEMINI_SANDBOX": "false",
        "GEMINI_CLI_HOME": "/logs",
        # pty is not compatible with static node build: https://github.com/google-gemini/gemini-cli/issues/12878
        # use "child_process" to avoid crash on startup
        # since we only use headless mode, we don't need pty support
        "GEMINI_PTY_INFO": "child_process",
    }
    if use_vertex:
        env.update(
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "GOOGLE_CLOUD_PROJECT": vertex_project,
                "GOOGLE_CLOUD_LOCATION": vertex_location,
                "GOOGLE_APPLICATION_CREDENTIALS": cred_link_path,
            }
        )
    else:
        env.update(
            {
                "GEMINI_API_KEY": args.api_key,
                "GOOGLE_GEMINI_BASE_URL": args.api_base_url,
            }
        )
    if args.firewall_env:
        env.update(args.firewall_env)

    if args.disable_web_search:
        _write_no_web_policy_to_container(container, env["GEMINI_CLI_HOME"])

    env = {k: v for k, v in env.items() if v is not None}

    # Stream output and render to a human-readable log
    resp = client.api.exec_create(
        args.container_id,
        ["bash", "-c", gemini_command],
        stdout=True,
        stderr=True,
        environment=env,
        workdir="/workspace",
    )
    exec_output = client.api.exec_start(resp["Id"], stream=True, socket=False)

    rendered_log_dir = args.out_dir / "logs"
    rendered_log_dir.mkdir(parents=True, exist_ok=True)
    rendered_log_path = rendered_log_dir / "gemini.rendered.log"
    logger.info("Writing rendered Gemini stream to %s", rendered_log_path)

    with rendered_log_path.open("w", encoding="utf-8") as rendered_log:
        render_stream(
            inp=exec_output,
            out=rendered_log,
            on_chunk=lambda chunk: logger.debug(chunk.rstrip()),
        )

    exit_code = client.api.exec_inspect(resp["Id"])["ExitCode"]
    logger.info("Gemini CLI exit code: %d", exit_code)

    logger.info("Gemini CLI agent execution completed")
