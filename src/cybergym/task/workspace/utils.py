import os
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from cybergym.task.metadata import TASK_METADATA
from cybergym.utils import DATA_DIR

TASK_DATA_DIR = DATA_DIR / "tasks"

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _include_workstyle() -> bool:
    """ORIG_TASK_DESC=1 → use the pristine upstream task description:
    the fork's workstyle/agent-guidance add-ons are skipped, matching
    sunblaze-ucb/exploitgym verbatim. Unset (default) keeps fork behavior."""
    return os.environ.get("ORIG_TASK_DESC", "") != "1"


_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
)
_jinja_env.globals["include_workstyle"] = _include_workstyle()


def render_template(template_name: str, **kwargs) -> str:
    """Render a Jinja2 template from the templates directory."""
    template = _jinja_env.get_template(template_name)
    return template.render(**kwargs)


def add_reference_poc_cybergym(
    task_id: str, workspace_dir: Path | None = None, copy: bool = True
) -> str:
    """Add the reference PoC to the workspace and return the description of the PoC."""
    if workspace_dir is not None and copy:
        task_data_dir = TASK_DATA_DIR / "user" / TASK_METADATA[task_id].entry_name
        poc_path = task_data_dir / "poc"
        shutil.copy(poc_path, workspace_dir / "poc")
        error_log_path = task_data_dir / "output.vul"
        shutil.copy(error_log_path, workspace_dir / "error.txt")
        desc_path = task_data_dir / "description.txt"
        shutil.copy(desc_path, workspace_dir / "description.txt")
    return render_template("_includes/known_vulnerability.md.j2")
