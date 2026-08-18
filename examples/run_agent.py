r"""
Run Codex, Claude Code, or Gemini evaluation against mixed kernelCTF, V8,
and user (cybergym binary exploitation) tasks.

The controller's per-deployment secrets must be exported first — the runner
derives task tokens and expected flags from them, so they have to match the
running controller (which logs them at startup; ``scripts/setup/pre_run.py``
prints the matching export lines)::

    export CYBERGYM_SERVER_SALT=...
    export CYBERGYM_SERVER_FLAG_SEED=...
    export CYBERGYM_SERVER_API_KEY=...

Usage:
    # Run all task sets from default files
    python examples/run_agent.py --agent claude

    # Run specific mixed tasks
    python examples/run_agent.py --agent codex \
        kernel:kernelctf/CVE-2024-1085_lts v8:cve-2020-6418-real \
        user:cybergym/arvo_1461

    # Read only one family from file
    python examples/run_agent.py --agent gemini --task-family kernel

    # Direct API keys
    OPENAI_API_KEY=... python examples/run_agent.py --agent codex --use-api-key
    ANTHROPIC_API_KEY=... python examples/run_agent.py --agent claude --use-api-key
    GEMINI_API_KEY=... python examples/run_agent.py --agent gemini --use-api-key

User (cybergym) tasks are always run with the EXEC target.
"""

import argparse
import functools
import logging
import logging.handlers
import multiprocessing
import os
import random
import shutil
import signal
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr
from tqdm import tqdm

from cybergym.evaluation.agents.claude_code import ClaudeCodeAgent
from cybergym.evaluation.agents.codex import CodexAgent
from cybergym.evaluation.agents.gemini_cli import GeminiCliAgent
from cybergym.evaluation.kernel import KernelEvaluator
from cybergym.evaluation.types import EvalConfig
from cybergym.evaluation.user import UserEvaluator
from cybergym.evaluation.v8 import V8Evaluator
from cybergym.server.types import (
    API_KEY_ENV_VAR,
    FLAG_SEED_ENV_VAR,
    SALT_ENV_VAR,
)
from cybergym.task.metadata import V8_TASK_METADATA
from cybergym.task.workspace.registry import TaskType
from cybergym.utils import PROJECT_ROOT, APIKeyManager, LiteLLMAPIKeyManager

global_terminate_flag = multiprocessing.Value("i", 0)

# Per-worker flag: True only while the worker is executing a task. The SIGINT
# handler (installed in workers) uses this to decide whether to raise
# KeyboardInterrupt. If the worker is idle (blocked in call_queue.get()), we
# must NOT raise — dying there orphans the queue's POSIX reader lock and
# deadlocks the pool. While busy, raising is desirable so the task's finally
# blocks (container cleanup, etc.) run.
_worker_task_active = False


def _worker_sigint_handler(signum, frame):
    if _worker_task_active:
        raise KeyboardInterrupt


def _main_sigterm_handler(signum, frame):
    # Treat SIGTERM like Ctrl+C so `run_as.sh --stop` gets the same graceful
    # shutdown path (terminate flag + executor shutdown) instead of a hard kill.
    raise KeyboardInterrupt


