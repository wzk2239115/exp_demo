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
    """Indent each line of text with prefix."""
    return "\n".join(prefix + line for line in text.splitlines())


def emit(text: str, out: TextIO = sys.stdout) -> None:
    out.write(text)
    if not text.endswith("\n"):
        out.write("\n")
    out.flush()


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_content_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def render_event_line(raw_line: str, verbose: bool = False) -> list[str]:
    line = raw_line.strip()
    if not line:
        return []

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return [line]

    event = _as_mapping(event)
    event_type = event.get("type")

    if event_type == "system" and event.get("subtype") == "init":
        return [f"[init] model={event.get('model', '?')} cwd={event.get('cwd', '?')}"]

    if event_type == "rate_limit_event":
        info = _as_mapping(event.get("rate_limit_info"))
        return [f"[rate-limit] status={info.get('status', '?')}"]

    message = _as_mapping(event.get("message"))
    content = _as_content_list(message.get("content"))
    first = content[0] if content and isinstance(content[0], dict) else {}
    first_type = first.get("type", "")

    if event_type == "assistant" and first_type == "thinking":
        thinking = first.get("thinking", "")
        if verbose:
            return ["[thinking]", indent(thinking)]
        return ["[thinking] " + short(thinking)]

    if event_type == "assistant" and first_type == "tool_use":
        tool_name = first.get("name", "?")
        raw_tool_input = first.get("input")
        tool_input = _as_mapping(raw_tool_input)
        lines = []
        desc = _render_value(tool_input.get("description", ""))
        command = _render_value(tool_input.get("command", ""))
        if verbose:
            if desc:
                lines.append(f"[tool:{tool_name}] {desc}")
            else:
                lines.append(f"[tool:{tool_name}]")
            if command:
                cmd_lines = command.splitlines()
                lines.append("  $ " + cmd_lines[0])
                for cl in cmd_lines[1:]:
                    lines.append("    " + cl)
        else:
            if desc and command:
                lines.append(f"[tool:{tool_name}] {short(desc)}")
                lines.append(f"  $ {short(command, limit=500)}")
            elif command:
                lines.append(f"[tool:{tool_name}] $ {short(command, limit=500)}")
            elif desc:
                lines.append(f"[tool:{tool_name}] {short(desc)}")
            else:
                if tool_input:
                    summary = " ".join(
                        f"{k}={short(v, limit=100)}" for k, v in tool_input.items()
                    )
                else:
                    summary = short(_render_value(raw_tool_input), limit=200)
                lines.append(f"[tool:{tool_name}] {summary or 'no-input'}")
        return lines

    if event_type == "user" and first_type == "tool_result":
        result_text = first.get("content")
        if not isinstance(result_text, str):
            result_text = _render_value(result_text or event.get("tool_use_result", ""))
        marker = "[tool-error]" if first.get("is_error") else "[tool-result]"
        return [marker, result_text]

    if event_type == "assistant":
        text_blocks = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        ]
        if text_blocks:
            return ["\n".join(text_blocks)]

    return []


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

    parser = argparse.ArgumentParser(description="Render Claude Code JSON stream")
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
