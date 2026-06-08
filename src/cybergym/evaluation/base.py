"""Base evaluator class."""

import logging
import re
import time
from pathlib import Path
from typing import Callable
from uuid import uuid4

import docker
from docker.models.containers import Container

from cybergym.evaluation.types import (
    AgentFnArguments,
    CheckResult,
    EvalConfig,
    EvalResult,
)
from cybergym.firewall import FirewallProxyManager
from cybergym.task.metadata import TASK_METADATA
from cybergym.task.workspace import prepare_workspace
from cybergym.utils import (
    APIKeyManager,
    check_system_config,
    docker_cp_from_container,
    docker_cp_to_container,
    get_docker_client,
    save_json,
)

logger = logging.getLogger(__name__)


def _container_name_part(value: str, max_len: int = 32) -> str:
    """Sanitize ``value`` for use in a Docker container name.

    Docker hostnames are capped at 63 chars; truncate long inputs (e.g.
    syzbot extids ~40 chars combined with long aliases) so the final
    ``cg-eval-<part>-<uuid8>`` stays well under the limit.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")
    sanitized = sanitized.lower() or "unknown"
    return sanitized[:max_len].rstrip("-") or "unknown"


def _container_name_suffix() -> str:
    return uuid4().hex[:8]


class Evaluator:
    """Base class for task evaluators.

    Subclasses must implement :meth:`_collect_outputs_impl` and
    :meth:`_verify_impl`.  Optionally override :meth:`_cleanup_impl`
    for custom teardown logic.

    The full pipeline is run by calling :meth:`evaluate`::

        evaluator = MyEvaluator(config)
        result = evaluator.evaluate(agent_fn)
    """

    def __init__(
        self,
        config: EvalConfig,
        key_manager: APIKeyManager | None = None,
    ) -> None:
        self.config = config
        self.container: Container | None = None
        self._key_manager = key_manager
        self._api_key: str | None = None

    def _collect_outputs_impl(self, container: Container, out_dir: Path) -> None:
        """Copy task-specific outputs from the container to local *out_dir*.

        Override in subclasses to define which paths inside the container
        count as outputs (e.g. ``/pocs/``, ``/workspace/flag.txt``).
        """
        raise NotImplementedError

    def collect_outputs(self, container: Container, out_dir: Path) -> None:
        """Copy all outputs from the container to local *out_dir*.

        :meth:`_collect_outputs_impl` for task-specific outputs.
        """
        try:
            if self.config.save_workspace_after_eval:
                workspace_out = out_dir / "workspace"
                docker_cp_from_container(
                    container.id,
                    "/workspace",
                    str(workspace_out),
                )
                self._prune_large_files(
                    workspace_out, self.config.save_workspace_max_file_bytes
                )
            self._collect_outputs_impl(container, out_dir)
        except Exception as e:
            logger.exception(
                f"Failed to copy outputs from container: {e}", stack_info=True
            )

    @staticmethod
    def _prune_large_files(directory: Path, max_bytes: int | None) -> None:
        """Delete files larger than *max_bytes* under *directory* (recursive).

        No-op when *max_bytes* is None. Operates on the host-side copy only,
        so it never mutates the container (a kept container retains everything).
        """
        if max_bytes is None:
            return
        removed = 0
        freed = 0
        for path in directory.rglob("*"):
            try:
                if path.is_file() and not path.is_symlink():
                    size = path.stat().st_size
                    if size > max_bytes:
                        path.unlink()
                        removed += 1
                        freed += size
            except OSError as e:
                logger.warning("Could not prune workspace file %s: %s", path, e)
        if removed:
            logger.info(
                "Pruned %d workspace file(s) larger than %d bytes (%.1f MiB freed)",
                removed,
                max_bytes,
                freed / (1024 * 1024),
            )

    def collect_logs(self, container: Container, out_dir: Path) -> None:
        """Copy logs from the container to local *out_dir*."""
        try:
            docker_cp_from_container(
                container.id,
                "/logs/.",
                str(out_dir),
            )
        except Exception as e:
            logger.exception(
                f"Failed to copy logs from container: {e}", stack_info=True
            )

    def _verify_impl(self, out_dir: Path) -> list[CheckResult]:
        """Assess the outputs collected in *out_dir*.

        Override in subclasses to implement task-specific success criteria.
        Works entirely on local files so it can run after the container is gone.
        """
        raise NotImplementedError

    def verify(self):
        """Wrapper around :meth:`_verify_impl`"""
        results = self._verify_impl(self.config.out_dir / "outputs")
        res = EvalResult(task_id=self.config.task_id, checks=results)
        return res

    def _save_metadata(self, out_dir: Path) -> None:
        """Save evaluation metadata to *out_dir* before verification.

        Override in subclasses to persist task-specific metadata
        (e.g. expected flag). Called after outputs are collected but
        before :meth:`verify`.
        """

    def _cleanup_impl(self):
        """Run subclass-specific cleanup logic.

        Override in subclasses for custom cleanup (e.g. deleting remote
        resources).  Called by :meth:`cleanup` before container removal.
        """

    def cleanup(self):
        """Clean up all resources used by the evaluator.

        Saves API key usage, deletes the scoped API key, runs
        :meth:`_cleanup_impl`, then removes the Docker container.
        """
        if self._api_key and self._key_manager:
            try:
                usage = self._key_manager.get_api_key_usage(self._api_key)
                save_json(
                    usage,
                    self.config.out_dir / "key_usage.json",
                    indent=2,
                )
                logger.info("API key spend: %.4f", usage.get("spend", 0.0))
            except Exception as e:
                logger.warning("Failed to get API key usage: %s", e)

            try:
                self._key_manager.delete_api_key(self._api_key)
            except Exception as e:
                logger.warning("Failed to delete API key: %s", e)

        # cleanup() runs from evaluate()'s finally block, so every step must be
        # best-effort: a failure here must not propagate (it would mask the
        # already-computed result) or skip the remaining teardown.
        try:
            self._cleanup_impl()
        except Exception as e:
            logger.warning("Error in subclass cleanup: %s", e)

        if self.container is not None:
            if not self.config.keep_container:
                cid = self.container.id[:12]
                try:
                    self.container.remove(force=True)
                    logger.info("Container %s removed", cid)
                except Exception as e:
                    logger.warning(
                        "Failed to remove container %s during cleanup; "
                        "it may need manual removal (docker rm -f): %s",
                        cid,
                        e,
                    )
                finally:
                    self.container = None
            else:
                logger.info("Keeping container %s", self.container.id[:12])

    def _resolve_docker_image(self) -> str:
        """Return the Docker image name for this task.

        Override in subclasses that use a different metadata source.
        """
        task_meta = TASK_METADATA[self.config.task_id]
        return task_meta.images[self.config.image_mode]

    def _extra_volumes(self) -> dict:
        """Return additional volumes to mount in the agent container.

        Override in subclasses to mount task-specific data (e.g. kernel
        artifacts). Format matches Docker SDK volumes dict::

            {"/host/path": {"bind": "/container/path", "mode": "ro"}}
        """
        return {}

    def _extra_container_kwargs(self) -> dict:
        """Return additional kwargs for ``client.containers.run()``.

        Override in subclasses to pass extra options like ``devices``,
        ``cap_add``, ``security_opt``, etc.
        """
        return {}

    def _resource_container_kwargs(self) -> dict:
        """Build ``containers.run()`` kwargs from :class:`EvalConfig` limits.

        Only fields the user set are included, so unspecified limits leave
        Docker's defaults (i.e. unlimited) in place.
        """
        cfg = self.config
        mapping = {
            "mem_limit": cfg.container_mem_limit,
            "memswap_limit": cfg.container_memswap_limit,
            "nano_cpus": cfg.container_nano_cpus,
            "pids_limit": cfg.container_pids_limit,
            "shm_size": cfg.container_shm_size,
        }
        kwargs: dict = {k: v for k, v in mapping.items() if v is not None}
        if cfg.container_storage_size is not None:
            kwargs["storage_opt"] = {"size": cfg.container_storage_size}
        return kwargs

    def prepare_workspace(self, workspace_dir: Path) -> str:
        """Prepare the task workspace and return the task description.

        By default, this calls :func:`cybergym.task.workspace.prepare_workspace`
        to set up the workspace based on the task ID, and returns the prompt
        generated by that function. Override if you need custom workspace
        preparation logic or a different prompt format.
        """
        return prepare_workspace(
            self.config.task_type,
            self.config.task_id,
            workspace_dir,
            **self.config.task_extra_kwargs,
        )

    def evaluate(
        self,
        agent_fn: Callable[
            [
                AgentFnArguments,
            ],
            None,
        ],
    ) -> EvalResult:
        """Run the full evaluation pipeline.

        1. Prepare the task workspace via :func:`cybergym.task.workspace.prepare_workspace`.
        2. Start a Docker container from the task image.
        3. Copy the workspace into the container at ``/workspace``.
        4. Call ``agent_fn(container, prompt)``.
        5. Call :meth:`collect_outputs` to copy results to ``out_dir/outputs/``.
        6. Call :meth:`verify` on the collected outputs.
        7. Persist ``result.json`` and return an :class:`EvalResult`.
        """
        docker_image = self._resolve_docker_image()
        # Container name: task_id alone identifies both task_type and task;
        # keep short to stay under Docker's 63-char hostname limit.
        container_name = (
            "cg-eval-"
            f"{_container_name_part(self.config.task_id)}-"
            f"{_container_name_suffix()}"
        )

        self.config.out_dir.mkdir(parents=True, exist_ok=True)
        save_json(
            self.config,
            self.config.out_dir / "config.json",
            indent=2,
        )

        system_config = check_system_config()
        save_json(
            system_config,
            self.config.out_dir / "system_config.json",
            indent=2,
        )

        workspace_dir = self.config.out_dir / "workspace"
        workspace_dir.mkdir(exist_ok=True)
        prompt = self.prepare_workspace(workspace_dir)

        logger.info(
            "Starting evaluation: task=%s image=%s", self.config.task_id, docker_image
        )

        # Connect to a running firewall proxy if enabled
        firewall_env: dict[str, str] | None = None
        network: str | None = None
        if self.config.use_firewall:
            firewall = FirewallProxyManager()
            firewall.connect()
            network = firewall.network_name
            firewall_env = firewall.env_vars()
            logger.info(
                "Connected to firewall: network=%s url=%s", network, firewall.proxy_url
            )

        client = get_docker_client()
        try:
            volumes = {
                str(self.config.runtime_dir.absolute()): {
                    "bind": self.config.runtime_dir_in_container,
                    "mode": "ro",
                },
                **self._extra_volumes(),
            }
            self.container = client.containers.run(
                image=docker_image,
                command=["tail", "-f", "/dev/null"],
                detach=True,
                name=container_name,
                network=network,
                volumes=volumes,
                **self._resource_container_kwargs(),
                **self._extra_container_kwargs(),
            )
            logger.info(
                "Container started: name=%s id=%s",
                self.container.name,
                self.container.id[:12],
            )

            workspace_in_container = self.config.workspace_dir_in_container

            self.container.exec_run(
                ["bash", "-c", f"mkdir -p {workspace_in_container}"]
            )
            docker_cp_to_container(
                self.container.id,
                f"{workspace_dir}/.",
                workspace_in_container,
            )
            logger.info("Workspace copied to container")

            # Validate that at least one auth source is available
            if (
                not self.config.api_key
                and not self.config.credential_path
                and not self._key_manager
            ):
                raise ValueError(
                    "No authentication configured: provide 'api_key', "
                    "'credential_path', or a key_manager"
                )

            # Resolve API key: use direct key if provided, otherwise generate via LiteLLM
            api_base_url: str | None = None
            if self.config.api_key:
                self._api_key = self.config.api_key.get_secret_value()
                api_base_url = self.config.api_base_url
                logger.info("Using direct API key")
            elif self._key_manager:
                self._api_key = self._key_manager.generate_api_key()
                api_base_url = self._key_manager.api_base_url
                logger.info("Generated API key via key manager")

            logger.info(
                "Format prompt, template: %s", self.config.task_description_template
            )
            task_description = (
                self.config.task_description_template.format(task_description=prompt)
                if self.config.task_description_template
                else prompt
            )

            logger.info("Running agent")
            tic = time.perf_counter()

            try:
                agent_fn(
                    AgentFnArguments(
                        task_description=task_description,
                        container_id=self.container.id,
                        runtime_dir_in_container=self.config.runtime_dir_in_container,
                        agent_timeout_seconds=self.config.agent_timeout_seconds,
                        out_dir=self.config.out_dir,
                        api_base_url=api_base_url,
                        api_key=self._api_key,
                        extra_kwargs=self.config.agent_extra_kwargs,
                        credential_path=self.config.credential_path,
                        firewall_env=firewall_env,
                    )
                )
            except Exception:
                logger.exception("Error running agent function", stack_info=True)
                pass
            toc = time.perf_counter()
            logger.info("Agent finished")

            outputs_dir = self.config.out_dir / "outputs"
            outputs_dir.mkdir(exist_ok=True)
            self._save_metadata(self.config.out_dir)
            self.collect_outputs(self.container, outputs_dir)

            try:
                result = self.verify()
            except Exception as e:
                logger.exception("Error during verification", stack_info=True)
                result = EvalResult(
                    task_id=self.config.task_id, checks=[], error=str(e)
                )
            result.elapsed_time = toc - tic

            result_path = self.config.out_dir / "result.json"
            save_json(result, result_path, indent=2)
            total_score = sum(check.score for check in result.checks)
            logger.info(
                "Saved evaluation result: task=%s path=%s total_score=%.3f",
                result.task_id,
                result_path,
                total_score,
            )

            return result

        finally:
            if self.container is not None:
                self.collect_logs(self.container, self.config.out_dir / "logs")
            self.cleanup()
