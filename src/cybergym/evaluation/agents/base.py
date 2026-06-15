"""Agent abstraction: a paired install + run unit.

An :class:`Agent` bundles two phases the evaluator drives:

* :meth:`Agent.install` — runs *before* the agent, with network access (via the
  allow-all install proxy when the firewall is enabled). Override it to install
  whatever this agent needs for the given task; it receives the task id and type
  so installs can differ per agent *and* per task. Enable it for a task by
  overriding :meth:`Agent.has_install_phase` to return True.
* :meth:`Agent.run` — runs the agent itself against the prepared container.
"""

from abc import ABC, abstractmethod

from docker.models.containers import Container

from cybergym.evaluation.types import AgentFnArguments
from cybergym.task.workspace import TaskType


class Agent(ABC):
    """Base class for runnable agents."""

    @abstractmethod
    def run(self, args: AgentFnArguments) -> None:
        """Run the agent against the prepared container.

        ``args`` carries the task description, container id, resolved API key /
        base URL, firewall env, etc. (see :class:`AgentFnArguments`).
        """

    def install(
        self,
        container: Container,
        *,
        env: dict[str, str] | None,
        task_id: str,
        task_type: TaskType,
    ) -> None:
        """Install dependencies in *container* before the agent runs.

        Default: no-op. Override to install whatever this agent needs for the
        given task; branch on *task_id* / *task_type* for per-task differences.
        Runs only when :meth:`has_install_phase` returns True for the task: the
        evaluator then routes the container through the allow-all install proxy
        while this runs, then locks it back down to the API-only run network
        before :meth:`run`.

        *env* carries the install proxy's environment variables (``HTTP_PROXY``
        etc.) when the firewall is enabled; pass it through to
        ``container.exec_run(..., environment=env)`` so commands here can reach
        the network.
        """

    def has_install_phase(self, task_type: TaskType) -> bool:
        """Whether this agent runs an install phase for *task_type*.

        Default: False (no install phase). Override to enable it for the tasks
        this agent needs to install for.
        """
        return False
