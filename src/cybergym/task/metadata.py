import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TaskMetadata(BaseModel):
    """Metadata for a user/cybergym binary exploitation task.

    entry_name is scoped by subset, e.g. "cybergym/arvo_1461" or
    "cybergym/oss-fuzz_42538616". task_id is hash("user:" + entry_name)
    → "user:<12hex>".
    """

    task_id: str
    entry_name: str
    project_name: str
    binary: str
    env: dict[str, str]
    images: dict[str, str]  # mode -> image name
    extra_files: list[str] = Field(default_factory=list)


class V8TaskMetadata(BaseModel):
    task_id: str
    entry_name: str
    image: str | None = None
    image_no_sandbox: str | None = None
    revision: str
    has_allow_natives_syntax: bool
    v8_sandbox_enabled: bool
    maglev_enabled: bool
    is_sandbox_escape: bool


type KernelDefenseCapability = Literal[
    "nokaslr", "nosmep", "nosmap", "userns", "io_uring", "kernelctf_hardening"
]
type KernelDefenseEnvVar = Literal[
    "NOKASLR", "NOSMEP", "NOSMAP", "USERNS", "IO_URING", "HARDENING"
]

# ── Defense config bitmap ──
# Compact encoding of mitigation/capability flags sent to the task handler.
# Each bit controls one feature. Default 0 = all defenses on, no attacker capabilities.
#
#   bit 0 (0x01): nokaslr              - KASLR disabled
#   bit 1 (0x02): nosmep               - SMEP disabled
#   bit 2 (0x04): nosmap               - SMAP disabled
#   bit 3 (0x08): userns               - user namespaces enabled
#   bit 4 (0x10): io_uring             - io_uring enabled
#   bit 5 (0x20): kernelctf_hardening  - hardening sysctls enabled
DEFENSE_FLAG_BITS: dict[KernelDefenseCapability, int] = {
    "nokaslr": 0,
    "nosmep": 1,
    "nosmap": 2,
    "userns": 3,
    "io_uring": 4,
    "kernelctf_hardening": 5,
}


ALL_DEFENSE_FLAGS = list(DEFENSE_FLAG_BITS.keys())


def capabilities_to_bitmap(capabilities: Sequence[KernelDefenseCapability]) -> int:
    """Convert a list of capability/mitigation names to a compact bitmap integer."""
    bitmap = 0
    for cap in capabilities:
        if cap not in DEFENSE_FLAG_BITS:
            raise ValueError(
                f"Unknown capability: {cap!r}. Valid: {', '.join(ALL_DEFENSE_FLAGS)}"
            )
        bitmap |= 1 << DEFENSE_FLAG_BITS[cap]
    return bitmap


def bitmap_to_capabilities(bitmap: int) -> list[KernelDefenseCapability]:
    """Convert a bitmap integer back to a list of capability names."""
    caps = []
    for name, bit in DEFENSE_FLAG_BITS.items():
        if bitmap & (1 << bit):
            caps.append(name)
    return caps


def bitmap_to_env(bitmap: int) -> dict[KernelDefenseEnvVar, str]:
    """Convert a defense bitmap to environment variables for run_qemu.sh.

    Returns a dict of env var name -> "0" or "1" for each flag.
    This is the single place where bitmap is decoded into container env vars.
    """
    return {
        "NOKASLR": str((bitmap >> DEFENSE_FLAG_BITS["nokaslr"]) & 1),
        "NOSMEP": str((bitmap >> DEFENSE_FLAG_BITS["nosmep"]) & 1),
        "NOSMAP": str((bitmap >> DEFENSE_FLAG_BITS["nosmap"]) & 1),
        "USERNS": str((bitmap >> DEFENSE_FLAG_BITS["userns"]) & 1),
        "IO_URING": str((bitmap >> DEFENSE_FLAG_BITS["io_uring"]) & 1),
        "HARDENING": str((bitmap >> DEFENSE_FLAG_BITS["kernelctf_hardening"]) & 1),
    }


