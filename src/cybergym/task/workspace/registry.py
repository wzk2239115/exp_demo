from enum import StrEnum
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Literal, overload

from cybergym.task.workspace.kernel import prepare_workspace_kernel
from cybergym.task.workspace.user import USER_TASK, prepare_workspace_user
from cybergym.task.workspace.v8 import prepare_workspace_v8


def _infer_required_arguments(fn: Callable) -> list[str]:
    """Infer the argument names of the function."""

    sig = signature(fn)
    required_args = [
        param.name
        for param in sig.parameters.values()
        if param.default == param.empty
        and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    ]
    return required_args


type PrepareWorkspaceFn = Callable[..., str]
type TaskDispatcherEntry = tuple[PrepareWorkspaceFn, list[str]]


class TaskType(StrEnum):
    USER_EXPLOITATION = "USER_EXPLOITATION"
    V8_EXPLOITATION = "V8_EXPLOITATION"
    KERNEL_EXPLOITATION = "KERNEL_EXPLOITATION"


TASK_DISPATCHER: dict[TaskType, TaskDispatcherEntry] = {
    TaskType.USER_EXPLOITATION: (
        prepare_workspace_user,
        _infer_required_arguments(prepare_workspace_user),
    ),
    TaskType.V8_EXPLOITATION: (
        prepare_workspace_v8,
        _infer_required_arguments(prepare_workspace_v8),
    ),
    TaskType.KERNEL_EXPLOITATION: (
        prepare_workspace_kernel,
        _infer_required_arguments(prepare_workspace_kernel),
    ),
}


@overload
def prepare_workspace(
    task_type: Literal[TaskType.USER_EXPLOITATION],
    task_id: str,
    workspace_dir: Path,
    *,
    controller_url: str,
    target: USER_TASK,
    agent_id: str,
    agent_token: str,
    request_writeup: bool = False,
) -> str: ...


@overload
def prepare_workspace(
    task_type: Literal[TaskType.V8_EXPLOITATION],
    task_id: str,
    workspace_dir: Path,
    *,
    controller_url: str,
    agent_id: str,
    agent_token: str,
    request_writeup: bool = False,
    include_extra: bool = False,
    no_sandbox: bool = False,
) -> str: ...


@overload
def prepare_workspace(
    task_type: Literal[TaskType.KERNEL_EXPLOITATION],
    task_id: str,
    workspace_dir: Path,
    *,
    controller_url: str,
    agent_id: str,
    agent_token: str,
    include_vulnerability_doc: bool = True,
    include_exploit_doc: bool = False,
    include_exploit: bool = False,
    include_pov: bool = False,
    include_patch: bool = False,
    defense_capabilities: list[str] | None = None,
) -> str: ...


def prepare_workspace(
    task_type: TaskType, task_id: str, workspace_dir: Path, **kwargs: Any
) -> str:
    if task_type not in TASK_DISPATCHER:
        raise ValueError(f"Unknown task type: {task_type}")

    fn, required_args = TASK_DISPATCHER[task_type]
    kwargs["task_id"] = task_id
    kwargs["workspace_dir"] = workspace_dir
    missing_args = [arg for arg in required_args if arg not in kwargs]

    if missing_args:
        raise ValueError(f"Missing required arguments: {missing_args}")

    return fn(**kwargs)