def _mark_task_active(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _worker_task_active
        _worker_task_active = True
        try:
            return fn(*args, **kwargs)
        finally:
            _worker_task_active = False

    return wrapper


LOG_FORMAT = (
    "%(asctime)s [%(name)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
)
SCRIPT_LOGGER_NAME = "run_agent"
logger = logging.getLogger(SCRIPT_LOGGER_NAME)

type AgentName = str
type TaskFamily = str

AGENT_API_ENV_VARS: dict[AgentName, str] = {
    "codex": "OPENAI_API_KEY",
    "claude_code": "ANTHROPIC_API_KEY",
    "gemini_cli": "GEMINI_API_KEY",
}
AGENT_DEFAULT_MODELS: dict[AgentName, str] = {
    "codex": "gpt-5.3-codex",
    "claude_code": "claude-sonnet-4-6",
    "gemini_cli": "gemini-3.1-pro-preview",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Codex, Claude Code, or Gemini on mixed kernelCTF, V8, and user tasks",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--agent",
        required=True,
        choices=sorted(AGENT_DEFAULT_MODELS),
        help="Agent backend to run",
    )

    task_selection = parser.add_argument_group("task selection")
    task_selection.add_argument(
        "task_ids",
        nargs="*",
        metavar="TASK_ID",
        help="Task IDs to run. Can mix kernel:*, v8:*, and user:*.",
    )
    task_selection.add_argument(
        "--task-family",
        choices=["all", "kernel", "v8", "user"],
        default="all",
        help="Which task IDs to select from the shared task file when TASK_IDs are omitted",
    )
    task_selection.add_argument(
        "--tasks-file",
        type=Path,
        help="Shared task file with kernel:*, v8:*, and/or user:* entries",
    )
    task_selection.add_argument(
        "--shuffle-tasks",
        action="store_true",
        help="Randomize task order (after filtering by --task-family, before pre-flight checks)",
    )
    task_selection.add_argument(
        "--first-n",
        type=int,
        default=None,
        help="Only run the first N tasks after filtering and shuffling (for quick tests)",
    )

    user_group = parser.add_argument_group("user (cybergym) tasks")
    user_group.add_argument(
        "--user-mode",
        choices=["exp.none", "exp.canary", "exp.pie", "exp.relro", "exp.hardened"],
        default="exp.none",
        help="Image mode for user tasks (e.g. exp.none, exp.canary, exp.pie, exp.relro, exp.hardened)",
    )

    v8_group = parser.add_argument_group("v8 tasks")
    v8_group.add_argument(
        "--v8-mode",
        choices=["sandbox", "strict", "nosandbox", "nodefense"],
        default="nodefense",
        help=(
            "Which V8 build to evaluate against. "
            "'sandbox' = main image (sandbox enabled); skips pre-sandbox "
            "tasks that have no main image. "
            "'strict' = prefer main (sandbox-enabled) image, fall back to "
            "nosandbox image when no main image exists; never skips a v8 "
            "task that has any image. "
            "'nosandbox' = sandbox-disabled image; skips sandbox-escape "
            "tasks that have no nosandbox image. "
            "'nodefense' = prefer nosandbox if available, fall back to "
            "main; never skips a v8 task that has any image."
        ),
    )

    kernel_group = parser.add_argument_group("kernel tasks")

    def _kernel_defense_arg(spec: str) -> str:
        # Validate at parse time; resolver is called again per task.
        try:
            resolve_kernel_defense_caps(spec)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e)) from e
        return spec

    kernel_group.add_argument(
        "--kernel-defense",
        default="default",
        type=_kernel_defense_arg,
        metavar="SPEC",
        help=(
            "Kernel mitigation profile. Presets: "
            "'original' (use the CVE's original kernelctf capabilities), "
            "'strict' (bitmap=0; all defenses on, no attacker capabilities), "
            "'nodefense' (all defenses off + all attacker capabilities). "
            "Or a '+'-separated list of individual capability names: "
            "nokaslr, nosmep, nosmap, userns, io_uring, kernelctf_hardening "
            "(e.g. 'nokaslr+userns'). Use 'strict' for an explicit empty list."
        ),
    )

    parser.add_argument(
        "--controller-url",
        default="http://172.17.0.1:8666",
        help="Shared challenge controller URL",
    )

    parser.add_argument(
        "--model",
        default=None,
        help="Override the default model for the selected agent",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh", "max", "auto"],
        default="medium",
        help=(
            "Reasoning effort level. Applies to codex and claude_code; "
            "'max' and 'auto' are claude_code-only."
        ),
    )
    parser.add_argument(
        "--timeout", type=int, default=3600, help="Agent timeout (seconds)"
    )
    parser.add_argument("--max-workers", type=int, default=1, help="Parallel workers")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT / "out" / "run_agent",
        help="Output root",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove existing output before running",
    )
    parser.add_argument("--use-firewall", action="store_true")
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="Don't remove agent container after run",
    )

    auth = parser.add_argument_group("authentication")
    auth.add_argument(
        "--use-api-key",
        action="store_true",
        help="Use the selected agent's direct API key env var",
    )
    auth.add_argument(
        "--proxy-url",
        default=None,
        help="CyberGym proxy URL for budget tracking",
    )
    auth.add_argument(
        "--proxy-admin-key",
        default=None,
        help="Admin key for proxy budget endpoints (env: CYBERGYM_ADMIN_KEY)",
    )
    auth.add_argument(
        "--litellm-base-url",
        default=None,
        help="LiteLLM proxy URL. Or set LITELLM_BASE_URL.",
    )

    parser.add_argument(
        "--budget",
        type=float,
        default=20.0,
        help="Max budget per task (USD, with proxy or litellm)",
    )
    parser.add_argument(
        "--allowed-models",
        nargs="*",
        default=None,
        metavar="MODEL",
        help=(
            "Restrict each proxy/litellm key to these model names (others get "
            "HTTP 403). Only applies with --proxy-url / --litellm-base-url. "
            "Default: unrestricted. Pass '--allowed-models' with no value to "
            "scope keys to the run's --model. Include any auxiliary model the "
            "agent calls internally (e.g. a Gemini classifier model)."
        ),
    )
    parser.add_argument("--litellm-user-id", default=None)
    parser.add_argument("--litellm-team-id", default=None)

    args = parser.parse_args()

    if args.litellm_base_url is None:
        args.litellm_base_url = os.getenv("LITELLM_BASE_URL")
    if args.litellm_user_id is None:
        args.litellm_user_id = os.getenv("LITELLM_USER_ID")
    if args.litellm_team_id is None:
        args.litellm_team_id = os.getenv("LITELLM_TEAM_ID")

    if args.model is None:
        args.model = AGENT_DEFAULT_MODELS[args.agent]

    # `--allowed-models` with no values means "scope to the run's model".
    if args.allowed_models == []:
        args.allowed_models = [args.model]

    has_auth = (
        args.use_api_key
        or args.proxy_url
        or args.litellm_base_url
        or bool(os.environ.get(AGENT_API_ENV_VARS[args.agent]))
        or bool(os.environ.get("LITELLM_MASTER_KEY"))
    )
    if not has_auth:
        parser.error(
            "No auth configured. Use --use-api-key, "
            "--proxy-url, --litellm-base-url, or set the matching API key env var."
        )

    # The controller's token salt, flag seed, and API key are per-deployment
    # secrets with no hardcoded fallback — the evaluators must derive the same
    # tokens and flags as the controller. Reject here rather than once per task.
    missing_secrets = [
        var
        for var in (SALT_ENV_VAR, FLAG_SEED_ENV_VAR, API_KEY_ENV_VAR)
        if not os.environ.get(var)
    ]
    if missing_secrets:
        parser.error(
            f"Controller secrets not set: {', '.join(missing_secrets)}. They must "
            "match the running controller, which logs them at startup; "
            "scripts/setup/pre_run.py prints the matching export lines. "
            "See docs/eval.md."
        )

    return args


