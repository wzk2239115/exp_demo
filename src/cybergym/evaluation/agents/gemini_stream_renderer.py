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


def _maybe_short(text: str, limit: int, verbose: bool) -> str:
    if verbose:
        return text
    return short(text, limit=limit)


def render_event_line(raw_line: str, verbose: bool = False) -> list[str]:
    line = raw_line.strip()
    if not line:
        return []

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Plain text lines (e.g. "YOLO mode is enabled...")
        return [line]

    event = _as_mapping(event)
    event_type = event.get("type")

    if event_type == "init":
        return [
            f"[init] model={event.get('model', '?')} session={event.get('session_id', '?')}"
        ]

    if event_type == "message":
        role = event.get("role", "?")
        content = _render_value(event.get("content", ""))
        return [f"[{role}] {_maybe_short(content, limit=300, verbose=verbose)}"]

    if event_type == "tool_use":
        tool_name = event.get("tool_name", "?")
        raw_params = event.get("parameters")
        params = _as_mapping(raw_params)
        command = _render_value(params.get("command", ""))
        if command:
            return [
                f"[tool:{tool_name}] $ {_maybe_short(command, limit=500, verbose=verbose)}"
            ]
        if params:
            summary = " ".join(
                f"{k}={_maybe_short(_render_value(v), limit=100, verbose=verbose)}"
                for k, v in params.items()
            )
        else:
            summary = _maybe_short(
                _render_value(raw_params), limit=200, verbose=verbose
            )
        return [f"[tool:{tool_name}] {summary or 'no-params'}"]

    if event_type == "tool_result":
        status = event.get("status", "")
        output = event.get("output", "")
        error = event.get("error", {})
        marker = "[tool-error]" if status == "error" or error else "[tool-result]"
        lines = [marker]
        if error and isinstance(error, Mapping):
            err_text = _render_value(error.get("message", error))
            lines.append(_maybe_short(err_text, limit=500, verbose=verbose))
        elif output:
            out_text = _render_value(output)
            lines.append(_maybe_short(out_text, limit=500, verbose=verbose))
        return lines

    # Unknown event type — render as-is
    return [
        f"[{event_type or '?'}] {_maybe_short(json.dumps(event), limit=300, verbose=verbose)}"
    ]


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

    parser = argparse.ArgumentParser(description="Render Gemini CLI JSON stream")
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
