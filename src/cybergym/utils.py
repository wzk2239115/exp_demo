import logging
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import uuid4

import httpx
from pydantic_core import to_json

import docker

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_docker_client() -> docker.DockerClient:
    """Process-local cached Docker client.

    Reusing one client per process keeps the underlying urllib3 connection
    pool warm so back-to-back Docker API calls reuse open unix-socket
    connections instead of handshaking each time. ``lru_cache`` makes the
    cache per-process, so each ``ProcessPoolExecutor`` worker gets its own;
    the parent must not call this before forking workers (lazy initialization
    naturally prevents this in our code paths).
    """
    return docker.from_env()


PROJECT_ROOT = Path(__file__).parents[2].absolute()
DATA_DIR = PROJECT_ROOT / "data"
DATA_UTILS_DIR = DATA_DIR / "utils"


# ── sysctl paths used by get_system_config ───────────────────────────────────

_SYSCTL_PATHS = {
    "aslr": "/proc/sys/kernel/randomize_va_space",
    "core_pattern": "/proc/sys/kernel/core_pattern",
    "core_uses_pid": "/proc/sys/kernel/core_uses_pid",
}

_ASLR_LABELS = {
    "0": "disabled",
    "1": "conservative (stack/mmap/VDSO)",
    "2": "full (default)",
}


def get_system_config() -> dict:
    """Read evaluation-relevant kernel settings and return them as a dict.

    Keys returned:
        aslr              – raw value (0/1/2) from randomize_va_space
        aslr_label        – human-readable description
        core_pattern      – kernel.core_pattern string
        core_uses_pid     – kernel.core_uses_pid (0 or 1)
    """
    config: dict = {}
    for key, path in _SYSCTL_PATHS.items():
        try:
            config[key] = Path(path).read_text().strip()
        except OSError:
            config[key] = None

    config["aslr_label"] = _ASLR_LABELS.get(config.get("aslr", ""), "unknown")
    return config


def check_system_config() -> dict:
    """Read system config, log it, and warn about non-ideal settings.

    Returns the same dict as :func:`get_system_config`.
    """
    config = get_system_config()

    logger.info(
        "System config: aslr=%s (%s), core_pattern=%s, core_uses_pid=%s",
        config.get("aslr"),
        config.get("aslr_label"),
        config.get("core_pattern"),
        config.get("core_uses_pid"),
    )

    return config


def save_json(obj, path, indent=None, **kwargs):
    """
    Save a JSON object to a file.
    """
    with open(path, "wb") as f:
        f.write(to_json(obj, indent=indent, **kwargs))


