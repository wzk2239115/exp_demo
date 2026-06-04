import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from litellm.proxy.utils import _get_docs_url, _get_openapi_url, _get_redoc_url
from starlette.responses import Response

from cybergym.llm_proxy import server
from cybergym.llm_proxy.budget import BudgetManager


def _make_client(manager: BudgetManager, master_key: str = "sk-test") -> TestClient:
    app = FastAPI()
    app.add_middleware(
        server.BudgetAuthMiddleware,
        manager=manager,
        master_key=master_key,
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
                key, model, {"input_tokens": in_tok, "output_tokens": out_tok}, cost=cost
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
