"""Task-type-specific container launch strategies.

Each TaskHandler knows how to validate a task_info string and launch the
appropriate Docker container. ServerManager dispatches to the correct handler
based on the task_info prefix.
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import docker
from cybergym.server.types import ContainerResources
from cybergym.task.metadata import (
    KERNEL_TASK_METADATA,
    TASK_METADATA,
    V8_TASK_METADATA,
    bitmap_to_capabilities,
    bitmap_to_env,
)
from cybergym.utils import DATA_DIR, docker_cp_to_container, get_docker_client

logger = logging.getLogger(__name__)


FLAG_CONTAINER_PATH = "/run/flag"


def _container_name_part(value: str, max_len: int = 32) -> str:
    """Sanitize ``value`` for use in a Docker container name and cap its
    length so the full name stays well under Docker's 63-char hostname limit.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")
    sanitized = sanitized.lower() or "unknown"
    return sanitized[:max_len].rstrip("-") or "unknown"


def _task_container_name(prefix: str, task_info: str) -> str:
    suffix = uuid4().hex[:8]
    return f"cg-{prefix}-{_container_name_part(task_info)}-{suffix}"


def _inject_flag(container_id: str, flag: str) -> None:
    """Write the flag into the container via docker_cp (never in process args)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".flag", delete=True) as f:
        f.write(flag)
        f.flush()
        docker_cp_to_container(container_id, Path(f.name), FLAG_CONTAINER_PATH)


def _get_container_ip(container) -> str:
    """Extract the IP address from a running Docker container."""
    nets = container.attrs["NetworkSettings"]["Networks"]
    if not nets:
        raise RuntimeError(f"No network found for container {container.id}")
    ip = list(nets.values())[0]["IPAddress"]
    if not ip:
        raise RuntimeError(f"No IP address found for container {container.id}")
    return ip


class TaskHandler(Protocol):
    """Strategy for task-type-specific container launch."""

    RESOURCE_KEY: str
    """Key used to look up this handler's resource budget in the per-type
    map passed by :class:`ServerManager` (e.g. ``"kernel"``, ``"v8"``)."""

    def resolve_task(self, task_info: str) -> tuple[str, str]:
        """Parse task_info and validate the task exists.

        Returns:
            (task_id, image_name)

        Raises:
            KeyError: If the task_id is not found in metadata.
            ValueError: If the task_info format is invalid.
        """
        ...

    def launch(
        self,
        task_info: str,
        flag: str,
        *,
        network: str | None = None,
        resources: ContainerResources | None = None,
    ) -> tuple[str, int, str]:
        """Launch a Docker container for the task.

        Args:
            task_info: Task identifier string.
            flag: The flag to inject into the container.
            network: Optional Docker network name. When provided, the
                container is attached to this network instead of the
                default bridge (used for proxy/firewall enforcement).
            resources: Optional resource budget applied to the launched
                container. ``None`` leaves Docker's defaults (unlimited).

        Returns:
            (ip, port, container_id)
        """
        ...


class UserTaskHandler:
    """Binary exploitation handler (user/cybergym tasks).

    Mounts data/server/ as /data (socat + user/ scripts). Uses the 8-byte
    hex size-prefix protocol on port 8000.

    task_info format: ``<task_id>/<image_mode>/<target>``.

    ``task_id`` may be the hashed form ``user:<hex>`` or the alias
    ``user:<entry_name>`` (``entry_name`` itself contains a ``/``), so we
    rpartition twice — first to peel off ``target``, then ``image_mode`` —
    and treat everything left as the ``task_id``.

    ``target`` is ``READ`` or ``EXEC``; it selects the flag-file
    privilege profile inside the container (``user/init.sh`` branches on it).
    """

    PORT = 8000
    RESOURCE_KEY = "user"
    _VALID_TARGETS = ("READ", "EXEC")

    def _parse_task_info(self, task_info: str) -> tuple[str, str, str]:
        head, _, target = task_info.rpartition("/")
        task_id, _, image_type = head.rpartition("/")
        if not task_id or not image_type or target not in self._VALID_TARGETS:
            raise ValueError(
                f"Invalid task_info {task_info!r}; expected "
                f"'<task_id>/<image_mode>/<target>' with target in "
                f"{self._VALID_TARGETS}"
            )
        return task_id, image_type, target

    def resolve_task(self, task_info: str) -> tuple[str, str]:
        task_id, image_type, _target = self._parse_task_info(task_info)
        task_meta = TASK_METADATA[task_id]
        return task_id, task_meta.images[image_type]

    def launch(
        self,
        task_info: str,
        flag: str,
        *,
        network: str | None = None,
        resources: ContainerResources | None = None,
    ) -> tuple[str, int, str]:
        task_id, image_type, target = self._parse_task_info(task_info)
        task_meta = TASK_METADATA[task_id]
        image_name = task_meta.images[image_type]
        target_binary_path = f"/out/{task_meta.binary}"

        logger.info(
            "User: launching container for task_info=%s image=%s network=%s",
            task_info,
            image_name,
            network,
        )

        client = get_docker_client()
        container = client.containers.run(
            image=image_name,
            command=["tail", "-f", "/dev/null"],
            detach=True,
            name=_task_container_name("task", task_info),
            network=network,
            volumes={
                str(DATA_DIR / "server"): {"bind": "/data", "mode": "ro"},
            },
            environment=task_meta.env,
            **(resources.to_run_kwargs() if resources else {}),
        )
        _inject_flag(container.id, flag)
        container.exec_run(["/data/user/start.sh", target_binary_path, target], detach=True)
        time.sleep(0.5)
        container.reload()
        ip = _get_container_ip(container)
        return ip, self.PORT, container.id


class V8TaskHandler:
    """V8 exploitation handler.

    Mounts data/server/v8/ (start.sh, serve.sh) and data/server/socat
    into the container. start.sh runs .init, writes /flag, starts socat
    on port 1337 with raw JS protocol.

    task_info format: ``v8:<hash>`` or ``v8:<hash>/nosandbox``. The
    ``/nosandbox`` suffix selects ``image_no_sandbox`` for tasks that
    have a sandbox-disabled build.
    """

    PORT = 1337
    RESOURCE_KEY = "v8"

    def _parse_task_info(self, task_info: str) -> tuple[str, bool]:
        """Split task_info into (task_id, no_sandbox)."""
        task_id, sep, suffix = task_info.rpartition("/")
        if sep and suffix == "nosandbox":
            return task_id, True
        return task_info, False

    def _resolve_image(self, task_id: str, no_sandbox: bool) -> str:
        task_meta = V8_TASK_METADATA[task_id]
        if no_sandbox:
            if task_meta.image_no_sandbox is None:
                raise ValueError(f"Task {task_id} does not support no-sandbox variant")
            return task_meta.image_no_sandbox
        if task_meta.image is None:
            raise ValueError(
                f"Task {task_id} has no main image (V8 build predates the sandbox); "
                f"use the nosandbox variant instead"
            )
        return task_meta.image

    def resolve_task(self, task_info: str) -> tuple[str, str]:
        task_id, no_sandbox = self._parse_task_info(task_info)
        image = self._resolve_image(task_id, no_sandbox)
        return task_id, image

    def launch(
        self,
        task_info: str,
        flag: str,
        *,
        network: str | None = None,
        resources: ContainerResources | None = None,
    ) -> tuple[str, int, str]:
        task_id, no_sandbox = self._parse_task_info(task_info)
        image = self._resolve_image(task_id, no_sandbox)

        logger.info(
            "V8: launching container for task_info=%s image=%s no_sandbox=%s network=%s",
            task_info,
            image,
            no_sandbox,
            network,
        )

        server_dir = DATA_DIR / "server"
        client = get_docker_client()
        container = client.containers.run(
            image=image,
            command=["tail", "-f", "/dev/null"],
            detach=True,
            name=_task_container_name("v8", task_info),
            network=network,
            volumes={
                str(server_dir): {"bind": "/data", "mode": "ro"},
            },
            **(resources.to_run_kwargs() if resources else {}),
        )
        _inject_flag(container.id, flag)
        container.exec_run(["/data/v8/start.sh"], detach=True)
        time.sleep(1)
        container.reload()
        ip = _get_container_ip(container)
        return ip, self.PORT, container.id


class KernelTaskHandler:
    """Kernel exploitation handler (kernelctf + syzbot subsets).

    Launches a QEMU VM inside a Docker container. The image is resolved
    directly from ``KernelTaskMetadata.image_name`` and is expected to have
    all kernel artifacts, VM images, and source trees baked in — no host
    volumes are mounted for task data. The VM's serial console is exposed
    via socat on a TCP port.

    task_info format::

        kernel:<hash>
        kernel:<hash>/<defense_bitmap>

    The defense bitmap is a compact integer encoding of mitigation/capability
    flags (see DEFENSE_FLAG_BITS in metadata.py). Default 0 = all defenses on.
    """

    PORT = 1337
    RESOURCE_KEY = "kernel"

    def _parse_task_info(self, task_info: str) -> tuple[str, int]:
        """Parse task_info into (task_id, defense_bitmap)."""
        parts = task_info.split("/")
        task_id = parts[0]
        defense_bitmap = int(parts[1]) if len(parts) > 1 else 0
        return task_id, defense_bitmap

    def resolve_task(self, task_info: str) -> tuple[str, str]:
        task_id, _ = self._parse_task_info(task_info)
        if task_id not in KERNEL_TASK_METADATA:
            raise KeyError(f"Unknown kernel task: {task_id}")
        return task_id, KERNEL_TASK_METADATA[task_id].image_name

    def launch(
        self,
        task_info: str,
        flag: str,
        *,
        network: str | None = None,
        resources: ContainerResources | None = None,
    ) -> tuple[str, int, str]:
        task_id, defense_bitmap = self._parse_task_info(task_info)
        meta = KERNEL_TASK_METADATA[task_id]
        image = meta.image_name

        logger.info(
            "Kernel: launching QEMU container for task_info=%s image=%s defense_bitmap=%d network=%s",
            task_info,
            image,
            defense_bitmap,
            network,
        )
        logger.info("Defense capabilities: %s", bitmap_to_capabilities(defense_bitmap))

        # Use KVM if available on the host
        devices = []
        if Path("/dev/kvm").exists():
            devices.append("/dev/kvm:/dev/kvm")
        else:
            logger.warning("KVM not available, QEMU will use software emulation (slow)")

        # Scripts are always mounted (not baked into images)
        scripts_dir = DATA_DIR / "server" / "kernel"
        volumes = {
            str(scripts_dir.absolute()): {"bind": "/scripts", "mode": "ro"},
        }

        client = get_docker_client()
        container = client.containers.run(
            image=image,
            command=["tail", "-f", "/dev/null"],
            detach=True,
            name=_task_container_name("kernel", task_info),
            network=network,
            devices=devices if devices else None,
            volumes=volumes,
            environment={
                "PORT": str(self.PORT),
                **bitmap_to_env(defense_bitmap),
                # Per-task VM-launch overrides (empty for almost all tasks).
                "QEMU_EXTRA_ARGS": meta.qemu_extra_args,
                "KERNEL_CMDLINE_EXTRA": meta.kernel_cmdline_extra,
            },
            **(resources.to_run_kwargs() if resources else {}),
        )

        _inject_flag(container.id, flag)
        container.exec_run(["/scripts/start_qemu.sh"], detach=True)

        # Wait for socat to start listening
        time.sleep(2)
        container.reload()
        if container.status != "running":
            raise RuntimeError(
                f"QEMU container exited unexpectedly (status: {container.status})"
            )
        ip = _get_container_ip(container)
        return ip, self.PORT, container.id


# ── Dispatch ────────────────────────────────────────────────────────

_user_handler = UserTaskHandler()
_v8_handler = V8TaskHandler()
_kernel_handler = KernelTaskHandler()

# Prefix -> handler. Checked in order; first match wins.
_HANDLER_PREFIXES: list[tuple[str, TaskHandler]] = [
    ("v8:", _v8_handler),
    ("kernel:", _kernel_handler),
    ("user:", _user_handler),
]
_DEFAULT_HANDLER: TaskHandler = _user_handler


def get_handler(task_info: str) -> TaskHandler:
    """Return the appropriate TaskHandler for a given task_info string."""
    for prefix, handler in _HANDLER_PREFIXES:
        if task_info.startswith(prefix):
            return handler
    return _DEFAULT_HANDLER