def docker_cp_to_container(
    container_id: str, host_path: str | Path, container_path: str, check: bool = True
) -> None:
    """Copy a file or directory from the host into a running container.

    Delegates to ``docker cp`` directly for correct semantics.
    """
    proc = subprocess.run(
        ["docker", "cp", str(host_path), f"{container_id}:{container_path}"],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    logger.debug("docker cp output: %s", proc.stdout.decode(errors="replace").rstrip())


def docker_cp_from_container(
    container_id: str, container_path: str, host_path: str | Path, check: bool = True
) -> None:
    """Copy a file or directory from a container to the host.

    Delegates to ``docker cp`` directly for correct semantics.
    """
    proc = subprocess.run(
        ["docker", "cp", f"{container_id}:{container_path}", str(host_path)],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    logger.debug("docker cp output: %s", proc.stdout.decode(errors="replace").rstrip())


def docker_exec_stream_with_exit_code(
    container_id,
    cmd,
    stdout=True,
    stderr=True,
    stdin=False,
    tty=False,
    privileged=False,
    user="",
    detach=False,
    environment=None,
    workdir=None,
    demux=False,
):
    client = get_docker_client()
    resp = client.api.exec_create(
        container_id,
        cmd,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        tty=tty,
        privileged=privileged,
        user=user,
        environment=environment,
        workdir=workdir,
    )
    exec_output = client.api.exec_start(
        resp["Id"], detach=detach, tty=tty, stream=True, socket=False, demux=demux
    )

    for line in exec_output:
        logger.debug(line.decode(errors="replace").rstrip())

    return client.api.exec_inspect(resp["Id"])["ExitCode"]


def container_credential_symlink(
    container_id: str,
    content: str | None = None,
    host_file: str | Path | None = None,
    link_path: str = "/logs/credentials",
) -> str:
    """Place a credential in a container behind a symlink.

    The real file lives under ``/tmp/<uuid>`` so that when ``/logs`` is
    copied out of the container the symlink target no longer exists —
    preventing accidental credential leakage.

    Provide *either* ``content`` (written directly) or ``host_file``
    (docker-cp'd in).  Returns the ``/tmp/…`` path of the real file.
    """
    if content is None and host_file is None:
        raise ValueError("Provide either content or host_file")

    client = get_docker_client()
    container = client.containers.get(container_id)

    tmp_path = f"/tmp/{uuid4()}"

    if host_file is not None:
        docker_cp_to_container(container_id, host_file, tmp_path)
    else:
        container.exec_run(
            ["bash", "-c", f"cat > {tmp_path} << 'CRED_EOF'\n{content}\nCRED_EOF"],
        )

    container.exec_run(["ln", "-sf", tmp_path, link_path])
    return tmp_path


@runtime_checkable
class APIKeyManager(Protocol):
    """Protocol for API key managers with budget tracking."""

    @property
    def api_base_url(self) -> str: ...

    def generate_api_key(self, max_budget: float | None = None) -> str: ...

    def get_api_key_usage(self, api_key: str) -> dict: ...

    def delete_api_key(self, api_key: str) -> None: ...

    def revoke_all(self) -> None: ...


class LiteLLMAPIKeyManager:
    def __init__(
        self,
        litellm_base_url: str,
        litellm_master_key: str,
        litellm_user_id: str | None = None,
        litellm_team_id: str | None = None,
        default_max_budget: float = 5.0,
        api_key_alias_prefix: str = "rmit-",
    ):
        self.default_max_budget = default_max_budget
        self.litellm_base_url = litellm_base_url
        self.litellm_master_key = litellm_master_key
        self.litellm_user_id = litellm_user_id
        self.litellm_team_id = litellm_team_id
        self.api_key_alias_prefix = api_key_alias_prefix
        self._alive_keys: set[str] = set()
        self._deleted_keys: set[str] = set()

    @property
    def api_base_url(self) -> str:
        return self.litellm_base_url

    def generate_api_key(self, max_budget: float | None = None) -> str:
        logger.info(
            "Generating LiteLLM API key with max_budget=%.2f",
            max_budget or self.default_max_budget,
        )
        params = {
            "max_budget": max_budget or self.default_max_budget,
            "key_alias": self.api_key_alias_prefix + str(uuid4()),
            "allowed_routes": ["llm_api_routes"],
        }
        if self.litellm_user_id:
            params["user_id"] = self.litellm_user_id
        if self.litellm_team_id:
            params["team_id"] = self.litellm_team_id
        with httpx.Client(base_url=self.litellm_base_url, timeout=60) as client:
            response = client.post(
                "/key/generate",
                json=params,
                headers={"Authorization": f"Bearer {self.litellm_master_key}"},
            )
            response.raise_for_status()
            data = response.json()
            key = data["key"]
            self._alive_keys.add(key)
            logger.info("Successfully generated API key")
            return key

    def delete_api_key(self, api_key: str):
        logger.info("Deleting LiteLLM API key")
        with httpx.Client(base_url=self.litellm_base_url, timeout=60) as client:
            response = client.post(
                "/key/delete",
                json={"keys": [api_key]},
                headers={"Authorization": f"Bearer {self.litellm_master_key}"},
            )
            response.raise_for_status()
        self._alive_keys.discard(api_key)
        self._deleted_keys.add(api_key)
        logger.info("API key deleted successfully")

    def revoke_all(self):
        """Delete all alive keys tracked by this manager."""
        keys = list(self._alive_keys)
        if not keys:
            return
        logger.info("Revoking %d alive API key(s)", len(keys))
        for key in keys:
            try:
                self.delete_api_key(key)
            except Exception as e:
                logger.warning("Failed to revoke API key: %s", e)

    def get_api_key_usage(self, api_key: str) -> dict:
        logger.info("Fetching API key usage information")
        with httpx.Client(base_url=self.litellm_base_url, timeout=60) as client:
            response = client.get(
                "/key/info",
                params={"key": api_key},
                headers={"Authorization": f"Bearer {self.litellm_master_key}"},
            )
            response.raise_for_status()
            data = response.json()["info"]
            logger.info("Retrieved API key usage: spend=%.2f", data.get("spend", 0.0))
            return data
