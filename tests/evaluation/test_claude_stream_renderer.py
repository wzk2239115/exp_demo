import io
import json

from cybergym.evaluation.agents.claude_code import run_claude_code_with_container
from cybergym.evaluation.agents.claude_stream_renderer import (
    emit,
    render_event_line,
    render_stream,
    short,
)
from cybergym.evaluation.types import AgentFnArguments


class TestClaudeStreamRenderer:
    def test_short_normalizes_and_truncates(self):
        text = "line1\nline2\r\n" + ("x" * 230)
        rendered = short(text, limit=20)
        assert rendered == "line1 line2 xxxxxxxx..."

    def test_render_event_line_skips_empty_lines(self):
        assert render_event_line("\n") == []

    def test_render_event_line_passthrough_invalid_json(self):
        assert render_event_line("not-json") == ["not-json"]

    def test_render_system_init(self):
        event = {"type": "system", "subtype": "init", "model": "opus", "cwd": "/w"}
        assert render_event_line(json.dumps(event)) == ["[init] model=opus cwd=/w"]

    def test_render_rate_limit(self):
        event = {
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "cooldown"},
        }
        assert render_event_line(json.dumps(event)) == ["[rate-limit] status=cooldown"]

    def test_render_thinking(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [{"type": "thinking", "thinking": "a\nb\r\nc"}],
            },
        }
        assert render_event_line(json.dumps(event)) == ["[thinking] a b c"]

    def test_render_tool_use_shows_description_and_command(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "bash",
                        "input": {
                            "description": "run\nthing",
                            "command": "echo hello",
                        },
                    }
                ],
            },
        }
        assert render_event_line(json.dumps(event)) == [
            "[tool:bash] run thing",
            "  $ echo hello",
        ]

    def test_render_tool_use_command_only(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "bash",
                        "input": {"command": "echo hi"},
                    }
                ],
            },
        }
        assert render_event_line(json.dumps(event)) == ["[tool:bash] $ echo hi"]

    def test_render_verbose_tool_use(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {
                            "description": "Run exploit",
                            "command": "cd /tmp\n./exploit --flag",
                        },
                    }
                ],
            },
        }
        assert render_event_line(json.dumps(event), verbose=True) == [
            "[tool:Bash] Run exploit",
            "  $ cd /tmp",
            "    ./exploit --flag",
        ]

    def test_render_verbose_thinking(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [{"type": "thinking", "thinking": "line1\nline2"}],
            },
        }
        assert render_event_line(json.dumps(event), verbose=True) == [
            "[thinking]",
            "  line1\n  line2",
        ]

    def test_render_tool_result_success_with_multiline_body(self):
        event = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "is_error": False,
                        "content": "line1\nline2",
                    }
                ],
            },
        }
        assert render_event_line(json.dumps(event)) == ["[tool-result]", "line1\nline2"]

    def test_render_tool_result_error_with_fallback(self):
        event = {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "is_error": True}]},
            "tool_use_result": {"exit_code": 1},
        }
        assert render_event_line(json.dumps(event)) == [
            "[tool-error]",
            '{"exit_code": 1}',
        ]

    def test_render_assistant_text_joins_all_text_blocks(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "part1"},
                    {"type": "thinking", "thinking": "ignore"},
                    {"type": "text", "text": "part2"},
                ]
            },
        }
        assert render_event_line(json.dumps(event)) == ["part1\npart2"]

    def test_render_unknown_event_is_ignored(self):
        event = {"type": "assistant", "message": {"content": [{"type": "image"}]}}
        assert render_event_line(json.dumps(event)) == []

    def test_emit_appends_trailing_newline(self):
        out = io.StringIO()
        emit("hello", out)
        assert out.getvalue() == "hello\n"

    def test_render_stream_processes_multiple_lines(self):
        inp = io.StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "system",
                            "subtype": "init",
                            "model": "sonnet",
                            "cwd": "/workspace",
                        }
                    ),
                    "not-json",
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [{"type": "text", "text": "final answer"}]
                            },
                        }
                    ),
                ]
            )
            + "\n"
        )
        out = io.StringIO()

        render_stream(inp, out)

        assert out.getvalue() == (
            "[init] model=sonnet cwd=/workspace\nnot-json\nfinal answer\n"
        )


class FakeContainer:
    def __init__(self, stream_lines):
        self.stream_lines = stream_lines
        self.calls = []

    def exec_run(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if kwargs.get("stream"):
            return None, iter(self.stream_lines)
        return type("ExecResult", (), {"exit_code": 0, "output": b""})()


class FakeContainers:
    def __init__(self, container):
        self._container = container

    def get(self, container_id):
        assert container_id == "container-123"
        return self._container


class FakeAPI:
    def __init__(self, stream_lines):
        self._stream_lines = stream_lines
        self.exec_create_calls = []

    def exec_create(self, container_id, cmd, **kwargs):
        self.exec_create_calls.append((container_id, cmd, kwargs))
        return {"Id": "exec-123"}

    def exec_start(self, exec_id, stream=False, socket=False):
        return iter(self._stream_lines)

    def exec_inspect(self, exec_id):
        return {"ExitCode": 0}


class FakeDockerClient:
    def __init__(self, container):
        self.containers = FakeContainers(container)
        self.api = FakeAPI(container.stream_lines)


class TestClaudeCodeRunner:
    def test_runner_writes_rendered_log_and_keeps_raw_tee(self, monkeypatch, tmp_path):
        init_event = json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-opus",
                "cwd": "/workspace",
            }
        )
        text_event = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "exploit summary"}]},
            }
        )
        stream_lines = [
            (init_event + "\n" + text_event[:35]).encode(),
            (text_event[35:] + "\n").encode(),
        ]
        fake_container = FakeContainer(stream_lines)
        fake_client = FakeDockerClient(fake_container)

        # Patch the imported get_docker_client (not docker.from_env): the real
        # get_docker_client is @lru_cache'd, so feeding it a fake via from_env
        # would poison the cache for every later test (e.g. integration tests
        # that need a real client).
        monkeypatch.setattr(
            "cybergym.evaluation.agents.claude_code.get_docker_client",
            lambda: fake_client,
        )

        args = AgentFnArguments(
            task_description="solve it",
            runtime_dir_in_container="/data",
            agent_timeout_seconds=30,
            out_dir=tmp_path,
            container_id="container-123",
            extra_kwargs={"claude_model": "claude-opus"},
            api_base_url="https://example.test",
            api_key="secret",
        )

        run_claude_code_with_container(args)

        rendered_log = tmp_path / "logs" / "claude_code.rendered.log"
        assert rendered_log.exists()
        assert rendered_log.read_text() == (
            "[init] model=claude-opus cwd=/workspace\nexploit summary\n"
        )

        # Verify the streaming exec was created via low-level API
        assert len(fake_client.api.exec_create_calls) == 1
        _, cmd, kwargs = fake_client.api.exec_create_calls[0]
        assert "/logs/claude_code.log" in cmd[2]