def setup_logging(
    out_root: Path,
) -> tuple[multiprocessing.Queue, logging.handlers.QueueListener]:
    out_root.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(LOG_FORMAT)
    handlers = [logging.StreamHandler(), logging.FileHandler(out_root / "run.log")]
    for handler in handlers:
        handler.setFormatter(fmt)

    log_queue = multiprocessing.Queue(-1)
    listener = logging.handlers.QueueListener(
        log_queue, *handlers, respect_handler_level=True
    )
    listener.start()

    root = logging.getLogger()
    root.handlers = [logging.handlers.QueueHandler(log_queue)]
    root.setLevel(logging.INFO)
    logging.getLogger("cybergym").setLevel(logging.INFO)

    return log_queue, listener


def _init_worker(log_queue: multiprocessing.Queue) -> None:
    signal.signal(signal.SIGINT, _worker_sigint_handler)
    # Same semantics for SIGTERM: interrupt the active task (its finally blocks
    # do container cleanup) but never raise while idle (would deadlock the pool).
    signal.signal(signal.SIGTERM, _worker_sigint_handler)

    qh = logging.handlers.QueueHandler(log_queue)
    qh.setLevel(logging.INFO)

    root = logging.getLogger()
    root.handlers = [qh]
    root.setLevel(logging.WARNING)
    logging.getLogger("cybergym").setLevel(logging.DEBUG)
    logging.getLogger(SCRIPT_LOGGER_NAME).setLevel(logging.INFO)


