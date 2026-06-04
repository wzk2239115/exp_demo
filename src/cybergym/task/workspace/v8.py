import logging
import shutil
from pathlib import Path

from cybergym.task.metadata import V8_TASK_METADATA
from cybergym.task.workspace.utils import TASK_DATA_DIR, render_template

logger = logging.getLogger(__name__)


def _copy_task_data(entry_name: str, workspace_dir: Path, include_extra: bool) -> None:
    """Copy pov/ directory into workspace.

    entry_name format: "pwncollege/cve-2020-6418-real" or "sbxbrk/385775375"
    """
    task_data_dir = TASK_DATA_DIR / "v8" / entry_name
    if not task_data_dir.is_dir():
        logger.info("No task data found at %s", task_data_dir)
        return

    pov_dir = task_data_dir / "pov"
    if pov_dir.is_dir():
        shutil.copytree(pov_dir, workspace_dir / "pov")
        logger.info("Copied pov/ to workspace")

    # always copy the hidden .extra/, for debugging only
    extra_dir = task_data_dir / ".extra"
    if extra_dir.is_dir() and include_extra:
        shutil.copytree(extra_dir, workspace_dir / ".extra")
        logger.info("Copied .extra/ to workspace")


def prepare_workspace_v8(
    task_id: str,
    workspace_dir: Path,
    controller_url: str,
    agent_id: str,
    agent_token: str,
    request_writeup: bool = False,
    include_extra: bool = False,
    no_sandbox: bool = False,
) -> str:
    task_meta = V8_TASK_METADATA[task_id]

    _copy_task_data(task_meta.entry_name, workspace_dir, include_extra=include_extra)

    readme_content = render_template(
        "v8.md.j2",
        controller_url=controller_url,
        agent_id=agent_id,
        token=agent_token,
        request_writeup=request_writeup,
        no_sandbox=no_sandbox,
    )

    (workspace_dir / "README.md").write_text(readme_content)
    return readme_content
