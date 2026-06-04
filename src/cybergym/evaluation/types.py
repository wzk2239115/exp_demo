from pathlib import Path
from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, Field, SecretStr

from cybergym.task.metadata import KernelDefenseCapability
from cybergym.task.workspace import TaskType
from cybergym.task.workspace.user import USER_TASK
from cybergym.utils import DATA_DIR

type JSONValue = Any


class BaseTaskExtraKwargs(TypedDict, total=False):
    request_writeup: bool
    agent_id: str
    agent_token: str


class UserTaskExtraKwargs(BaseTaskExtraKwargs):
    controller_url: str
    target: USER_TASK
    image_mode: NotRequired[str]


class V8TaskExtraKwargs(BaseTaskExtraKwargs):
    controller_url: str
    include_extra: NotRequired[bool]
    no_sandbox: NotRequired[bool]


class KernelTaskExtraKwargs(BaseTaskExtraKwargs):
    controller_url: str
    include_vulnerability_doc: NotRequired[bool]
    include_exploit_doc: NotRequired[bool]
    include_exploit: NotRequired[bool]
    include_pov: NotRequired[bool]
    include_patch: NotRequired[bool]
    defense_capabilities: NotRequired[list[KernelDefenseCapability]]


type TaskExtraKwargs = (
    UserTaskExtraKwargs | V8TaskExtraKwargs | KernelTaskExtraKwargs
)


class EvalConfig(BaseModel):
    task_id: str
    task_type: TaskType
    out_dir: Path
    task_extra_kwargs: TaskExtraKwargs | dict[str, Any] = Field(default_factory=dict)
    image_mode: str = "exp.none"
    keep_container: bool = False
    runtime_dir: Path = DATA_DIR / "runtime"
    runtime_dir_in_container: str = "/data"
    workspace_dir_in_container: str = "/workspace"
    agent_timeout_seconds: int = 3600
    agent_extra_kwargs: dict[str, JSONValue] = Field(default_factory=dict)
    api_base_url: str | None = None
    api_key: SecretStr | None = None

    save_workspace_after_eval: bool = True
    """Whether to save the agent's workspace after evaluation.
    Enabled by default (useful for debugging or analysis). To bound disk
    usage, files larger than ``save_workspace_max_file_bytes`` are skipped.
    Set to False to skip saving the workspace entirely."""

    save_workspace_max_file_bytes: int | None = 10 * 1024 * 1024
    """When saving the workspace, drop any file larger than this many bytes
    (default: 10 MiB). This keeps source, scripts, and small PoCs while
    discarding large blobs (compiled binaries, core dumps, corpora). Set to
    None to keep every file regardless of size."""

    credential_path: Path | None = None
    """Optional path to a credential file on the host.

    When provided, the file is docker-cp'd into the container by the agent
    function, and ``api_key`` may be omitted.

    Example::

        credential_path=Path.home() / ".claude" / ".credentials.json"
    """

    task_description_template: str | None = None
    """Optional template for task description. If provided, it will be
    formatted with `{task_description}` which will be replaced by the
    actual task description."""

    use_firewall: bool = False
    """Place the agent container behind the shared firewall proxy.

    When True, the evaluator connects to a running FirewallProxyManager
    instance (started separately via ``python -m cybergym.firewall start``)
    and places the agent container on the internal Docker network.  The
    firewall's domain allowlist is configured at proxy start time, not here.
    """

    container_mem_limit: str | None = "8g"
    """Hard memory cap for the agent container (e.g. ``"8g"``, ``"512m"``).

    Forwarded to ``docker.containers.run(mem_limit=...)``. ``None`` means
    no limit.
    """

    container_nano_cpus: int | None = 4_000_000_000
    """CPU quota in nano-CPUs (1 CPU = 1_000_000_000). Forwarded to
    ``docker.containers.run(nano_cpus=...)``. ``None`` means no limit."""

    container_memswap_limit: str | None = None
    """Total memory + swap cap (e.g. ``"8g"``). Set equal to
    ``container_mem_limit`` to disable swap. Forwarded to ``memswap_limit``."""

    container_pids_limit: int | None = 65536
    """Max number of processes in the container (prevents fork bombs).
    Forwarded to ``docker.containers.run(pids_limit=...)``."""

    container_shm_size: str | None = None
    """Size of ``/dev/shm`` (e.g. ``"1g"``). Forwarded to ``shm_size``."""

    container_storage_size: str | None = None
    """Writable-layer size cap (e.g. ``"10g"``). Forwarded to
    ``storage_opt={"size": ...}``. Requires a storage driver that supports
    per-container quotas (overlay2 on xfs w/ pquota, btrfs, zfs, devicemapper)."""


class CheckResult(BaseModel):
    name: str
    score: float
    # Placeholder for richer analysis (coredump PC value, flag content, etc.)
    details: dict[str, JSONValue] | None = None


class AgentFnArguments(BaseModel):
    task_description: str
    runtime_dir_in_container: str
    agent_timeout_seconds: int
    out_dir: Path
    container_id: str | None = None
    extra_kwargs: dict[str, JSONValue] = Field(default_factory=dict)
    api_base_url: str | None = None
    api_key: str | None = None
    credential_path: Path | None = None
    firewall_env: dict[str, str] | None = None
    """Firewall proxy environment variables (HTTP_PROXY, HTTPS_PROXY, etc.).

    Set automatically by the evaluator when ``use_firewall`` is True.
    Agent runners should merge these into the container environment
    so that tools inside the container respect the firewall proxy.
    """

    disable_web_search: bool = True


class EvalResult(BaseModel):
    task_id: str
    elapsed_time: float = 0.0
    checks: list[CheckResult]
    error: str | None = None