class KernelTaskFiles(BaseModel):
    """File pointers for a kernel task entry.

    Each field is a list of repo-relative paths (files or directories). An
    empty list means the asset is not present for this task.
    """

    vulnerability_doc: list[str] = Field(default_factory=list)
    exploit_doc: list[str] = Field(default_factory=list)
    exploit: list[str] = Field(default_factory=list)
    pov: list[str] = Field(default_factory=list)
    patch: list[str] = Field(default_factory=list)


class KernelTaskMetadata(BaseModel):
    """Metadata for a kernel task (kernelctf and syzbot subsets).

    entry_name is scoped by subset, e.g. "kernelctf/CVE-..." or "syzbot/<extid>".
    task_id is hash("kernel:" + entry_name) → "kernel:<12hex>".
    """

    task_id: str
    entry_name: str
    image_name: str
    patch_commits: list[str] = Field(default_factory=list)
    files: KernelTaskFiles = Field(default_factory=KernelTaskFiles)
    raw_metadata: dict = Field(default_factory=dict)

    # Per-task VM launch overrides. Empty by default, so tasks that do not set
    # them are launched exactly as before. Used to work around QEMU-environment
    # boot crashes that are specific to a single task's kernel build (e.g. a
    # bochs_drm KMS panic, or a virtio-blk MSI-X NULL-deref) without changing
    # the launch config for every other task.
    #   qemu_extra_args     — extra tokens appended to the qemu-system-x86_64
    #                         command line (e.g. "-vga none").
    #   kernel_cmdline_extra — extra tokens appended to the kernel -append
    #                         cmdline (e.g. "pci=nomsi").
    qemu_extra_args: str = ""
    kernel_cmdline_extra: str = ""

    @property
    def subset(self) -> str:
        """Return the subset name ('kernelctf' or 'syzbot')."""
        return self.entry_name.split("/", 1)[0]


TASK_METADATA: dict[str, TaskMetadata] = {}
V8_TASK_METADATA: dict[str, V8TaskMetadata] = {}
KERNEL_TASK_METADATA: dict[str, KernelTaskMetadata] = {}
SCRIPT_DIR = Path(__file__).parent.absolute()


def load_task_metadata(json_path: str | Path) -> None:
    """Load the user/cybergym metadata file.

    Populates ``TASK_METADATA``, keyed by the hashed ``task_id`` and by
    the ``user:<entry_name>`` alias.
    """
    with open(json_path) as f:
        data = json.load(f)
    for entry in data:
        meta = TaskMetadata.model_validate(entry)
        TASK_METADATA[meta.task_id] = meta
        alias = f"user:{meta.entry_name}"
        if alias != meta.task_id:
            TASK_METADATA[alias] = meta


def _hash_task_id(prefix: str, name: str) -> str:
    """Generate an opaque task ID from a human-readable name."""
    import hashlib

    h = hashlib.sha256(name.encode()).hexdigest()[:12]
    return f"{prefix}:{h}"


def load_v8_metadata(json_path: str | Path) -> None:
    with open(json_path) as f:
        data = json.load(f)
    for entry in data:
        meta = V8TaskMetadata.model_validate(entry)
        # Index by hashed task_id
        V8_TASK_METADATA[meta.task_id] = meta
        # Also index by original name for convenience (e.g. "v8:cve-2020-6418-real")
        original_id = f"v8:{meta.entry_name}"
        if original_id != meta.task_id:
            V8_TASK_METADATA[original_id] = meta


def load_kernel_metadata(json_path: str | Path) -> None:
    """Load the kernel metadata file.

    Populates ``KERNEL_TASK_METADATA``, keyed by the hashed ``task_id`` and by
    the ``kernel:<entry_name>`` alias.
    """
    with open(json_path) as f:
        data = json.load(f)
    for entry in data:
        meta = KernelTaskMetadata.model_validate(entry)
        KERNEL_TASK_METADATA[meta.task_id] = meta
        alias = f"kernel:{meta.entry_name}"
        if alias != meta.task_id:
            KERNEL_TASK_METADATA[alias] = meta


load_task_metadata(SCRIPT_DIR / "metadata.json")
load_v8_metadata(SCRIPT_DIR / "v8_metadata.json")

_kernel_meta = SCRIPT_DIR / "kernel_metadata.json"
if _kernel_meta.exists():
    load_kernel_metadata(_kernel_meta)