def build_key_manager(args: argparse.Namespace) -> APIKeyManager | None:
    if args.proxy_url:
        from cybergym.llm_proxy.manager import ProxyKeyManager

        admin_key = args.proxy_admin_key or os.environ.get("CYBERGYM_ADMIN_KEY")
        return ProxyKeyManager(
            proxy_url=args.proxy_url,
            default_max_budget=args.budget,
            admin_key=admin_key,
        )

    litellm_master_key = os.environ.get("LITELLM_MASTER_KEY")
    if args.litellm_base_url and litellm_master_key:
        return LiteLLMAPIKeyManager(
            litellm_base_url=args.litellm_base_url,
            litellm_master_key=litellm_master_key,
            litellm_user_id=args.litellm_user_id,
            litellm_team_id=args.litellm_team_id,
            default_max_budget=args.budget,
        )

    return None


ALL_KERNEL_DEFENSE_CAPS: list[str] = [
    "nokaslr",
    "nosmep",
    "nosmap",
    "userns",
    "io_uring",
    "kernelctf_hardening",
]


def resolve_kernel_defense_caps(spec: str) -> list[str] | None:
    """Translate --kernel-defense into a defense_capabilities list.

    Accepted forms:
        - 'original': returns None so KernelEvaluator falls back to the
          task's ``original_capabilities`` from metadata.
        - 'strict':   returns [] (all defenses on, no attacker capabilities).
        - 'nodefense': returns the full capability list.
        - '+'-separated list of capability names, e.g.
          'nokaslr+nosmep+userns'. Whitespace around tokens is stripped.
    """
    if spec == "original":
        return None
    if spec == "strict":
        return []
    if spec == "nodefense":
        return list(ALL_KERNEL_DEFENSE_CAPS)
    if spec == "default":
        return ["nokaslr", "userns"]

    caps = [c.strip() for c in spec.split("+") if c.strip()]
    if not caps:
        raise ValueError(
            f"--kernel-defense {spec!r} parsed to no capabilities; "
            f"use 'strict' to explicitly request the empty list"
        )
    unknown = [c for c in caps if c not in ALL_KERNEL_DEFENSE_CAPS]
    if unknown:
        raise ValueError(
            f"Unknown kernel capability/capabilities {unknown}; "
            f"valid: {ALL_KERNEL_DEFENSE_CAPS}"
        )
    # Deduplicate while preserving order
    seen: set[str] = set()
    return [c for c in caps if not (c in seen or seen.add(c))]


def resolve_v8_no_sandbox(meta, mode: str) -> bool | None:
    """Decide whether to use the nosandbox image for one v8 task.

    Returns True/False to pick image_no_sandbox/image, or None when the
    task should be skipped because the requested image isn't available.
    """
    if mode == "sandbox":
        return False if meta.image is not None else None
    if mode == "strict":
        if meta.image is not None:
            return False
        if meta.image_no_sandbox is not None:
            return True
        return None
    if mode == "nosandbox":
        return True if meta.image_no_sandbox is not None else None
    if mode == "nodefense":
        if meta.image_no_sandbox is not None:
            return True
        if meta.image is not None:
            return False
        return None
    raise ValueError(f"Unknown v8 mode: {mode!r}")


def infer_task_family(task_id: str) -> TaskFamily:
    if task_id.startswith("kernel:"):
        return "kernel"
    if task_id.startswith("v8:"):
        return "v8"
    if task_id.startswith("user:"):
        return "user"
    raise ValueError(f"Unsupported task id: {task_id}")


