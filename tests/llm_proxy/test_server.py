import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from litellm.proxy.utils import _get_docs_url, _get_openapi_url, _get_redoc_url
from starlette.responses import Response

from cybergym.llm_proxy import server
from cybergym.llm_proxy.budget import BudgetManager


def _make_client(
    manager: BudgetManager,
    master_key: str = "sk-test",
    block_web_search: bool = True,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        server.BudgetAuthMiddleware,
        manager=manager,
        master_key=master_key,
        block_web_search=block_web_search,
    )

    @app.post("/v1/messages")
    @app.post("/models/{model_name:path}:countTokens")
    async def allowed_endpoint(request: Request):
        return JSONResponse(
            {
                "authorization": request.headers.get("authorization"),
                "x_api_key": request.headers.get("x-api-key"),
                "x_goog_api_key": request.headers.get("x-goog-api-key"),
                "api_key": request.headers.get("api-key"),
            }
        )

    @app.post("/budget/check")
    async def budget_endpoint():
        return JSONResponse({"ok": True})

    @app.post("/model/new")
    async def blocked_endpoint():
        return JSONResponse({"ok": True})

    return TestClient(app)


class TestLLMProxyServer:
    def test_docs_env_flags_disable_litellm_docs(self):
        assert server.os.environ["NO_DOCS"] == "true"
        assert server.os.environ["NO_REDOC"] == "true"
        assert server.os.environ["NO_OPENAPI"] == "true"
        assert _get_docs_url() is None
        assert _get_redoc_url() is None
        assert _get_openapi_url() is None

    def test_inference_route_matching(self):
        # Stateless inference routes derived from LiteLLM's openai/anthropic/google lists.
        assert server._is_inference_route("/v1/messages")
        assert server._is_inference_route("/v1/messages/count_tokens")
        assert server._is_inference_route("/v1/responses")
        assert server._is_inference_route("/v1/embeddings")
        assert server._is_inference_route("/v1/audio/transcriptions")
        assert server._is_inference_route("/v1/images/generations")
        assert server._is_inference_route("/v1/moderations")
        assert server._is_inference_route("/v1/rerank")
        assert server._is_inference_route("/models/gemini-2.5-pro:countTokens")
        assert server._is_inference_route(
            "/v1beta/models/gemini-2.5-pro:generateContent"
        )

        # Provider pass-through prefixes.
        assert server._is_inference_route("/openai/v1/responses")
        assert server._is_inference_route("/anthropic/v1/messages")
        assert server._is_inference_route("/vertex_ai/v1/chat/completions")
        assert server._is_inference_route("/bedrock/model/anthropic.claude-3/invoke")
        assert server._is_inference_route("/gemini/v1beta/models/x:generateContent")

        # Admin / MCP / stateful / non-inference routes stay blocked.
        assert not server._is_inference_route("/model/new")
        assert not server._is_inference_route("/guardrails/test_custom_code")
        assert not server._is_inference_route("/mcp-rest/test/connection")
        assert not server._is_inference_route("/mcp-rest/tools/call")
        assert not server._is_inference_route("/v1/mcp/server")
        assert not server._is_inference_route("/v1/batches")
        assert not server._is_inference_route("/v1/files")
        assert not server._is_inference_route("/v1/assistants")
        assert not server._is_inference_route("/v1/threads/abc/messages")
        assert not server._is_inference_route("/v1/realtime")
        assert not server._is_inference_route("/v1/containers")
        assert not server._is_inference_route("/v1/skills")
        assert not server._is_inference_route("/interactions")
        # Bare provider prefix without a subpath is not a real LiteLLM route.
        assert not server._is_inference_route("/anthropic")

    def test_budget_route_requires_admin_key(self, monkeypatch):
        monkeypatch.setattr(server, "_admin_key", "cgym-admin-test")
        client = _make_client(BudgetManager())

        response = client.post("/budget/check")
        assert response.status_code == 401
        assert response.json()["error"]["type"] == "auth_error"

        response = client.post(
            "/budget/check", headers={"x-admin-key": "cgym-admin-test"}
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_non_inference_route_is_forbidden_before_forwarding(self):
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager)

        response = client.post("/model/new", headers={"authorization": f"Bearer {key}"})
        assert response.status_code == 403
        assert response.json()["error"]["type"] == "forbidden_route"

    def test_budget_exhaustion_returns_429(self):
        manager = BudgetManager(default_max_budget=1.0)
        key = manager.generate_key(max_budget=1.0)
        manager.record_usage(key, "openai/gpt-5.4", {}, cost=1.0)
        client = _make_client(manager)

        response = client.post(
            "/v1/messages", headers={"authorization": f"Bearer {key}"}
        )
        assert response.status_code == 429
        assert response.json()["error"]["type"] == "budget_exceeded"

    def test_missing_key_returns_401(self):
        client = _make_client(BudgetManager())
        response = client.post("/v1/messages")
        assert response.status_code == 401
        assert response.json()["error"] == "Missing API key"

    def test_extract_api_key_header_precedence(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/messages",
                "headers": [
                    (b"x-api-key", b"anthropic-key"),
                    (b"x-goog-api-key", b"google-key"),
                    (b"api-key", b"generic-key"),
                    (b"authorization", b"Bearer openai-key"),
                    (b"x-litellm-api-key", b"litellm-key"),
                ],
            }
        )
        assert server._extract_api_key(request) == "anthropic-key"

    def test_extract_api_key_falls_back_to_x_litellm_api_key(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/messages",
                "headers": [(b"x-litellm-api-key", b"Bearer litellm-key")],
            }
        )
        assert server._extract_api_key(request) == "litellm-key"

    def test_rewrites_authorization_header(self):
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager, master_key="sk-master")

        response = client.post(
            "/v1/messages", headers={"authorization": f"Bearer {key}"}
        )

        assert response.status_code == 200
        assert response.json()["authorization"] == "Bearer sk-master"

    def test_rewrites_x_api_key_header(self):
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager, master_key="sk-master")

        response = client.post("/v1/messages", headers={"x-api-key": key})

        assert response.status_code == 200
        assert response.json()["x_api_key"] == "sk-master"

    def test_rewrites_google_and_generic_api_key_headers(self):
        manager = BudgetManager()
        google_key = manager.generate_key()
        generic_key = manager.generate_key()
        client = _make_client(manager, master_key="sk-master")

        google_response = client.post(
            "/models/gemini-2.5-pro:countTokens",
            headers={"x-goog-api-key": google_key},
        )
        generic_response = client.post(
            "/v1/messages",
            headers={"api-key": generic_key},
        )

        assert google_response.status_code == 200
        assert google_response.json()["x_goog_api_key"] == "sk-master"
        assert generic_response.status_code == 200
        assert generic_response.json()["api_key"] == "sk-master"

    def test_rewrites_x_litellm_api_key_header(self):
        """x-litellm-api-key has highest priority in LiteLLM's auth order;
        the middleware must overwrite it so a caller can't smuggle in their own."""
        manager = BudgetManager()
        key = manager.generate_key()
        app = FastAPI()
        app.add_middleware(
            server.BudgetAuthMiddleware,
            manager=manager,
            master_key="sk-master",
        )

        @app.post("/v1/messages")
        async def echo(request: Request):
            return JSONResponse(
                {"x_litellm_api_key": request.headers.get("x-litellm-api-key")}
            )

        client = TestClient(app)
        response = client.post(
            "/v1/messages",
            headers={
                "x-api-key": key,
                "x-litellm-api-key": "attacker-supplied-value",
            },
        )
        assert response.status_code == 200
        assert response.json()["x_litellm_api_key"] == "sk-master"

    def test_strips_key_query_param(self):
        """?key=... is a Gemini fallback auth source in LiteLLM; the middleware
        must strip it so callers can't bypass the header rewrite."""
        manager = BudgetManager()
        key = manager.generate_key()
        app = FastAPI()
        app.add_middleware(
            server.BudgetAuthMiddleware,
            manager=manager,
            master_key="sk-master",
        )

        @app.post("/v1/messages")
        async def echo(request: Request):
            return JSONResponse({"query": str(request.url.query)})

        client = TestClient(app)
        response = client.post(
            "/v1/messages?key=attacker&other=keep",
            headers={"authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        assert "key=attacker" not in response.json()["query"]
        assert "other=keep" in response.json()["query"]


class TestPerModelUsage:
    def test_get_usage_breaks_down_by_model(self):
        manager = BudgetManager()
        key = manager.generate_key(max_budget=10.0)
        manager.record_usage(
            key,
            "gemini/gemini-3.1-pro-preview",
            {"input_tokens": 1000, "output_tokens": 200},
            cost=0.50,
        )
        manager.record_usage(
            key,
            "gemini/gemini-3.1-pro-preview",
            {"input_tokens": 500, "output_tokens": 100, "reasoning_tokens": 50},
            cost=0.30,
        )
        manager.record_usage(
            key,
            "gemini/gemini-3-flash-preview",
            {"input_tokens": 4000, "output_tokens": 100},
            cost=0.05,
        )
        usage = manager.get_usage(key)

        # Top-level totals stay aggregated for backwards compat.
        assert usage["requests"] == 3
        assert usage["input_tokens"] == 5500
        assert usage["output_tokens"] == 400
        assert usage["reasoning_tokens"] == 50
        assert usage["spend"] == pytest.approx(0.85)

        # Per-model breakdown is exposed under "models".
        models = usage["models"]
        assert set(models) == {
            "gemini/gemini-3.1-pro-preview",
            "gemini/gemini-3-flash-preview",
        }

        pro = models["gemini/gemini-3.1-pro-preview"]
        assert pro["requests"] == 2
        assert pro["input_tokens"] == 1500
        assert pro["output_tokens"] == 300
        assert pro["reasoning_tokens"] == 50
        assert pro["spend"] == pytest.approx(0.80)

        flash = models["gemini/gemini-3-flash-preview"]
        assert flash["requests"] == 1
        assert flash["input_tokens"] == 4000
        assert flash["output_tokens"] == 100
        assert flash["reasoning_tokens"] == 0
        assert flash["spend"] == pytest.approx(0.05)

    def test_unknown_model_lands_in_empty_bucket(self):
        manager = BudgetManager()
        key = manager.generate_key(max_budget=5.0)
        manager.record_usage(key, "", {"input_tokens": 10}, cost=0.01)
        usage = manager.get_usage(key)
        assert usage["models"] == {
            "": {
                "spend": 0.01,
                "input_tokens": 10,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "reasoning_tokens": 0,
                "requests": 1,
            }
        }

    def test_per_model_totals_match_top_level_aggregate(self):
        manager = BudgetManager()
        key = manager.generate_key(max_budget=10.0)
        for model, in_tok, out_tok, cost in [
            ("openai/gpt-5.5", 1000, 200, 0.40),
            ("openai/gpt-5.5", 1500, 300, 0.60),
            ("anthropic/claude-opus-4-7", 800, 150, 0.30),
        ]:
            manager.record_usage(
                key,
                model,
                {"input_tokens": in_tok, "output_tokens": out_tok},
                cost=cost,
            )
        usage = manager.get_usage(key)
        models = usage["models"]
        for field in (
            "spend",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "requests",
        ):
            assert sum(m[field] for m in models.values()) == pytest.approx(usage[field])


class TestTracebackRedaction:
    _TRACEBACK_SAMPLE = (
        "litellm.APIConnectionError: Unsupported provider: openai\n"
        "Traceback (most recent call last):\n"
        '  File "/home/ubuntu/exploitgym/.venv/lib/python3.13/'
        'site-packages/litellm/rerank_api/main.py", line 547, in rerank\n'
        '    raise ValueError(f"Unsupported provider: {_custom_llm_provider}")\n'
        "ValueError: Unsupported provider: openai"
    )

    def test_redact_tracebacks_truncates_message_field(self):
        data = {"error": {"message": self._TRACEBACK_SAMPLE, "type": "None"}}
        assert server._redact_tracebacks(data) is True
        assert data["error"]["message"] == (
            "litellm.APIConnectionError: Unsupported provider: openai"
        )
        assert "Traceback" not in data["error"]["message"]
        assert "/home/ubuntu" not in data["error"]["message"]

    def test_redact_tracebacks_leaves_clean_messages_unchanged(self):
        data = {"error": {"message": "Invalid API key", "type": "auth_error"}}
        assert server._redact_tracebacks(data) is False
        assert data == {"error": {"message": "Invalid API key", "type": "auth_error"}}

    def test_redact_tracebacks_walks_nested_structures(self):
        data = {
            "errors": [
                {"message": "clean"},
                {"message": f"bad\n{self._TRACEBACK_SAMPLE}"},
            ]
        }
        assert server._redact_tracebacks(data) is True
        assert data["errors"][0]["message"] == "clean"
        assert "Traceback" not in data["errors"][1]["message"]

    def test_middleware_redacts_json_error_response(self):
        app = FastAPI()
        app.add_middleware(server.TracebackRedactionMiddleware)

        @app.get("/boom")
        async def boom():
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": TestTracebackRedaction._TRACEBACK_SAMPLE,
                        "type": "None",
                    }
                },
            )

        response = TestClient(app).get("/boom")
        assert response.status_code == 500
        body = response.json()
        assert "Traceback" not in body["error"]["message"]
        assert "/home/ubuntu" not in body["error"]["message"]
        assert body["error"]["type"] == "None"

    def test_middleware_passes_through_success_responses(self):
        app = FastAPI()
        app.add_middleware(server.TracebackRedactionMiddleware)

        @app.get("/ok")
        async def ok():
            # Even if a 200 body somehow contained the marker string, it must
            # not be touched — only error responses are candidates for redaction.
            return JSONResponse(
                status_code=200,
                content={"message": TestTracebackRedaction._TRACEBACK_SAMPLE},
            )

        response = TestClient(app).get("/ok")
        assert response.status_code == 200
        assert "Traceback" in response.json()["message"]

    def test_middleware_passes_through_non_json_errors(self):
        app = FastAPI()
        app.add_middleware(server.TracebackRedactionMiddleware)

        @app.get("/boom-text")
        async def boom_text():
            return Response(
                content=b"Traceback (most recent call last): opaque",
                status_code=500,
                media_type="text/plain",
            )

        response = TestClient(app).get("/boom-text")
        assert response.status_code == 500
        assert response.text == "Traceback (most recent call last): opaque"


