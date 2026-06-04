#!/usr/bin/env python3
"""Batch agent trajectory scorer.

Finds all task directories (containing result.json) under a root directory,
then runs a scorer agent (Claude Code or Codex) to analyze each trajectory and
produce scorer_result.json.

The scorer runs inside the task's **original target image** (the same image the
agent was evaluated against), so it has first-hand access to the target's
source code and build artifacts (e.g. ``/src/v8`` and ``/challenge`` for V8
tasks) to verify root-cause / target-vulnerability claims. The image is
resolved per task from its ``config.json`` via cybergym metadata.

The agent CLI itself is not baked into a fixed image — the statically-built
runtime under ``data/runtime`` (node + the claude/codex/gemini CLIs) is
bind-mounted at ``/data``, exactly like the main evaluation harness. This means
run_scorer must be able to import ``cybergym``; run it via ``uv run``.

Authentication defaults to API keys from environment variables:
  - Claude: ANTHROPIC_API_KEY
  - Codex: OPENAI_API_KEY
Use --use-credential to authenticate via credential files instead.

Usage:
    uv run agent_scorer/run_scorer.py /path/to/experiment/root \
        --scorer claude \
        --model claude-sonnet-4-6 \
        --output-dir out/scores

The scorer agent runs in a container started from the task image with:
    /scoring/task/   <- task trajectory (bind-mounted read-only, preprocessed)
    /scoring/output/ <- output directory (bind-mounted; scorer_result.json here)
    /data/           <- agent CLI runtime (bind-mounted from data/runtime)
    plus the target's own source/binaries already present in the image.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
PROMPT_FILE = SCRIPT_DIR / "prompt.md"
JUDGE_PROMPT_FILE = SCRIPT_DIR / "judge_prompt.md"
DEFAULT_RUNTIME_DIR = REPO_ROOT / "data" / "runtime"

CLAUDE_CODE_BIN = "/data/node/bin/claude-code.sh"
CODEX_BIN = "/data/node/bin/codex.sh"

CLAUDE_CREDENTIAL_PATH = Path.home() / ".claude" / ".credentials.json"
CODEX_CREDENTIAL_PATH = Path.home() / ".codex" / "auth.json"

# Smart-quote / dash characters → ASCII, so the scorer's `grep -F` evidence-quote
# validation matches what the model reproduces. Applied to a host-side copy of
# the trajectory before it is mounted into the container.
_UNICODE_REPLACEMENTS = [
    ("’", "'"),
    ("‘", "'"),
    ("“", '"'),
    ("”", '"'),
    ("–", "-"),
    ("—", "--"),
]


def resolve_task_image(task_dir: Path, override: str | None = None) -> str:
    """Resolve the original target image for a task from its config.json.

    Uses cybergym metadata (so the script must be run with ``cybergym``
    importable, e.g. via ``uv run``). ``override`` short-circuits resolution.
    """
    if override:
        return override

    cfg_path = task_dir / "config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no config.json in {task_dir}; cannot resolve image")
    cfg = json.loads(cfg_path.read_text())
    task_id = cfg.get("task_id", "")

    try:
        from cybergym.task.metadata import (
            KERNEL_TASK_METADATA,
            TASK_METADATA,
            V8_TASK_METADATA,
        )
    except ImportError as e:
        raise RuntimeError(
            "cybergym must be importable to resolve task images — run via "
            "`uv run agent_scorer/run_scorer.py ...` (or pass --task-image)."
        ) from e

    if task_id.startswith("v8:"):
        m = V8_TASK_METADATA.get(task_id)
        if m is None:
            raise KeyError(f"v8 task not in metadata: {task_id}")
        no_sandbox = bool(cfg.get("task_extra_kwargs", {}).get("no_sandbox"))
        img = (m.image_no_sandbox if no_sandbox else m.image) or m.image or m.image_no_sandbox
        if img is None:
            raise ValueError(f"v8 task {task_id} has no usable image")
        return img
    if task_id.startswith("kernel:"):
        m = KERNEL_TASK_METADATA.get(task_id)
        if m is None:
            raise KeyError(f"kernel task not in metadata: {task_id}")
        return m.image_name
    if task_id.startswith("user:"):
        m = TASK_METADATA.get(task_id)
        if m is None:
            raise KeyError(f"user task not in metadata: {task_id}")
        mode = cfg.get("image_mode", "exp.none")
        img = m.images.get(mode) or m.images.get("vul")
        if img is None:
            raise ValueError(f"user task {task_id} has no image for mode {mode!r}")
        return img
    raise ValueError(f"unrecognised task_id prefix: {task_id!r}")


def _prepare_task_copy(task_dir: Path, dest: Path) -> None:
    """Copy *task_dir* to *dest* and preprocess it for scoring.

    Done on the host so the container (an arbitrary task image) needs no python.
    Drops rendered logs and normalises smart quotes in log/jsonl files.
    """
    shutil.copytree(task_dir, dest, symlinks=True)
    for p in dest.rglob("*.rendered.log"):
        p.unlink(missing_ok=True)
    for p in dest.rglob("*"):
        if p.is_file() and p.suffix in (".log", ".jsonl"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            new = text
            for a, b in _UNICODE_REPLACEMENTS:
                new = new.replace(a, b)
            if new != text:
                p.write_text(new, encoding="utf-8")


def find_task_dirs(root: Path) -> list[Path]:
    """Find all directories containing result.json under root."""
    dirs = []
    for result_json in sorted(root.rglob("result.json")):
        task_dir = result_json.parent
        if (task_dir / "logs").is_dir():
            dirs.append(task_dir)
        else:
            logger.debug("Skipping %s (no logs/ directory)", task_dir)
    return dirs


def has_scorer_result(
    task_dir: Path, output_dir: Path, root_dir: Path | None = None
) -> bool:
    if root_dir:
        rel = str(task_dir.resolve().relative_to(root_dir.resolve()))
        flat_name = rel.replace("/", "__")
        return (output_dir / flat_name / "scorer_result.json").exists()
    return (output_dir / task_dir.name / "scorer_result.json").exists()


def _setup_credential_in_container(
    container_name: str, scorer: str, config_dir: str
) -> None:
    """Copy credential files into a running container, following the same
    pattern as cybergym.utils.container_credential_symlink.

    The real file is placed under /tmp/<uuid> and symlinked into
    config_dir so that copying config_dir out doesn't leak credentials.
    """
    tmp_path = f"/tmp/{uuid.uuid4()}"

    if scorer == "claude":
        cred_file = CLAUDE_CREDENTIAL_PATH
        if not cred_file.exists():
            raise FileNotFoundError(
                f"Claude credential file not found: {cred_file}\n"
                "Run 'claude' once on the host to authenticate."
            )
        subprocess.run(
            ["docker", "cp", str(cred_file), f"{container_name}:{tmp_path}"],
            check=True,
            capture_output=True,
        )
        link_path = f"{config_dir}/.credentials.json"
        subprocess.run(
            ["docker", "exec", container_name, "ln", "-sf", tmp_path, link_path],
            check=True,
            capture_output=True,
        )

    elif scorer == "codex":
        cred_file = CODEX_CREDENTIAL_PATH
        if not cred_file.exists():
            raise FileNotFoundError(
                f"Codex credential file not found: {cred_file}\n"
                "Run 'codex login' on the host to authenticate."
            )
        subprocess.run(
            ["docker", "cp", str(cred_file), f"{container_name}:{tmp_path}"],
            check=True,
            capture_output=True,
        )
        link_path = f"{config_dir}/auth.json"
        subprocess.run(
            ["docker", "exec", container_name, "ln", "-sf", tmp_path, link_path],
            check=True,
            capture_output=True,
        )


def build_agent_command(
    scorer: str, model: str, timeout: int, prompt_path: str, log_name: str
) -> str:
    if scorer == "claude":
        return (
            f"cat {prompt_path} | timeout {timeout} {CLAUDE_CODE_BIN} "
            f"--model {model} "
            "--verbose --output-format=stream-json "
            "--permission-mode=bypassPermissions "
            f"2>&1 | tee /scoring/output/{log_name}"
        )
    elif scorer == "codex":
        return (
            f"cat {prompt_path} | timeout {timeout} {CODEX_BIN} exec "
            f"--model {model} "
            "--dangerously-bypass-approvals-and-sandbox "
            "--skip-git-repo-check "
            "--json "
            f"2>&1 | tee /scoring/output/{log_name}"
        )
    else:
        raise ValueError(f"Unknown scorer: {scorer}")


def run_scorer_for_task(
    task_dir: Path,
    scorer: str,
    model: str,
    timeout: int,
    api_base_url: str | None,
    output_dir: Path,
    root_dir: Path | None = None,
    use_credential: bool = False,
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    task_image_override: str | None = None,
) -> dict:
    """Run the scorer agent for a single task directory, inside its task image."""
    task_id = task_dir.name
    container_name = f"scorer-{task_id}-{uuid.uuid4().hex[:8]}"
    config_dir = "/tmp/agent-config"
    home_dir = "/tmp/agent-home"

    try:
        task_image = resolve_task_image(task_dir, task_image_override)
    except Exception as e:
        logger.error("[%s] Could not resolve task image: %s", task_id, e)
        return {"task_id": task_id, "status": "error", "error": f"image: {e}"}

    with tempfile.TemporaryDirectory(prefix="scorer-") as tmp_root:
        tmp_root_path = Path(tmp_root)
        tmp_output_path = tmp_root_path / "output"
        tmp_output_path.mkdir()
        tmp_task_path = tmp_root_path / "task"
        # Host-side copy + preprocess (image may have no python).
        _prepare_task_copy(task_dir, tmp_task_path)

        scorer_command = build_agent_command(
            scorer, model, timeout, "/scoring/prompt.md", "scorer.log"
        )
        judge_command = build_agent_command(
            scorer, model, timeout, "/scoring/judge_prompt.md", "judge.log"
        )

        # Static node runtime is mounted at /data; keep its bin on PATH so the
        # CLIs (and any subprocesses) resolve `node`. HOME is set explicitly
        # since arbitrary task images may not define one.
        env_vars = {
            "PATH": "/data/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": home_dir,
        }
        if scorer == "claude":
            command = scorer_command
            env_vars["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            env_vars["CLAUDE_CONFIG_DIR"] = config_dir
            env_vars["API_TIMEOUT_MS"] = "3000000"
            env_vars["CLAUDE_CODE_MAX_RETRIES"] = "10"
            env_vars["IS_SANDBOX"] = "1"
            if api_base_url:
                env_vars["ANTHROPIC_BASE_URL"] = api_base_url
                env_vars["ANTHROPIC_MODEL"] = model
                env_vars["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model
                env_vars["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model
                env_vars["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model
                env_vars["CLAUDE_CODE_SUBAGENT_MODEL"] = model
        elif scorer == "codex":
            command = scorer_command
            env_vars["CODEX_HOME"] = config_dir
            if api_base_url:
                env_vars["OPENAI_BASE_URL"] = api_base_url
        else:
            raise ValueError(f"Unknown scorer: {scorer}")

        if not use_credential:
            if scorer == "claude":
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    raise RuntimeError(
                        "ANTHROPIC_API_KEY not found (use --use-credential for credential file)"
                    )
                env_vars["ANTHROPIC_API_KEY"] = api_key
            elif scorer == "codex":
                api_key = os.environ.get("OPENAI_API_KEY", "")
                if not api_key:
                    raise RuntimeError(
                        "OPENAI_API_KEY not found (use --use-credential for credential file)"
                    )
                codex_api_key = api_key

        env_flags = []
        for k, v in env_vars.items():
            env_flags.extend(["-e", f"{k}={v}"])

        docker_cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--entrypoint",
            "tail",
            "-v",
            f"{Path(runtime_dir).resolve()}:/data:ro",
            "-v",
            f"{tmp_task_path}:/scoring/task:ro",
            "-v",
            f"{tmp_output_path}:/scoring/output",
            "-v",
            f"{PROMPT_FILE.resolve()}:/scoring/prompt.md:ro",
            "-v",
            f"{JUDGE_PROMPT_FILE.resolve()}:/scoring/judge_prompt.md:ro",
            "-w",
            "/scoring",
            *env_flags,
            task_image,
            "-f",
            "/dev/null",
        ]

        logger.info(
            "[%s] Starting scorer (%s / %s) in %s", task_id, scorer, model, task_image
        )

        try:
            subprocess.run(docker_cmd, check=True, capture_output=True, text=True)

            # Best-effort working-dir setup. git/python need not exist in the
            # task image; failures are ignored.
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "sh",
                    "-c",
                    f"mkdir -p {config_dir} {home_dir}; "
                    "command -v git >/dev/null 2>&1 && git init -q /scoring 2>/dev/null; "
                    "true",
                ],
                check=True,
                capture_output=True,
            )

            if use_credential:
                _setup_credential_in_container(container_name, scorer, config_dir)
            elif scorer == "codex":
                auth_json = json.dumps({"OPENAI_API_KEY": codex_api_key})
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        container_name,
                        "bash",
                        "-c",
                        f"mkdir -p {config_dir} && cat > {config_dir}/auth.json",
                    ],
                    input=auth_json.encode(),
                    check=True,
                    capture_output=True,
                )

            result = subprocess.run(
                ["docker", "exec", container_name, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout + 60,
            )

            if (tmp_output_path / "scorer_result.json").exists():
                logger.info("[%s] Scorer done, running judge pass", task_id)
                subprocess.run(
                    ["docker", "exec", container_name, "bash", "-c", judge_command],
                    capture_output=True,
                    text=True,
                    timeout=timeout + 60,
                )

            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )

            if root_dir:
                rel = str(task_dir.resolve().relative_to(root_dir.resolve()))
                flat_name = rel.replace("/", "__")
                dest_dir = output_dir / flat_name
            else:
                dest_dir = output_dir / task_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            tmp_result = tmp_output_path / "scorer_result.json"
            if tmp_result.exists():
                result_data = json.loads(tmp_result.read_text())
                result_data["scorer_model"] = f"{model} ({scorer})"
                result_data["scorer_task_image"] = task_image
                (dest_dir / "scorer_result.json").write_text(
                    json.dumps(result_data, indent=2)
                )
                (dest_dir / "_task_dir.txt").write_text(str(task_dir.resolve()))
                for log_name in ("scorer.log", "judge.log"):
                    log_file = tmp_output_path / log_name
                    if log_file.exists():
                        shutil.copy2(log_file, dest_dir / log_name)
                logger.info("[%s] scorer_result.json written to %s", task_id, dest_dir)
                return {"task_id": task_id, "status": "success"}
            else:
                logger.warning("[%s] scorer_result.json not found after run", task_id)
                scorer_log = tmp_output_path / "scorer.log"
                if scorer_log.exists():
                    shutil.copy2(scorer_log, dest_dir / "scorer.log")
                return {
                    "task_id": task_id,
                    "status": "no_output",
                    "exit_code": result.returncode,
                    "stderr_tail": result.stderr[-500:] if result.stderr else "",
                }

        except subprocess.TimeoutExpired:
            logger.error("[%s] Scorer timed out", task_id)
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )
            return {"task_id": task_id, "status": "timeout"}
        except Exception as e:
            logger.error("[%s] Scorer failed: %s", task_id, e)
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )
            return {"task_id": task_id, "status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Batch agent trajectory scorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=None,
        help="Root directory containing task result directories",
    )
    parser.add_argument(
        "--scorer",
        choices=["claude", "codex"],
        default="claude",
        help="Which agent CLI to use as the scorer (default: claude)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Model to use for scoring (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent scorer containers (default: 4)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout per task in seconds (default: 600)",
    )
    parser.add_argument(
        "--api-base-url",
        default=None,
        help="Custom API base URL (optional)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-score tasks that already have scorer_result.json",
    )
    parser.add_argument(
        "--task-list",
        type=Path,
        default=None,
        help="File with explicit task directory paths (one per line), bypasses rglob scan",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write scorer results (flat layout: relative path joined with __)",
    )
    parser.add_argument(
        "--success-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only score tasks where result.json indicates success (score > 0)",
    )
    parser.add_argument(
        "--use-credential",
        action="store_true",
        help="Use credential files (~/.claude/.credentials.json / ~/.codex/auth.json) instead of API keys",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=DEFAULT_RUNTIME_DIR,
        help="Host dir with the static agent CLI runtime, mounted at /data "
        f"(default: {DEFAULT_RUNTIME_DIR})",
    )
    parser.add_argument(
        "--task-image",
        default=None,
        help="Override the per-task image (otherwise resolved from each task's "
        "config.json via cybergym metadata). Useful to score against a single image.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List task directories without running the scorer",
    )

    args = parser.parse_args()

    if not args.task_list and not args.root:
        parser.error("either root directory or --task-list is required")

    if args.root and not args.root.is_dir():
        logger.error("Root directory does not exist: %s", args.root)
        sys.exit(1)

    if args.task_list:
        task_dirs = [
            Path(line.strip())
            for line in args.task_list.read_text().splitlines()
            if line.strip()
        ]
        missing = [d for d in task_dirs if not (d / "result.json").exists()]
        if missing:
            for m in missing:
                logger.warning("Task dir missing result.json: %s", m)
            task_dirs = [d for d in task_dirs if (d / "result.json").exists()]
        logger.info(
            "Loaded %d task directories from %s", len(task_dirs), args.task_list
        )
    else:
        task_dirs = find_task_dirs(args.root)
        logger.info("Found %d task directories under %s", len(task_dirs), args.root)

    if args.success_only:
        before = len(task_dirs)
        success_dirs = []
        for d in task_dirs:
            try:
                r = json.loads((d / "result.json").read_text())
                if any(c.get("score", 0) > 0 for c in r.get("checks", [])):
                    success_dirs.append(d)
            except Exception:
                pass
        task_dirs = success_dirs
        logger.info("Filtered to %d successful tasks (from %d)", len(task_dirs), before)

    if not args.overwrite:
        before = len(task_dirs)
        task_dirs = [
            d for d in task_dirs if not has_scorer_result(d, args.output_dir, args.root)
        ]
        skipped = before - len(task_dirs)
        if skipped:
            logger.info(
                "Skipping %d already-scored tasks (use --overwrite to re-score)",
                skipped,
            )

    if not task_dirs:
        logger.info("No tasks to score.")
        return

    logger.info("Will score %d tasks with %d workers", len(task_dirs), args.workers)

    if args.dry_run:
        for d in task_dirs:
            print(d)
        return

    runtime_node = Path(args.runtime_dir) / "node" / "bin"
    if not runtime_node.is_dir():
        logger.error(
            "Agent CLI runtime not found at %s. Build it with "
            "scripts/setup/static_build_node_and_agents.sh, or pass --runtime-dir.",
            runtime_node,
        )
        sys.exit(1)

    if args.use_credential:
        if args.scorer == "claude" and not CLAUDE_CREDENTIAL_PATH.exists():
            logger.error(
                "Claude credential not found at %s. "
                "Run 'claude' to authenticate, or remove --use-credential to use ANTHROPIC_API_KEY.",
                CLAUDE_CREDENTIAL_PATH,
            )
            sys.exit(1)
        elif args.scorer == "codex" and not CODEX_CREDENTIAL_PATH.exists():
            logger.error(
                "Codex credential not found at %s. "
                "Run 'codex login' to authenticate, or remove --use-credential to use OPENAI_API_KEY.",
                CODEX_CREDENTIAL_PATH,
            )
            sys.exit(1)
    else:
        if args.scorer == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            logger.error("ANTHROPIC_API_KEY not set (or use --use-credential)")
            sys.exit(1)
        elif args.scorer == "codex" and not os.environ.get("OPENAI_API_KEY"):
            logger.error("OPENAI_API_KEY not set (or use --use-credential)")
            sys.exit(1)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_scorer_for_task,
                task_dir=d,
                scorer=args.scorer,
                model=args.model,
                timeout=args.timeout,
                api_base_url=args.api_base_url,
                output_dir=args.output_dir,
                root_dir=args.root,
                use_credential=args.use_credential,
                runtime_dir=args.runtime_dir,
                task_image_override=args.task_image,
            ): d
            for d in task_dirs
        }

        for future in as_completed(futures):
            task_dir = futures[future]
            try:
                result = future.result()
                results.append(result)
                status = result["status"]
                logger.info(
                    "[%s] Done: %s (%d/%d)",
                    result["task_id"],
                    status,
                    len(results),
                    len(task_dirs),
                )
            except Exception as e:
                logger.error("[%s] Unexpected error: %s", task_dir.name, e)
                results.append(
                    {
                        "task_id": task_dir.name,
                        "status": "error",
                        "error": str(e),
                    }
                )

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "success"),
        "no_output": sum(1 for r in results if r["status"] == "no_output"),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "error": sum(1 for r in results if r["status"] == "error"),
    }
    logger.info("Scoring complete: %s", json.dumps(summary))

    summary_dir = args.output_dir
    summary_path = summary_dir / "scorer_summary.json"
    summary["results"] = results
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Summary written to %s", summary_path)


if __name__ == "__main__":
    main()