def build_agent_spec(args: argparse.Namespace) -> SimpleNamespace:
    if args.agent == "codex":
        return SimpleNamespace(
            agent=CodexAgent(),
            agent_extra_kwargs={
                "codex_model": args.model,
                "reasoning_effort": args.reasoning_effort,
            },
            direct_api_key_env="OPENAI_API_KEY",
        )
    if args.agent == "claude_code":
        return SimpleNamespace(
            agent=ClaudeCodeAgent(),
            agent_extra_kwargs={
                "claude_model": args.model,
                "reasoning_effort": args.reasoning_effort,
            },
            direct_api_key_env="ANTHROPIC_API_KEY",
        )
    if args.agent == "gemini_cli":
        return SimpleNamespace(
            agent=GeminiCliAgent(),
            agent_extra_kwargs={"gemini_model": args.model},
            direct_api_key_env="GEMINI_API_KEY",
        )
    raise ValueError(f"Unsupported agent: {args.agent}")


def resolve_task_ids(args: argparse.Namespace) -> list[str]:
    if args.task_ids:
        return args.task_ids

    if not args.tasks_file:
        raise ValueError("No tasks file specified")

    with args.tasks_file.open() as f:
        task_ids = [line.strip() for line in f if line.strip()]

    if args.task_family == "all":
        return task_ids
    return [
        task_id
        for task_id in task_ids
        if infer_task_family(task_id) == args.task_family
    ]


def compute_out_dir(out_root: Path, task_id: str) -> Path:
    family = infer_task_family(task_id)
    task_id_sanitized = task_id.replace(":", "_").replace("/", "_")
    return out_root / family / task_id_sanitized


@_mark_task_active
def run_one(
    task_id: str,
    out_dir: Path,
    args: argparse.Namespace,
    key_manager: APIKeyManager | None,
    stagger_time: int = 10,
) -> None:
    time.sleep(1)
    if global_terminate_flag.value == 1:
        logger.info("Terminate flag set, skipping %s", task_id)
        return
    time.sleep(random.randrange(1, stagger_time))

    out_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    task_fh = logging.FileHandler(out_dir / "task.log")
    task_fh.setLevel(logging.DEBUG)
    task_fh.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(task_fh)

    agent_spec = build_agent_spec(args)
    api_key: SecretStr | None = None
    if args.use_api_key:
        raw_api_key = os.environ.get(agent_spec.direct_api_key_env)
        api_key = SecretStr(raw_api_key) if raw_api_key else None
    elif not key_manager:
        raw_api_key = os.environ.get(agent_spec.direct_api_key_env)
        api_key = SecretStr(raw_api_key) if raw_api_key else None

    family = infer_task_family(task_id)

    try:
        if family == "kernel":
            kernel_extra: dict = {
                "controller_url": args.controller_url,
                "include_pov": True,
            }
            defense_caps = resolve_kernel_defense_caps(args.kernel_defense)
            if defense_caps is not None:
                kernel_extra["defense_capabilities"] = defense_caps
            evaluator = KernelEvaluator(
                config=EvalConfig(
                    task_id=task_id,
                    task_type=TaskType.KERNEL_EXPLOITATION,
                    out_dir=out_dir,
                    task_extra_kwargs=kernel_extra,
                    agent_extra_kwargs=agent_spec.agent_extra_kwargs,
                    agent_timeout_seconds=args.timeout,
                    api_key=api_key,
                    use_firewall=args.use_firewall,
                    keep_container=args.keep_container,
                    allowed_models=args.allowed_models,
                ),
                key_manager=key_manager,
            )
        elif family == "v8":
            v8_meta = V8_TASK_METADATA[task_id]
            no_sandbox = resolve_v8_no_sandbox(v8_meta, args.v8_mode)
            assert no_sandbox is not None, (
                f"v8 task {task_id} reached run_one with no usable image; "
                f"pre-flight should have skipped it"
            )
            evaluator = V8Evaluator(
                config=EvalConfig(
                    task_id=task_id,
                    task_type=TaskType.V8_EXPLOITATION,
                    out_dir=out_dir,
                    task_extra_kwargs={
                        "controller_url": args.controller_url,
                        "no_sandbox": no_sandbox,
                    },
                    agent_extra_kwargs=agent_spec.agent_extra_kwargs,
                    agent_timeout_seconds=args.timeout,
                    api_key=api_key,
                    use_firewall=args.use_firewall,
                    keep_container=args.keep_container,
                    allowed_models=args.allowed_models,
                ),
                key_manager=key_manager,
            )
        elif family == "user":
            evaluator = UserEvaluator(
                config=EvalConfig(
                    task_id=task_id,
                    task_type=TaskType.USER_EXPLOITATION,
                    image_mode=args.user_mode,
                    out_dir=out_dir,
                    task_extra_kwargs={
                        "controller_url": args.controller_url,
                        "target": "EXEC",
                    },
                    agent_extra_kwargs=agent_spec.agent_extra_kwargs,
                    agent_timeout_seconds=args.timeout,
                    api_key=api_key,
                    use_firewall=args.use_firewall,
                    keep_container=args.keep_container,
                    allowed_models=args.allowed_models,
                ),
                key_manager=key_manager,
            )
        else:
            raise ValueError(f"Unsupported task family: {family}")

        evaluator.evaluate(agent_spec.agent)
    except Exception as e:
        logger.exception("Evaluation for %s raised exception: %s", task_id, e)
    finally:
        root.removeHandler(task_fh)
        task_fh.close()