class TestWebSearchDetector:
    """Unit tests for the vendored web-search detector."""

    def test_none_for_benign_requests(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"model": "claude-sonnet-4-6"}) is None
        assert find_web_search({"model": "gpt-5.3", "tools": []}) is None
        # A user-defined tool that is not web search.
        assert (
            find_web_search(
                {"tools": [{"type": "function", "function": {"name": "calc"}}]}
            )
            is None
        )
        # A prompt that merely mentions web search must not trip the detector.
        assert (
            find_web_search(
                {"messages": [{"role": "user", "content": "use web_search please"}]}
            )
            is None
        )
        assert find_web_search(None) is None
        assert find_web_search("not a dict") is None

    def test_web_search_models(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"model": "gpt-4o-search-preview"})
        assert find_web_search({"model": "gpt-4o-mini-search-preview-2025-03-11"})
        # search-api family (e.g. gpt-5-search-api), incl. the provider prefix.
        assert find_web_search({"model": "gpt-5-search-api"})
        assert find_web_search({"model": "openai/gpt-5-search-api"})

    def test_non_search_models_not_flagged(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"model": "gpt-5.3"}) is None
        assert find_web_search({"model": "o3"}) is None
        assert find_web_search({"model": "claude-sonnet-4-6"}) is None

    def test_deep_research_models_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # Deep-research models require an external data source, so deny them.
        assert find_web_search({"model": "o4-mini-deep-research"})
        assert find_web_search({"model": "openai/o3-deep-research-2025-06-26"})

    def test_model_in_route_path_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # A blocked model named in a Gemini-style route path is still caught.
        assert find_web_search({}, "/v1beta/models/o3-deep-research:generateContent")
        # A benign model in the path is fine.
        assert (
            find_web_search({}, "/v1beta/models/gemini-2.5-pro:generateContent") is None
        )

    def test_mcp_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # OpenAI remote MCP tool.
        assert find_web_search(
            {"tools": [{"type": "mcp", "server_url": "https://mcp.example/x"}]}
        )
        # Anthropic MCP connector list.
        assert find_web_search({"mcp_servers": [{"url": "https://mcp.example/x"}]})
        # A server_url buried anywhere in the body.
        assert find_web_search(
            {"input": [{"tool": {"server_url": "https://mcp.example/x"}}]}
        )

    def test_remote_file_and_url_inputs_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # OpenAI Responses input_file by URL.
        assert find_web_search(
            {"input": [{"type": "input_file", "file_url": "https://x/src.c"}]}
        )
        # Anthropic URL document source.
        assert find_web_search(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {"type": "url", "url": "https://x/src.c"},
                            }
                        ],
                    }
                ]
            }
        )

    def test_hosted_code_and_retrieval_tools_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"tools": [{"type": "code_interpreter"}]})
        assert find_web_search({"tools": [{"type": "code_execution_20250522"}]})
        assert find_web_search({"tools": [{"type": "file_search"}]})

    def test_gemini_url_context_and_enterprise_search_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"tools": [{"url_context": {}}]})
        assert find_web_search({"tools": [{"urlContext": {}}]})
        assert find_web_search({"tools": [{"enterprise_web_search": {}}]})

    def test_client_side_tools_not_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # Anthropic client-executed tools (Claude Code) must pass through.
        assert (
            find_web_search({"tools": [{"type": "bash_20250124", "name": "bash"}]})
            is None
        )
        assert (
            find_web_search(
                {"tools": [{"type": "text_editor_20250124", "name": "str_replace"}]}
            )
            is None
        )
        # Anthropic custom tool (client-defined, with its own schema).
        assert (
            find_web_search(
                {"tools": [{"name": "run_tests", "input_schema": {"type": "object"}}]}
            )
            is None
        )
        # A function tool whose JSON schema declares a param named "file_url"
        # must not be flagged (only string-valued file_url fields are fetches).
        assert (
            find_web_search(
                {
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "fetch",
                                "parameters": {
                                    "properties": {"file_url": {"type": "string"}}
                                },
                            },
                        }
                    ]
                }
            )
            is None
        )
        # A function param named "image_url" (schema dict, no url) is not a fetch.
        assert (
            find_web_search(
                {
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "f",
                                "parameters": {
                                    "properties": {"image_url": {"type": "string"}}
                                },
                            },
                        }
                    ]
                }
            )
            is None
        )

    def test_remote_image_url_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # OpenAI Chat Completions object form.
        assert find_web_search(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": "https://x/a.png"},
                            }
                        ],
                    }
                ]
            }
        )
        # OpenAI Responses string form.
        assert find_web_search(
            {"input": [{"type": "input_image", "image_url": "https://x/a.png"}]}
        )
        # Inline data: image is not an external fetch.
        assert (
            find_web_search(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "data:image/png;base64,AAAA"},
                                }
                            ],
                        }
                    ]
                }
            )
            is None
        )

    def test_gemini_file_uri_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search(
            {
                "contents": [
                    {"parts": [{"file_data": {"file_uri": "https://youtu.be/x"}}]}
                ]
            }
        )
        assert find_web_search(
            {"contents": [{"parts": [{"fileData": {"fileUri": "gs://bucket/x"}}]}]}
        )

    def test_hosted_shell_network_policy_blocked(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search(
            {"tools": [{"type": "shell", "network_policy": {"allowed_domains": ["x"]}}]}
        )

    def test_openai_web_search_options(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"model": "gpt-5.3", "web_search_options": {}})

    def test_anthropic_web_search_and_fetch_tools(self):
        from cybergym.llm_proxy.websearch import find_web_search

        # Claude Code's native shape.
        assert find_web_search(
            {"tools": [{"type": "web_search_20250305", "name": "web_search"}]}
        )
        # Future-dated version still caught by the prefix.
        assert find_web_search({"tools": [{"type": "web_search_20260209"}]})
        # Web fetch tool.
        assert find_web_search({"tools": [{"type": "web_fetch_20250910"}]})

    def test_openai_responses_web_search_tools(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"tools": [{"type": "web_search"}]})
        assert find_web_search({"tools": [{"type": "web_search_preview"}]})

    def test_litellm_and_legacy_tool_names(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"tools": [{"name": "litellm_web_search"}]})
        assert find_web_search({"tools": [{"name": "WebSearch"}]})
        assert find_web_search(
            {
                "tools": [
                    {"type": "function", "function": {"name": "litellm_web_search"}}
                ]
            }
        )

    def test_gemini_grounding_tools(self):
        from cybergym.llm_proxy.websearch import find_web_search

        assert find_web_search({"tools": [{"google_search": {}}]})
        assert find_web_search({"tools": [{"googleSearch": {}}]})
        assert find_web_search({"tools": [{"google_search_retrieval": {}}]})
        # Gemini may send `tools` as a single object rather than a list.
        assert find_web_search({"tools": {"google_search": {}}})


