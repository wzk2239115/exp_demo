"""
Server lifecycle controller.

Endpoints:
    - /create_server  - returns server ip & port (idempotent per agent_id+task_id)
    - /delete_server  - tears down the server and frees resources
    - /restart_server - delete then create
    - /health_check   - returns current server status

Management rules:
    - One (agent_id, task_id) pair → at most one server at a time.
    - Repeated create_server calls return the same ip/port.
    - Servers auto-expire after `server_ttl` seconds (default 1 hour).

"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field

from docker.errors import NotFound
from fastapi import HTTPException

import docker
from cybergym.server.task_handler import get_handler
from cybergym.server.types import (
    ContainerResources,
    RunCommandRequest,
    ServerHealthResponse,
    ServerInfo,
    ServerRequest,
)
from cybergym.task.token import generate_flag, verify_token
from cybergym.utils import get_docker_client

logger = logging.getLogger(__name__)

# Default time-to-live for a server (seconds).
DEFAULT_SERVER_TTL: int = 3600  # 1 hour

# Interval between cleanup sweeps (seconds).
CLEANUP_INTERVAL: int = 60

# Minimum interval between container launches for the same key (seconds).
RATE_LIMIT_INTERVAL: int = 60

# Max time a caller waits to attach to an in-flight creation of the same
# server before giving up. Must comfortably exceed a worst-case launch
# (docker run + QEMU boot + the health-check retry budget below).
CREATION_WAIT_TIMEOUT: float = 180.0

# Health-check retry budget for a freshly launched server.
HEALTH_CHECK_RETRIES: int = 3
HEALTH_CHECK_RETRY_DELAY: float = 3.0


# ── Internal record for a running server ─────────────────────────────


@dataclass
class _ServerRecord:
    task_info: str
    agent_id: str
    ip: str
    port: int
    created_at: float  # time.time()
    container_id: str  # placeholder for real docker container id


@dataclass
class _Creation:
    """Tracks an in-flight server creation.

    Concurrent ``create_server`` calls for the same ``(agent_id, task_info)``
    attach to this record and wait on ``event`` instead of launching a
    duplicate container. The creator fills in ``record`` (success) or
    ``error`` (failure) before setting the event.
    """

    event: threading.Event = field(default_factory=threading.Event)
    record: _ServerRecord | None = None
    error: BaseException | None = None


def _launch_container(
    task_info: str,
    flag_seed: str,
    *,
    network: str | None = None,
    resources_by_type: dict[str, ContainerResources] | None = None,
) -> tuple[str, int, str]:
    """Launch a docker container for the given task.

    Dispatches to the appropriate TaskHandler based on task_info prefix.
    The flag is derived deterministically from *flag_seed* and *task_info*.

    Args:
        task_info: Task identifier string.
        flag_seed: Seed for deterministic flag generation.
        network: Optional Docker network name for the container.
        resources_by_type: Optional map of handler ``RESOURCE_KEY`` to the
            resource budget applied to that task type's container. When the
            map omits a handler's key (or is ``None``), the container is
            launched with Docker's defaults.

    Returns:
        (ip, port, container_id)
    """
    flag = generate_flag(task_info, seed=flag_seed)
    handler = get_handler(task_info)
    resources = (
        resources_by_type.get(handler.RESOURCE_KEY) if resources_by_type else None
    )
    return handler.launch(task_info, flag, network=network, resources=resources)


def _destroy_container(record: _ServerRecord) -> None:
    """Destroy the docker container described by *record*.

    This is a no-op stub.
    """
    client = get_docker_client()
    try:
        container = client.containers.get(record.container_id)
        container.remove(force=True)
        logger.info(
            "Destroyed container %s for %s/%s (%s:%d)",
            record.container_id,
            record.agent_id,
            record.task_info,
            record.ip,
            record.port,
        )
    except NotFound:
        logger.warning(
            "Container %s not found during destroy for %s/%s",
            record.container_id,
            record.agent_id,
            record.task_info,
        )


def _health_check_container(record: _ServerRecord) -> bool:
    """Check if the docker container described by *record* is healthy.

    Checks that the container is running.
    """
    # Check if socat is listening inside the container by inspecting /proc/net/tcp,
    try:
        client = get_docker_client()
        container = client.containers.get(record.container_id)
        if container.status != "running":
            return False
        # Port in /proc/net/tcp is hex, in little-endian format
        port_hex = f"{record.port:04X}"
        res = container.exec_run(
            ["grep", "-q", f":{port_hex}", "/proc/net/tcp"],
        )
        return res.exit_code == 0
    except NotFound:
        logger.warning(
            "Health check: container %s not found for %s/%s",
            record.container_id,
            record.agent_id,
            record.task_info,
        )
        return False
    except Exception as e:
        logger.warning(
            "Health check failed for %s/%s - %s",
            record.agent_id,
            record.task_info,
            e,
        )
        return False


# ── ServerManager ────────────────────────────────────────────────────


class ServerManager:
    """Thread-safe registry of running task servers."""

    def __init__(
        self,
        salt: str,
        flag_seed: str,
        server_ttl: int = DEFAULT_SERVER_TTL,
        network: str | None = None,
        resources_by_type: dict[str, ContainerResources] | None = None,
    ):
        self._salt = salt
        self._flag_seed = flag_seed
        self._server_ttl = server_ttl
        self._network = network
        self._resources_by_type = resources_by_type
        # key: (agent_id, task_id) → _ServerRecord
        self._servers: dict[tuple[str, str], _ServerRecord] = {}
        # In-flight creations: key → _Creation. Lets concurrent callers attach
        # to a launch in progress instead of starting a duplicate.
        self._pending: dict[tuple[str, str], _Creation] = {}
        # Track last launch time for rate limiting
        self._last_launch: dict[tuple[str, str], float] = {}
        # Guards _servers, _pending and _last_launch. Held only for short
        # dict operations — never across a container launch or health check.
        self._lock = threading.Lock()
        self._cleanup_task: asyncio.Task | None = None

    # ── Auth helper ──────────────────────────────────────────────────

    def _verify(self, req: ServerRequest) -> str:
        task_info = verify_token(req.agent_id, req.token, salt=self._salt)
        if task_info is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        handler = get_handler(task_info)
        try:
            handler.resolve_task(task_info)
        except (KeyError, ValueError):
            raise HTTPException(status_code=400, detail="Unknown task_id")

        return task_info

    def _check_rate_limit(self, key: tuple[str, str]) -> None:
        """Check if enough time has passed since the last container launch for this key.

        Raises:
            HTTPException: If rate limit is violated.
        """
        now = time.time()
        last_launch = self._last_launch.get(key)
        if last_launch is not None:
            elapsed = now - last_launch
            if elapsed < RATE_LIMIT_INTERVAL:
                remaining = RATE_LIMIT_INTERVAL - elapsed
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Please wait {remaining:.1f} seconds before launching again.",
                )

    # ── Public API ───────────────────────────────────────────────────

    @staticmethod
    def _server_info(rec: _ServerRecord) -> ServerInfo:
        return ServerInfo(
            agent_id=rec.agent_id,
            ip=rec.ip,
            port=rec.port,
            created_at=rec.created_at,
        )

    def create_server(self, req: ServerRequest) -> ServerInfo:
        task_info = self._verify(req)
        key = (req.agent_id, task_info)

        # Hold the lock only long enough to either (a) return an existing
        # server, (b) attach to an in-flight creation, or (c) claim the right
        # to create. The slow launch + health check happen WITHOUT the lock,
        # so creations for different keys run concurrently and delete/health
        # calls never queue behind a multi-second QEMU boot.
        with self._lock:
            rec = self._servers.get(key)
            if rec is not None:
                logger.info(
                    "Returning existing server for %s/%s", req.agent_id, task_info
                )
                return self._server_info(rec)

            pending = self._pending.get(key)
            if pending is None:
                # We win the race to create. Reserve the key and record the
                # launch time for rate limiting before releasing the lock.
                self._check_rate_limit(key)
                self._last_launch[key] = time.time()
                pending = _Creation()
                self._pending[key] = pending
                is_creator = True
            else:
                is_creator = False

        if not is_creator:
            return self._await_creation(pending, req.agent_id, task_info)

        return self._launch_and_register(key, task_info, req.agent_id, pending)

    def _wait_for_pending(self, key: tuple[str, str]) -> None:
        """Block until any in-flight creation for *key* has settled.

        Lets ``delete_server``/``restart_server`` coordinate with a concurrent
        ``create_server``: after this returns, the creator has either published
        its server to ``_servers`` (so we can tear it down) or failed and
        cleared ``_pending`` (so there is nothing to orphan). No lock is held
        during the wait. The creation's outcome is intentionally ignored — the
        caller re-reads ``_servers`` under the lock afterwards.
        """
        with self._lock:
            pending = self._pending.get(key)
        if pending is not None:
            pending.event.wait(timeout=CREATION_WAIT_TIMEOUT)

    def _await_creation(
        self, pending: _Creation, agent_id: str, task_info: str
    ) -> ServerInfo:
        """Block until another caller's in-flight creation for this key finishes."""
        if not pending.event.wait(timeout=CREATION_WAIT_TIMEOUT):
            raise HTTPException(
                status_code=504,
                detail="Timed out waiting for in-flight server creation",
            )
        if pending.error is not None or pending.record is None:
            raise HTTPException(
                status_code=500, detail="Server created but health check failed"
            )
        logger.info("Reusing in-flight server for %s/%s", agent_id, task_info)
        return self._server_info(pending.record)

    def _launch_and_register(
        self,
        key: tuple[str, str],
        task_info: str,
        agent_id: str,
        pending: _Creation,
    ) -> ServerInfo:
        """Launch + health-check a server (no lock held), then publish it.

        On any failure the reservation is cleared and waiters are woken with
        an error so they don't hang for the full timeout.
        """
        try:
            ip, port, cid = _launch_container(
                task_info,
                self._flag_seed,
                network=self._network,
                resources_by_type=self._resources_by_type,
            )
            rec = _ServerRecord(
                task_info=task_info,
                agent_id=agent_id,
                ip=ip,
                port=port,
                created_at=time.time(),
                container_id=cid,
            )
            logger.info(
                "Created new server for %s/%s → %s:%d", agent_id, task_info, ip, port
            )

            if not self._await_healthy(rec):
                _destroy_container(rec)
                logger.error(
                    "Health check failed for newly created server %s/%s at %s:%d",
                    agent_id,
                    task_info,
                    ip,
                    port,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Server created but health check failed",
                )
        except BaseException as exc:
            with self._lock:
                self._pending.pop(key, None)
            pending.error = exc
            pending.event.set()
            raise
        else:
            with self._lock:
                self._servers[key] = rec
                self._pending.pop(key, None)
            pending.record = rec
            pending.event.set()
            return self._server_info(rec)

    @staticmethod
    def _await_healthy(rec: _ServerRecord) -> bool:
        """Poll the freshly launched server until it reports healthy."""
        for attempt in range(HEALTH_CHECK_RETRIES):
            if _health_check_container(rec):
                return True
            if attempt < HEALTH_CHECK_RETRIES - 1:
                time.sleep(HEALTH_CHECK_RETRY_DELAY)
        return False

    def delete_server(self, req: ServerRequest) -> dict:
        task_info = self._verify(req)
        key = (req.agent_id, task_info)

        # Coordinate with an in-flight create so we don't 404 now and leave its
        # container untracked once it publishes.
        self._wait_for_pending(key)

        with self._lock:
            rec = self._servers.pop(key, None)

        if rec is None:
            logger.info(
                "Delete server: no server found for %s/%s", req.agent_id, task_info
            )
            raise HTTPException(
                status_code=404, detail="No server found for this agent/task pair"
            )

        _destroy_container(rec)
        logger.info("Deleted server for %s/%s", req.agent_id, task_info)
        return {
            "message": "Server deleted",
            "task_info": task_info,
            "agent_id": req.agent_id,
        }

    def restart_server(self, req: ServerRequest) -> ServerInfo:
        task_info = self._verify(req)
        key = (req.agent_id, task_info)

        # Coordinate with an in-flight create for this key: wait for it to
        # publish so we tear down its container instead of racing it and
        # leaking a second, untracked one.
        self._wait_for_pending(key)

        # Check rate limit before restarting
        with self._lock:
            self._check_rate_limit(key)
            self._last_launch[key] = time.time()
            rec = self._servers.pop(key, None)

        if rec is not None:
            _destroy_container(rec)
            logger.info(
                "Deleted existing server for %s/%s before restart",
                req.agent_id,
                task_info,
            )

        # Create a fresh one
        ip, port, cid = _launch_container(
            task_info,
            self._flag_seed,
            network=self._network,
            resources_by_type=self._resources_by_type,
        )
        new_rec = _ServerRecord(
            task_info=task_info,
            agent_id=req.agent_id,
            ip=ip,
            port=port,
            created_at=time.time(),
            container_id=cid,
        )
        with self._lock:
            self._servers[key] = new_rec

        logger.info(
            "Restarted server for %s/%s → %s:%d", req.agent_id, task_info, ip, port
        )
        return ServerInfo(
            agent_id=new_rec.agent_id,
            ip=new_rec.ip,
            port=new_rec.port,
            created_at=new_rec.created_at,
        )

    def health_check(self, req: ServerRequest) -> ServerHealthResponse:
        task_info = self._verify(req)
        key = (req.agent_id, task_info)

        with self._lock:
            rec = self._servers.get(key)

        if rec is None:
            return ServerHealthResponse(agent_id=req.agent_id, status="not_found")

        if not _health_check_container(rec):
            return ServerHealthResponse(
                agent_id=req.agent_id,
                status="unhealthy",
                ip=rec.ip,
                port=rec.port,
            )

        uptime = time.time() - rec.created_at
        return ServerHealthResponse(
            agent_id=req.agent_id,
            status="running",
            ip=rec.ip,
            port=rec.port,
            uptime_seconds=round(uptime, 2),
        )

    def run_command(self, req: RunCommandRequest) -> tuple[int, str]:
        task_info = self._verify(req)
        key = (req.agent_id, task_info)

        with self._lock:
            rec = self._servers.get(key)

        if rec is None:
            logger.info(
                "Run command: no server found for %s/%s", req.agent_id, task_info
            )
            raise HTTPException(
                status_code=404, detail="No server found for this agent/task pair"
            )

        client = get_docker_client()
        try:
            container = client.containers.get(rec.container_id)
            res = container.exec_run(req.command)
            return res.exit_code, res.output.decode(errors="ignore")
        except NotFound:
            logger.info(
                "Run command: container not found for %s/%s", req.agent_id, task_info
            )
            raise HTTPException(status_code=404, detail="Container not found")
        except Exception as e:
            logger.exception("Error running command in container")
            raise HTTPException(status_code=500, detail=str(e))

    # ── Auto-expiry ─────────────────────────────────────────────────

    def _expire_servers(self) -> int:
        """Remove servers that have exceeded the TTL. Returns count of expired."""
        now = time.time()
        expired_keys: list[tuple[str, str]] = []

        with self._lock:
            for key, rec in self._servers.items():
                if now - rec.created_at > self._server_ttl:
                    expired_keys.append(key)
            expired_records = [self._servers.pop(k) for k in expired_keys]

        for rec in expired_records:
            _destroy_container(rec)
            logger.info(
                "Auto-expired server for %s/%s (age %.0fs)",
                rec.agent_id,
                rec.task_info,
                now - rec.created_at,
            )
        return len(expired_records)

    async def start_cleanup_loop(self) -> None:
        """Start the background cleanup coroutine (call once during app lifespan)."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        """Cancel the cleanup coroutine and tear down all remaining servers."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Tear down any remaining servers
        with self._lock:
            remaining = list(self._servers.values())
            self._servers.clear()
        for rec in remaining:
            _destroy_container(rec)
            logger.info(
                "Shutdown: destroyed server for %s/%s", rec.agent_id, rec.task_info
            )

    async def _cleanup_loop(self) -> None:
        """Periodically expire servers that have exceeded the TTL."""
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL)
            try:
                count = self._expire_servers()
                if count:
                    logger.info("Cleanup sweep: expired %d server(s)", count)
            except Exception:
                logger.exception("Error during server cleanup sweep")
