import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from typing import Any, TextIO

from cybergym.evaluation.agents.stream_renderer_utils import iter_stream_lines


def short(value: Any, limit: int = 220) -> str:
    text = re.sub(r"[\r\n]+", " ", "" if value is None else str(value))
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def emit(text: str, out: TextIO = sys.stdout) -> None:
    out.write(text)
    if not text.endswith("\n"):
        out.write("\n")
    out.flush()


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _render_command(command: str, verbose: bool) -> list[str]:
    if verbose:
        cmd_lines = command.splitlines() or [""]
        lines = ["  $ " + cmd_lines[0]]
        lines.extend("    " + cl for cl in cmd_lines[1:])
        return lines
    return [f"  $ {short(command, limit=500)}"]


def _render_output(output: str, verbose: bool) -> list[str]:
    if not output:
        return []
    if verbose:
        return [output]
    return [short(output, limit=500)]


def _render_todo(items: list[Any]) -> list[str]:
    lines = ["[todo]"]
    for entry in items:
        entry = _as_mapping(entry)
        mark = "x" if entry.get("completed") else " "
        text = _render_value(entry.get("text", ""))
        lines.append(f"  [{mark}] {short(text, limit=300)}")
    return lines


def _render_changes(changes: list[Any]) -> str:
    parts = []
    for change in changes:
        change = _as_mapping(change)
        kind = change.get("kind", "?")
        path = change.get("path", "?")
        parts.append(f"{kind} {path}")
    return ", ".join(parts) or "no-changes"


def render_event_line(raw_line: str, verbose: bool = False) -> list[str]:
    line = raw_line.strip()
    if not line:
        return []

    # Plain text lines (e.g. "Reading prompt from stdin...")
    if not line.startswith("{"):
        return [line]

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return [line]

    event = _as_mapping(event)
    event_type = event.get("type")

    if event_type == "thread.started":
        return [f"[init] thread={event.get('thread_id', '?')}"]

    if event_type == "turn.started":
        return []

    if event_type == "turn.completed":
        usage = _as_mapping(event.get("usage"))
        if usage:
            return [f"[turn-completed] {short(_render_value(usage), limit=300)}"]
        return ["[turn-completed]"]

    if event_type == "error":
        message = event.get("message") or event.get("error") or event
        return [f"[error] {short(_render_value(message), limit=500)}"]

    item = _as_mapping(event.get("item"))
    item_type = item.get("type")

    if item_type == "agent_message":
        # The message is fully available when item.completed arrives;
        # item.started (if ever emitted) has no text.
        if event_type != "item.completed":
            return []
        text = _render_value(item.get("text", ""))
        if not text:
            return []
        if verbose:
            return [text]
        return [text if len(text) <= 2000 else short(text, limit=2000)]

    if item_type == "command_execution":
        command = _render_value(item.get("command", ""))
        if event_type == "item.started":
            lines = ["[tool:bash]"]
            lines.extend(_render_command(command, verbose))
            return lines
        if event_type == "item.completed":
            exit_code = item.get("exit_code")
            status = item.get("status", "")
            output = _render_value(item.get("aggregated_output", ""))
            is_error = status == "failed" or (
                isinstance(exit_code, int) and exit_code != 0
            )
            header = "[tool-error]" if is_error else "[tool-result]"
            if exit_code is not None:
                header = f"{header} exit={exit_code}"
            lines = [header]
            lines.extend(_render_output(output, verbose))
            return lines
        return []

    if item_type == "file_change":
        changes = item.get("changes") or []
        summary = _render_changes(changes if isinstance(changes, list) else [])
        if event_type == "item.started":
            return [f"[file-change:start] {summary}"]
        if event_type == "item.completed":
            status = item.get("status", "")
            marker = (
                "[file-change:failed]" if status == "failed" else "[file-change:done]"
            )
            return [f"{marker} {summary}"]
        return [f"[file-change:update] {summary}"]

    if item_type == "todo_list":
        items = item.get("items") or []
        if not isinstance(items, list):
            items = []
        return _render_todo(items)

    # Unknown event — render compactly so nothing is lost silently.
    label = event_type or "?"
    if item_type:
        label = f"{label}:{item_type}"
    return [f"[{label}] {short(_render_value(event), limit=300)}"]


def render_stream(
    inp: Iterable[str | bytes] | TextIO = sys.stdin,
    out: TextIO = sys.stdout,
    verbose: bool = False,
    on_chunk: Callable[[str], None] | None = None,
) -> None:
    for raw_line in iter_stream_lines(inp, on_chunk=on_chunk):
        try:
            rendered_lines = render_event_line(raw_line, verbose=verbose)
        except Exception as exc:
            rendered_lines = [
                f"[render-error] {type(exc).__name__}: {exc}",
                short(raw_line, limit=500),
            ]
        for rendered in rendered_lines:
            emit(rendered, out)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Render Codex JSON stream")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show full content without truncation",
    )
    args = parser.parse_args()
    render_stream(verbose=args.verbose)


if __name__ == "__main__":
    main()