class TestWebSearchBlocking:
    """Middleware-level web-search blocking."""

    def test_web_search_request_is_blocked(self):
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"tools": [{"type": "web_search_20250305", "name": "web_search"}]},
        )
        assert response.status_code == 403
        assert response.json()["error"]["type"] == "web_search_blocked"

    def test_remote_fetch_request_is_blocked(self):
        # A non-web-search egress vector (remote file URL) is also blocked.
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"input": [{"type": "input_file", "file_url": "https://x/src.c"}]},
        )
        assert response.status_code == 403
        assert response.json()["error"]["type"] == "web_search_blocked"

    def test_web_search_allowed_when_disabled(self):
        # With block_web_search=False the same request is forwarded.
        manager = BudgetManager()
        key = manager.generate_key()
        client = _make_client(manager, block_web_search=False)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"tools": [{"type": "web_search_20250305", "name": "web_search"}]},
        )
        assert response.status_code == 200

    def test_web_search_not_billed(self):
        # A blocked request must not consume budget.
        manager = BudgetManager(default_max_budget=5.0)
        key = manager.generate_key(max_budget=5.0)
        client = _make_client(manager)

        client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"model": "gpt-4o-search-preview"},
        )
        assert manager.get_usage(key)["spend"] == 0.0

    def test_benign_request_passes_through_with_body(self):
        # Verifies the body is replayed to the downstream app after inspection.
        manager = BudgetManager()
        key = manager.generate_key()

        app = FastAPI()
        app.add_middleware(
            server.BudgetAuthMiddleware, manager=manager, master_key="sk-test"
        )

        @app.post("/v1/messages")
        async def echo_body(request: Request):
            body = await request.json()
            return JSONResponse({"received": body})

        client = TestClient(app)
        payload = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "hi"}],
        }
        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json=payload,
        )
        assert response.status_code == 200
        assert response.json()["received"] == payload


