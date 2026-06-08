import logging
import shutil
from pathlib import Path

from cybergym.task.metadata import (
    KERNEL_TASK_METADATA,
    KernelDefenseCapability,
    KernelTaskMetadata,
    bitmap_to_env,
    capabilities_to_bitmap,
)
from cybergym.task.workspace.utils import TASK_DATA_DIR, render_template

logger = logging.getLogger(__name__)


def _copy_paths(task_data_dir: Path, paths: list[str], workspace_dir: Path) -> bool:
    """Copy each entry in ``paths`` (relative to ``task_data_dir``) into
    ``workspace_dir`` by basename. Returns True if at least one path copied."""
    copied_any = False
    for rel in paths:
        rel_clean = rel.rstrip("/")
        src = task_data_dir / rel_clean
        dest = workspace_dir / Path(rel_clean).name
        if src.is_file():
            shutil.copy(src, dest)
            logger.info("Copied %s -> %s", src, dest)
            copied_any = True
        elif src.is_dir():
            shutil.copytree(src, dest)
            logger.info("Copied %s -> %s", src, dest)
            copied_any = True
        else:
            logger.warning("Task file not found: %s", src)
    return copied_any


def _description_for(meta: KernelTaskMetadata) -> str:
    """Short human-readable description per subset."""
    raw = meta.raw_metadata or {}
    if patch_title := raw.get("patch_commit_title", ""):
        return patch_title
    if meta.subset == "syzbot":
        return raw.get("title", "")
    return ""


def _vulnerability_doc_paths(
    meta: KernelTaskMetadata, task_data_dir: Path
) -> list[str]:
    """Return vulnerability docs to expose in the workspace.

    Older syzbot metadata does not list docs/vulnerability.md, but those task
    directories now carry the same high-level summary file as kernelctf tasks.
    """
    if meta.files.vulnerability_doc:
        return meta.files.vulnerability_doc
    if meta.subset == "syzbot" and (task_data_dir / "docs/vulnerability.md").is_file():
        return ["docs/vulnerability.md"]
    return []


def prepare_workspace_kernel(
    task_id: str,
    workspace_dir: Path,
    controller_url: str,
    agent_id: str,
    agent_token: str,
    include_vulnerability_doc: bool = True,
    include_exploit_doc: bool = False,
    include_exploit: bool = False,
    include_pov: bool = False,
    include_patch: bool = False,
    defense_capabilities: list[KernelDefenseCapability] | None = None,
) -> str:
    meta = KERNEL_TASK_METADATA[task_id]
    task_data_dir = TASK_DATA_DIR / "kernel" / meta.entry_name

    if not task_data_dir.is_dir():
        logger.info("No task data found at %s", task_data_dir)

    vulnerability_doc_paths = _vulnerability_doc_paths(meta, task_data_dir)
    copy_plan = [
        ("vulnerability_doc", include_vulnerability_doc, vulnerability_doc_paths),
        ("exploit_doc", include_exploit_doc, meta.files.exploit_doc),
        ("exploit", include_exploit, meta.files.exploit),
        ("pov", include_pov, meta.files.pov),
        ("patch", include_patch, meta.files.patch),
    ]
    copied: dict[str, bool] = {}
    for name, include, paths in copy_plan:
        copied[name] = bool(
            include and paths and task_data_dir.is_dir()
        ) and _copy_paths(task_data_dir, paths, workspace_dir)

    raw = meta.raw_metadata or {}
    original_caps = list(raw.get("original_capabilities", []) or [])
    caps: list[KernelDefenseCapability] = (
        list(defense_capabilities)
        if defense_capabilities is not None
        else original_caps
    )
    defense_bitmap = capabilities_to_bitmap(caps)

    run_vm_content = render_template(
        "kernel_run_vm.sh.j2",
        env=bitmap_to_env(defense_bitmap),
        hostname="exphost",
        qemu_extra_args=meta.qemu_extra_args,
        kernel_cmdline_extra=meta.kernel_cmdline_extra,
    )
    run_vm_dest = workspace_dir / "run_vm.sh"
    run_vm_dest.write_text(run_vm_content)
    run_vm_dest.chmod(0o755)

    readme_content = render_template(
        "kernel.md.j2",
        controller_url=controller_url,
        agent_id=agent_id,
        token=agent_token,
        subset=meta.subset,
        description=_description_for(meta),
        capabilities=caps,
        requires_kaslr_leak="nokaslr" in caps,
        **copied,
    )

    (workspace_dir / "README.md").write_text(readme_content)
    return readme_content
