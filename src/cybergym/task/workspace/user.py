import logging
from pathlib import Path
from typing import Literal

from cybergym.task.metadata import TASK_METADATA
from cybergym.task.workspace.utils import add_reference_poc_cybergym, render_template

logger = logging.getLogger(__name__)

USER_TASK = Literal["READ", "EXEC"]


def prepare_workspace_user(
    task_id: str,
    workspace_dir: Path,
    controller_url: str,
    target: USER_TASK,
    agent_id: str,
    agent_token: str,
    request_writeup: bool = False,
    **kwargs,
) -> str:
    """Based on the task target, prepare the workspace for the task, including the README.md, run.sh"""
    task_meta = TASK_METADATA[task_id]

    run_sh_content = render_template(
        "rwx_run.sh.j2", binary_path=f"/out/{task_meta.binary}"
    )
    (workspace_dir / "run.sh").write_text(run_sh_content)

    poc_description = add_reference_poc_cybergym(task_id, workspace_dir)

    readme_content = render_template(
        "user.md.j2",
        target=target,
        project_name=task_meta.project_name,
        binary_path=f"/out/{task_meta.binary}",
        server_url=controller_url,
        agent_id=agent_id,
        token=agent_token,
        poc_description=poc_description,
        request_writeup=request_writeup,
    )

    (workspace_dir / "README.md").write_text(readme_content)

    return readme_content