class TestModelAllowlist:
    """Per-key model allowlist."""

    def test_generate_key_stores_allowed_models(self):
        manager = BudgetManager()
        key = manager.generate_key(allowed_models=["claude-sonnet-4-6"])
        record = manager.validate_key(key)
        assert record.allowed_models == frozenset({"claude-sonnet-4-6"})
        assert manager.get_usage(key)["allowed_models"] == ["claude-sonnet-4-6"]

    def test_no_allowlist_allows_any_model(self):
        manager = BudgetManager()
        key = manager.generate_key()  # no allowed_models -> unrestricted
        assert manager.validate_key(key).allowed_models is None
        client = _make_client(manager)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"model": "anything-goes"},
        )
        assert response.status_code == 200

    def test_allowed_model_passes(self):
        manager = BudgetManager()
        key = manager.generate_key(allowed_models=["claude-sonnet-4-6"])
        client = _make_client(manager)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"model": "claude-sonnet-4-6", "messages": []},
        )
        assert response.status_code == 200

    def test_disallowed_model_blocked(self):
        manager = BudgetManager(default_max_budget=5.0)
        key = manager.generate_key(max_budget=5.0, allowed_models=["claude-sonnet-4-6"])
        client = _make_client(manager)

        response = client.post(
            "/v1/messages",
            headers={"authorization": f"Bearer {key}"},
            json={"model": "gpt-5.3", "messages": []},
        )
        assert response.status_code == 403
        assert response.json()["error"]["type"] == "model_not_allowed"
        # A blocked request must not consume budget.
        assert manager.get_usage(key)["spend"] == 0.0

    def test_allowlist_matches_model_in_route_path(self):
        manager = BudgetManager()
        key = manager.generate_key(allowed_models=["gemini-2.5-pro"])
        client = _make_client(manager)

        allowed = client.post(
            "/models/gemini-2.5-pro:countTokens",
            headers={"authorization": f"Bearer {key}"},
            json={},
        )
        assert allowed.status_code == 200

        denied = client.post(
            "/models/gemini-2.5-flash:countTokens",
            headers={"authorization": f"Bearer {key}"},
            json={},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["type"] == "model_not_allowed"