def main() -> None:
    args = parse_args()

    # SIGTERM -> graceful KeyboardInterrupt shutdown (used by run_as.sh --stop).
    signal.signal(signal.SIGTERM, _main_sigterm_handler)

    out_root = Path(args.out_dir)
    log_queue, listener = setup_logging(out_root)
    key_manager = build_key_manager(args)
    task_ids = resolve_task_ids(args)

    jobs: list[tuple[str, Path]] = []
    for task_id in task_ids:
        if infer_task_family(task_id) == "v8":
            meta = V8_TASK_METADATA.get(task_id)
            if meta is None:
                logger.warning("Unknown v8 task %s, skipping.", task_id)
                continue
            if resolve_v8_no_sandbox(meta, args.v8_mode) is None:
                logger.warning(
                    "V8 task %s (%s) has no image for --v8-mode=%s "
                    "(image=%r, image_no_sandbox=%r, is_sandbox_escape=%s); "
                    "skipping.",
                    task_id,
                    meta.entry_name,
                    args.v8_mode,
                    meta.image,
                    meta.image_no_sandbox,
                    meta.is_sandbox_escape,
                )
                continue
        out_dir = compute_out_dir(out_root, task_id)
        if (out_dir / "result.json").exists() and not args.overwrite:
            logger.info("Result for %s already exists, skipping.", task_id)
            continue
        if out_dir.exists() and args.overwrite:
            logger.info("Removing existing output for %s", task_id)
            shutil.rmtree(out_dir)
        jobs.append((task_id, out_dir))

    if args.shuffle_tasks:
        random.shuffle(jobs)

    if args.first_n is not None:
        jobs = jobs[: args.first_n]

    if not jobs:
        logger.info("No tasks to run after filtering; exiting.")
        return

    auth_mode = (
        "proxy"
        if args.proxy_url
        else "litellm"
        if key_manager and not args.proxy_url
        else "api-key"
        if args.use_api_key
        else "env"
    )
    logger.info(
        "Running %d tasks with %d workers, agent=%s, model=%s, budget=$%.2f, auth=%s",
        len(jobs),
        args.max_workers,
        args.agent,
        args.model,
        args.budget,
        auth_mode,
    )

    try:
        max_workers = min(args.max_workers, len(jobs))
        stagger_time = max(10, 5 * max_workers)
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=(log_queue,),
        ) as executor:
            try:
                futures = [
                    executor.submit(
                        run_one, task_id, out_dir, args, key_manager, stagger_time
                    )
                    for task_id, out_dir in jobs
                ]
                for future in tqdm(as_completed(futures), total=len(futures)):
                    future.result()
            except KeyboardInterrupt:
                global_terminate_flag.value = 1
                logger.warning("KeyboardInterrupt, shutting down...")
                try:
                    executor.shutdown(wait=True, cancel_futures=True)
                except Exception:
                    logger.exception("Error during executor shutdown")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
