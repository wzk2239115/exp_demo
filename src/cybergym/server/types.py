from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cybergym.task.token import DEFAULT_FLAG_SEED, DEFAULT_SALT

DEFAULT_API_KEY = "cybergym-030a0cd7-5908-4862-8ab9-91f2bfc7b56d"
API_KEY_NAME = "X-API-Key"


class ContainerResources(BaseModel):
    """Resource budget for a launched verification container.

    Fields map directly to ``docker.containers.run(...)`` kwargs. A field
    left as ``None`` leaves Docker's default (i.e. unlimited) in place, so a
    partially-specified budget only caps the dimensions you set.
    """

    mem_limit: str | None = None
    """Hard memory cap (e.g. ``"5g"``, ``"512m"``)."""

    memswap_limit: str | None = None
    """Total memory + swap cap. Set equal to ``mem_limit`` to disable swap so
    an over-budget container is OOM-killed instead of swapping the host."""

    nano_cpus: int | None = None
    """CPU quota in nano-CPUs (1 CPU = 1_000_000_000)."""

    pids_limit: int | None = None
    """Max number of processes in the container (fork-bomb guard)."""

    shm_size: str | None = None
    """Size of ``/dev/shm`` (e.g. ``"256m"``)."""

    def to_run_kwargs(self) -> dict:
        """Return the subset of ``containers.run`` kwargs that are set."""
        mapping = {
            "mem_limit": self.mem_limit,
            "memswap_limit": self.memswap_limit,
            "nano_cpus": self.nano_cpus,
            "pids_limit": self.pids_limit,
            "shm_size": self.shm_size,
        }
        return {k: v for k, v in mapping.items() if v is not None}


# Per-type budgets live as subclasses so the field *defaults* travel with the
# type annotation. This matters for env overrides: pydantic-settings rebuilds
# a nested model from the annotated type's field defaults, so setting one knob
# (e.g. ``CYBERGYM_SERVER_KERNEL_RESOURCES__MEM_LIMIT=10g``) preserves the
# other caps instead of resetting them to ``None``.


class KernelContainerResources(ContainerResources):
    """Budget for a kernel verification container (runs a QEMU VM:
    ``-m 3.5G``, ``-smp cores=2``), so it gets the most headroom."""

    mem_limit: str | None = "8g"
    memswap_limit: str | None = "8g"
    nano_cpus: int | None = 4_000_000_000
    pids_limit: int | None = 65536


class V8ContainerResources(ContainerResources):
    """Budget for a v8 verification container (a single d8 target behind
    socat; d8 can spike while processing a malicious payload)."""

    mem_limit: str | None = "8g"
    memswap_limit: str | None = "8g"
    nano_cpus: int | None = 4_000_000_000
    pids_limit: int | None = 65536


class UserContainerResources(ContainerResources):
    """Budget for a binary-exploitation verification container (a single
    target binary behind socat)."""

    mem_limit: str | None = "8g"
    memswap_limit: str | None = "8g"
    nano_cpus: int | None = 4_000_000_000
    pids_limit: int | None = 65536


class ServerConfig(BaseSettings):
    """Server configuration with defaults that can be overridden by environment variables or arguments."""

    salt: str = DEFAULT_SALT
    host: str = "127.0.0.1"
    port: int = 8666
    flag_seed: str = DEFAULT_FLAG_SEED
    log_dir: Path = Path("./logs")

    api_key: str = Field(
        default=DEFAULT_API_KEY,
        description="API key for authentication",
    )

    network: str | None = Field(
        default=None,
        description="Docker network name for task containers (e.g. cybergym-internal for proxy enforcement)",
    )

    # Per-task-type resource budgets for launched verification containers.
    # Defaults live on the typed subclasses above; override any single field
    # via env, e.g. ``CYBERGYM_SERVER_KERNEL_RESOURCES__MEM_LIMIT=10g`` (the
    # other caps are preserved).
    kernel_resources: KernelContainerResources = KernelContainerResources()
    v8_resources: V8ContainerResources = V8ContainerResources()
    user_resources: UserContainerResources = UserContainerResources()

    model_config = SettingsConfigDict(
        env_prefix="CYBERGYM_SERVER_", env_nested_delimiter="__"
    )


class ServerRequest(BaseModel):
    """Identity payload used by /create_server, /delete_server, /restart_server, /health_check."""

    agent_id: str
    token: str


class RunCommandRequest(ServerRequest):
    command: list[str]


class ServerInfo(BaseModel):
    """Response returned by /create_server and /restart_server."""

    agent_id: str
    ip: str
    port: int
    created_at: float  # unix timestamp


class ServerHealthResponse(BaseModel):
    """Response returned by /health_check."""

    agent_id: str
    status: str  # "running", "not_found"
    ip: str | None = None
    port: int | None = None
    uptime_seconds: float | None = None
