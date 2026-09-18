"""Lightweight API proxy with per-key budget tracking.

Wraps litellm proxy to support Anthropic, OpenAI, Vertex AI, etc.
with in-memory per-key budget enforcement (no Postgres required).

Architecture:
- ASGI middleware intercepts requests, validates our custom keys,
  swaps in litellm's master key, and enforces budgets
- litellm proxy handles routing, format translation, cost calculation
- BudgetCallback records spend per key after each successful request

Usage:
    python -m cybergym.llm_proxy --port 4000 --config proxy_config.yaml
"""

import json
import logging
import os
import re
import secrets
import time
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from uuid import uuid4

import litellm
from fastapi import Request
from fastapi.responses import JSONResponse
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import LiteLLMRoutes, SpecialHeaders

# Disable FastAPI docs for the LiteLLM proxy before the app is created.
os.environ.setdefault("NO_DOCS", "true")
os.environ.setdefault("NO_REDOC", "true")
os.environ.setdefault("NO_OPENAPI", "true")

from litellm.proxy.proxy_server import app
from starlette.routing import compile_path

from cybergym.llm_proxy import _diag_loop_ref
from cybergym.llm_proxy.budget import BudgetManager
from cybergym.llm_proxy.websearch import find_web_search

logger = logging.getLogger(__name__)

# Derive the allowlist from LiteLLM's own inference route lists so new inference
# endpoints LiteLLM adds upstream (e.g. a future /v1/summarize) are picked up
# automatically. We intentionally exclude:
#   - mcp_routes — RCE surface (see /mcp-rest/test/*)
#   - agent_routes, litellm_native_routes — not stateless inference
# and drop categories under openai_routes that are stateful or admin-shaped.
# Provider pass-through prefixes are allowed below via _PASSTHROUGH_PREFIXES,
# which forwards native-format requests (e.g. /anthropic/v1/messages).
_STATEFUL_OR_ADMIN_SUBSTRINGS = (
    "/batches",
    "/files",
    "/fine_tuning",
    "/assistants",
    "/threads",
    "/vector_stores",
    "/vector_store/",
    "/containers",
    "/realtime",
    "/skills",
    "/interactions",
    "/engines/",
)


def _is_inference_pattern(pattern: str) -> bool:
    # compile_path doesn't accept `*` wildcards or `?`-prefixed query patterns.
    if "*" in pattern or "?" in pattern:
        return False
    return not any(sub in pattern for sub in _STATEFUL_OR_ADMIN_SUBSTRINGS)


INFERENCE_ROUTE_PATTERNS = tuple(
    p
    for p in (
        *LiteLLMRoutes.openai_routes.value,
        *LiteLLMRoutes.anthropic_routes.value,
        *LiteLLMRoutes.google_routes.value,
    )
    if _is_inference_pattern(p)
)

_INFERENCE_ROUTE_REGEXES = [
    compile_path(pattern)[0] for pattern in INFERENCE_ROUTE_PATTERNS
]

# Provider pass-through prefixes (e.g. /anthropic/v1/messages, /vertex_ai/...).
# LiteLLM signs these with its stored provider credentials; budget tracking is
# handled by the standard response callback. Note this broadens scope beyond
# inference — callers can reach any path the provider exposes under these
# prefixes, including provider-side file/batch/admin APIs.
_PASSTHROUGH_PREFIXES = tuple(
    f"{prefix}/" for prefix in LiteLLMRoutes.mapped_pass_through_routes.value
)


def _is_inference_route(path: str) -> bool:
    if path.startswith(_PASSTHROUGH_PREFIXES):
        return True
    return any(regex.match(path) for regex in _INFERENCE_ROUTE_REGEXES)


# Every header LiteLLM's get_api_key() reads as an auth credential must be rewritten
# to the master key, otherwise a caller can supply their own value via a header the
# middleware doesn't inspect and bypass budget-tracked auth. Source of truth is the
# SpecialHeaders enum consumed by litellm/proxy/auth/user_api_key_auth.py::get_api_key.
_AUTHORIZATION_HEADER = SpecialHeaders.openai_authorization.value.lower()
_LITELLM_AUTH_HEADERS = frozenset(h.value.lower() for h in SpecialHeaders)


# Model named in a Gemini-style route path, e.g.
# /v1beta/models/<model>:generateContent
_PATH_MODEL_RE = re.compile(r"/models/([^/:]+)")


def _request_model(body: object, path: str) -> str | None:
    """Return the model the request targets (body `model` or Gemini route path)."""
    if isinstance(body, dict) and isinstance(body.get("model"), str):
        return body["model"]
    match = _PATH_MODEL_RE.search(path or "")
    return match.group(1) if match else None


def _extract_api_key(request: Request) -> str:
    return (
        request.headers.get("x-api-key")
        or request.headers.get("x-goog-api-key")
        or request.headers.get("api-key")
        or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        or request.headers.get("x-litellm-api-key", "").removeprefix("Bearer ").strip()
    )


def _extract_api_key_from_scope(scope) -> str:
    """Extract API key from ASGI scope headers (no Request object needed)."""
    headers = {}
    for k, v in scope.get("headers", []):
        headers[k.decode("latin-1")] = v.decode("latin-1")
    return (
        headers.get("x-api-key")
        or headers.get("x-goog-api-key")
        or headers.get("api-key")
        or headers.get("authorization", "").removeprefix("Bearer ").strip()
        or headers.get("x-litellm-api-key", "").removeprefix("Bearer ").strip()
    )


async def _read_body(receive) -> bytes:
    """Read the complete request body from an ASGI receive callable."""
    body = b""
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    return body


class _ReplayReceive:
    """ASGI receive callable that replays a fixed body once.

    Each instance is independent (no shared mutable state) so concurrent
    requests don't clobber each other's state.
    """

    __slots__ = ("_body", "_sent")

    def __init__(self, body: bytes):
        self._body = body
        self._sent = False

    async def __call__(self):
        if not self._sent:
            self._sent = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}


async def _send_json(send, status_code: int, content: dict) -> None:
    """Send a JSON response directly via ASGI send callable."""
    body = json.dumps(content).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


# Internal master key for litellm proxy auth. Never exposed externally.
INTERNAL_MASTER_KEY = f"sk-internal-{uuid4().hex}"

# Admin key for /budget/* endpoints. Set during setup_proxy().
_admin_key: str = ""

# Context var to pass original key from middleware to callback within same request
_current_api_key: ContextVar[str] = ContextVar("_current_api_key", default="")


def _extract_usage(slo: dict, response_obj) -> dict:
    """Pull token counts from litellm's callback payload.

    Confirmed field locations (verified by inspecting live payloads):
    - `slo['prompt_tokens']` / `slo['completion_tokens']`: reliable for all
      providers; populated even when streaming.
    - Cache tokens (not in SLO top-level — litellm hasn't unified these):
        * OpenAI (Chat Completions + Responses API):
          `slo['response']['usage']['prompt_tokens_details']['cached_tokens']`
        * Anthropic: `cache_read_input_tokens` / `cache_creation_input_tokens`,
          either flat in SLO or under `slo['response']['usage']`.
    - `response_obj.usage` is empty `{}` for OpenAI Responses API, so we only
      use it as a last-resort fallback.
    """
    inner_usage = (slo.get("response") or {}).get("usage") or {}
    prompt_details = inner_usage.get("prompt_tokens_details") or {}
    completion_details = inner_usage.get("completion_tokens_details") or {}

    resp_obj_usage = getattr(response_obj, "usage", None)

    def _from_obj(attr: str) -> int:
        if resp_obj_usage is None:
            return 0
        if isinstance(resp_obj_usage, dict):
            return int(resp_obj_usage.get(attr) or 0)
        return int(getattr(resp_obj_usage, attr, 0) or 0)

    input_tokens = (
        int(slo.get("prompt_tokens") or 0)
        or int(inner_usage.get("prompt_tokens") or 0)
        or _from_obj("prompt_tokens")
    )
    output_tokens = (
        int(slo.get("completion_tokens") or 0)
        or int(inner_usage.get("completion_tokens") or 0)
        or _from_obj("completion_tokens")
    )
    # litellm unifies both read and creation counts under prompt_tokens_details
    # across providers (OpenAI, Anthropic, z.ai/GLM, ...). The flat
    # `cache_*_input_tokens` keys are Anthropic-specific duplicates that
    # litellm also forwards — kept only as a secondary fallback.
    cache_read = (
        int(prompt_details.get("cached_tokens") or 0)
        or int(inner_usage.get("cache_read_input_tokens") or 0)
        or int(slo.get("cache_read_input_tokens") or 0)
    )
    cache_create = (
        int(prompt_details.get("cache_creation_tokens") or 0)
        or int(inner_usage.get("cache_creation_input_tokens") or 0)
        or int(slo.get("cache_creation_input_tokens") or 0)
    )
    # OpenAI o-series: subset of completion_tokens spent on hidden reasoning.
    # Anthropic does not separately report thinking tokens, so this is 0 there.
    reasoning_tokens = int(completion_details.get("reasoning_tokens") or 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_create,
        "reasoning_tokens": reasoning_tokens,
    }


class BudgetCallback(CustomLogger):
    """litellm callback that tracks spend per API key in BudgetManager."""

    def __init__(self, manager: BudgetManager):
        self.manager = manager

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        api_key = _current_api_key.get("")
        slo = kwargs.get("standard_logging_object") or {}
        cost = slo.get("response_cost", 0.0)
        model = slo.get("model", kwargs.get("model", ""))
        duration = (
            (end_time - start_time).total_seconds() if start_time and end_time else 0.0
        )

        logger.debug(
            "Callback fired: key=%s model=%s cost=$%.6f duration=%.2fs",
            f"{api_key[:8]}...{api_key[-4:]}" if api_key else "<none>",
            model,
            cost,
            duration,
        )

        usage = _extract_usage(slo, response_obj)
        if any(usage.values()):
            logger.debug(
                "Usage: input=%d output=%d cache_read=%d cache_create=%d",
                usage["input_tokens"],
                usage["output_tokens"],
                usage["cache_read_input_tokens"],
                usage["cache_creation_input_tokens"],
            )
        else:
            logger.debug("No usage data in SLO or response object")

        has_usage_or_cost = cost > 0.0 or any(usage.values())

        if api_key and has_usage_or_cost:
            self.manager.record_usage(
                api_key, model, usage, cost=cost, duration=duration
            )
            record = self.manager._keys.get(api_key)
            if record:
                logger.debug(
                    "Key %s...%s: +$%.4f (total $%.4f / $%.2f)",
                    api_key[:8],
                    api_key[-4:],
                    cost,
                    record.spend,
                    record.max_budget,
                )
        elif not api_key:
            logger.debug("Skipping record_usage: no API key in context")
        elif not has_usage_or_cost:
            logger.debug("Skipping record_usage: no usage or cost data available")


class BudgetAuthMiddleware:
    """Pure ASGI middleware that validates custom keys and swaps in master key.

    For /budget/* endpoints: passes through directly.
    For all other endpoints: validates our cgym-* key, checks budget,
    replaces with litellm master key, and stashes original key in
    request headers for the callback to pick up.

    Implemented as a raw ASGI middleware (not BaseHTTPMiddleware) to avoid
    starlette's TaskGroup/ExceptionGroup crash under high concurrency
    (see https://github.com/encode/starlette/issues/1438).
    """

    def __init__(
        self,
        app,
        manager: BudgetManager,
        master_key: str,
        block_web_search: bool = True,
    ):
        self.app = app
        self.manager = manager
        self.master_key = master_key
        self.block_web_search = block_web_search

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Lazy one-time capture of the running event loop for the
        # stack-dump watcher (litellm's app defines lifespan=, which
        # silently disables FastAPI on_event("startup") hooks).
        _capture_loop_lazily()

        path = scope["path"]

        # Authenticate budget management endpoints with admin key
        if path.startswith("/budget/"):
            headers_dict = dict(
                (k.decode("latin-1"), v.decode("latin-1"))
                for k, v in scope.get("headers", [])
            )
            admin_key = (
                headers_dict.get("x-admin-key")
                or headers_dict.get("authorization", "").removeprefix("Bearer ").strip()
            )
            if not admin_key or not secrets.compare_digest(admin_key, _admin_key):
                logger.debug("Rejected budget request: invalid admin key")
                await _send_json(
                    send,
                    401,
                    {"error": {"message": "Invalid admin key", "type": "auth_error"}},
                )
                return
            logger.debug("Authenticated budget endpoint: %s %s", scope["method"], path)
            await self.app(scope, receive, send)
            return

        # Pass through litellm internal endpoints
        if path in ("/health", "/health/liveliness", "/health/readiness"):
            logger.debug("Passthrough health endpoint: %s", path)
            await self.app(scope, receive, send)
            return

        if not _is_inference_route(path):
            logger.debug(
                "Rejected route outside inference allowlist: %s %s",
                scope["method"],
                path,
            )
            await _send_json(
                send,
                403,
                {
                    "error": {
                        "message": f"Route not allowed for budget-scoped API keys: {path}",
                        "type": "forbidden_route",
                    }
                },
            )
            return

        # /v1/messages/count_tokens is no longer intercepted locally.
        # litellm's count_tokens endpoint is patched (see
        # _patch_litellm_count_tokens_endpoint) to forward to OUR upstream
        # (e.g. 360's native count_tokens), which returns exact counts
        # including system+tools. The old local estimate (~4 chars/token,
        # messages-only) under-counted and skewed cc's context accounting.

        logger.debug("Incoming request: %s %s", scope["method"], path)

        # Extract API key from headers
        api_key = _extract_api_key_from_scope(scope)

        if not api_key:
            logger.debug("Rejected: no API key in headers")
            await _send_json(send, 401, {"error": "Missing API key"})
            return

        key_hint = f"{api_key[:8]}...{api_key[-4:]}"
        logger.debug("Extracted key %s", key_hint)

        # Validate our custom key
        record = self.manager.validate_key(api_key)
        if record is None:
            usage = self.manager.get_usage(api_key)
            if usage is not None:
                logger.debug(
                    "Rejected key %s: budget exhausted ($%.2f / $%.2f)",
                    key_hint,
                    usage["spend"],
                    usage["max_budget"],
                )
                await _send_json(
                    send,
                    429,
                    {
                        "error": {
                            "message": f"Budget exhausted: ${usage['spend']:.2f} / ${usage['max_budget']:.2f}",
                            "type": "budget_exceeded",
                        }
                    },
                )
                return
            logger.debug("Rejected key %s: not found", key_hint)
            await _send_json(
                send,
                401,
                {"error": {"message": "Invalid API key", "type": "auth_error"}},
            )
            return

        logger.debug(
            "Validated key %s (spend $%.4f / $%.2f)",
            key_hint,
            record.spend,
            record.max_budget,
        )

        # Body-level policy checks
        enforce_models = record.allowed_models is not None
        new_body: bytes | None = None
        parsed_body = None
        raw_body: bytes | None = None
        body_was_read = False

        if (self.block_web_search or enforce_models) and scope["method"] in (
            "POST",
            "PUT",
            "PATCH",
        ):
            raw_body = await _read_body(receive)
            body_was_read = True
            if raw_body:
                try:
                    parsed_body = json.loads(raw_body)
                except ValueError:
                    parsed_body = None

            # Reject provider-side external retrieval
            if self.block_web_search:
                reason = find_web_search(parsed_body, path)
                if reason is not None:
                    logger.info(
                        "Rejected external-retrieval request for key %s (%s): %s %s",
                        key_hint,
                        reason,
                        scope["method"],
                        path,
                    )
                    await _send_json(
                        send,
                        403,
                        {
                            "error": {
                                "message": f"Request blocked by proxy policy (external retrieval disabled): {reason}",
                                "type": "web_search_blocked",
                            }
                        },
                    )
                    return

            # Enforce the per-key model allowlist
            if enforce_models:
                model = _request_model(parsed_body, path)
                if model is not None and model not in record.allowed_models:
                    logger.info(
                        "Rejected model '%s' for key %s (allowed: %s): %s %s",
                        model,
                        key_hint,
                        sorted(record.allowed_models),
                        scope["method"],
                        path,
                    )
                    await _send_json(
                        send,
                        403,
                        {
                            "error": {
                                "message": f"Model '{model}' is not allowed for this key",
                                "type": "model_not_allowed",
                            }
                        },
                    )
                    return

            # Normalize the 'thinking' param on /v1/messages requests
            def _rewrite_thinking_enabled() -> None:
                max_tokens = parsed_body.get("max_tokens") or 0
                try:
                    max_tokens = int(max_tokens)
                except (TypeError, ValueError):
                    max_tokens = 0
                budget = min(max(1024, max_tokens // 2), 8192)
                model_name = str(parsed_body.get("model") or "")
                if "deepseek" in model_name.lower():
                    effort = os.environ.get("REASONING_EFFORT", "").strip().lower()
                    if effort in ("low", "medium", "high", "xhigh", "max"):
                        parsed_body["reasoning_effort"] = effort
                        if not os.environ.get("THINKING_BUDGET"):
                            budget = max(budget, 16384)
                    try:
                        tb = int(os.environ.get("THINKING_BUDGET", "") or 0)
                    except ValueError:
                        tb = 0
                    if tb > 0:
                        budget = max(1024, min(tb, 65536))
                if max_tokens <= budget:
                    max_tokens = budget + 512
                    parsed_body["max_tokens"] = max_tokens
                parsed_body["thinking"] = {"type": "enabled", "budget_tokens": budget}

            if parsed_body and path == "/v1/messages":
                if litellm.use_chat_completions_url_for_anthropic_messages:
                    if "thinking" in parsed_body:
                        del parsed_body["thinking"]
                        new_body = json.dumps(parsed_body).encode("utf-8")
                        logger.info(
                            "Stripped 'thinking' from /v1/messages for key %s", key_hint
                        )
                    else:
                        new_body = None
                else:
                    thinking = parsed_body.get("thinking")
                    if isinstance(thinking, dict) and thinking.get("type") == "enabled":
                        new_body = None
                    else:
                        old_desc = (
                            json.dumps(thinking, ensure_ascii=False)
                            if thinking is not None
                            else "absent"
                        )
                        _rewrite_thinking_enabled()
                        new_body = json.dumps(parsed_body).encode("utf-8")
                        logger.info(
                            "Rewrote 'thinking' (%s -> enabled) in /v1/messages for key %s",
                            old_desc,
                            key_hint,
                        )

                    for env_key, field in (
                        ("SAMPLING_TEMPERATURE", "temperature"),
                        ("SAMPLING_TOP_P", "top_p"),
                    ):
                        raw = os.environ.get(env_key, "").strip()
                        if raw:
                            try:
                                parsed_body[field] = float(raw)
                            except ValueError:
                                pass
                    new_body = json.dumps(parsed_body).encode("utf-8")

        # Build modified scope with new body (if any) and swapped auth headers
        modified_scope = dict(scope)
        new_headers = []
        for k, v in scope.get("headers", []):
            name = k.decode("latin-1")
            if name == _AUTHORIZATION_HEADER:
                new_headers.append((k, f"Bearer {self.master_key}".encode("latin-1")))
            elif name in _LITELLM_AUTH_HEADERS:
                new_headers.append((k, self.master_key.encode("latin-1")))
            else:
                new_headers.append((k, v))
        if new_body is not None:
            new_headers = [
                (b"content-length", str(len(new_body)).encode("latin-1"))
                if k == b"content-length"
                else (k, v)
                for k, v in new_headers
            ]
        modified_scope["headers"] = new_headers

        # Strip ?key=... from query string
        query_string: bytes = scope.get("query_string", b"")
        if query_string:
            pairs = parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)
            if any(k == "key" for k, _ in pairs):
                modified_scope["query_string"] = urlencode(
                    [(k, v) for k, v in pairs if k != "key"]
                ).encode("latin-1")

        # Set up the receive callable. Use a class (not a closure) to avoid
        # variable capture bugs under concurrent requests (closures capture
        # variable references, so concurrent __call__ invocations would
        # clobber each other's _sent[0] / new_body / _replay_body).
        if new_body is not None:
            receive_callable = _ReplayReceive(new_body)
        elif body_was_read:
            receive_callable = _ReplayReceive(raw_body or b"")
        else:
            receive_callable = receive

        # Set context var so the callback knows which key made this request
        token = _current_api_key.set(api_key)
        logger.debug("Forwarding request to litellm: %s %s", scope["method"], path)
        try:
            await self.app(modified_scope, receive_callable, send)
        finally:
            _current_api_key.reset(token)


# LiteLLM glues full stack traces into APIConnectionError.message at
# litellm/litellm_core_utils/exception_mapping_utils.py:{2307,2463} and in
# common_request_processing.py:1727. These tracebacks leak absolute file paths,
# Python version, and internal code structure through the HTTP response body.
# Strip anything from the traceback marker onward before responding to clients.
_TRACEBACK_MARKER = "Traceback (most recent call last):"


def _redact_tracebacks(data: object) -> bool:
    """Recursively truncate `message` fields at the traceback marker.

    Returns True if any modification was made.
    """
    modified = False
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "message" and isinstance(value, str):
                idx = value.find(_TRACEBACK_MARKER)
                if idx >= 0:
                    data[key] = value[:idx].rstrip()
                    modified = True
            elif _redact_tracebacks(value):
                modified = True
    elif isinstance(data, list):
        for item in data:
            if _redact_tracebacks(item):
                modified = True
    return modified


class TracebackRedactionMiddleware:
    """Strip LiteLLM tracebacks from JSON error response bodies.

    Pure ASGI middleware (no BaseHTTPMiddleware) to avoid TaskGroup crashes.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = {"value": 200}
        content_type = {"value": ""}
        collected_body = bytearray()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code["value"] = message.get("status", 200)
                for k, v in message.get("headers", []):
                    if k == b"content-type":
                        content_type["value"] = v.decode("latin-1")
                        break
                await send(message)
            elif message["type"] == "http.response.body":
                if (
                    status_code["value"] >= 400
                    and "application/json" in content_type["value"]
                ):
                    collected_body.extend(message.get("body", b""))
                    if message.get("more_body", False):
                        return  # wait for all chunks
                    # All body collected — process
                    body_bytes = bytes(collected_body)
                    try:
                        data = json.loads(body_bytes)
                    except ValueError:
                        await send(
                            {
                                "type": "http.response.body",
                                "body": body_bytes,
                                "more_body": False,
                            }
                        )
                        return
                    if _redact_tracebacks(data):
                        body_bytes = json.dumps(data).encode("utf-8")
                    await send(
                        {
                            "type": "http.response.body",
                            "body": body_bytes,
                            "more_body": False,
                        }
                    )
                else:
                    await send(message)
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)


def _patch_litellm_server_tool_use_dict():
    """Coerce dict server_tool_use -> ServerToolUse before cost calculation.

    The same issue as: https://github.com/BerriAI/litellm/issues/26749

    Why: GLM-5.1 (z.ai) Anthropic-compat streaming responses round-trip through
    litellm's stream_chunk_builder, which assigns the raw dict
    {"web_search_requests": 0, "tool_search_requests": None} to
    Usage.server_tool_use without wrapping it. The cost calculator then does
    `usage.server_tool_use.web_search_requests is not None` and raises
    AttributeError, so completion_cost returns None and the request bills $0
    against the per-key budget. Drop this once litellm fixes it upstream.
    """
    from litellm.litellm_core_utils.llm_cost_calc import (
        tool_call_cost_tracking as _t,
    )
    from litellm.types.utils import ServerToolUse

    _orig = _t.StandardBuiltInToolCostTracking.response_object_includes_web_search_call

    def _coerce(obj):
        stu = getattr(obj, "server_tool_use", None)
        if isinstance(stu, dict):
            try:
                obj.server_tool_use = ServerToolUse(**stu)
            except Exception:
                obj.server_tool_use = None

    @staticmethod
    def _patched(response_object=None, usage=None):
        if usage is not None:
            _coerce(usage)
        if response_object is not None:
            resp_usage = getattr(response_object, "usage", None)
            if resp_usage is not None:
                _coerce(resp_usage)
        return _orig(response_object=response_object, usage=usage)

    _t.StandardBuiltInToolCostTracking.response_object_includes_web_search_call = (
        _patched
    )


def _patch_litellm_thinking_responses_routing():
    """Prevent litellm from re-routing thinking requests to the Responses API.

    When ``use_chat_completions_url_for_anthropic_messages`` is True we've
    already forced /v1/messages → chat/completions (see setup_proxy). But
    litellm's completion adapter has a SECOND routing decision inside
    ``_route_openai_thinking_to_responses_api_if_needed``
    (adapters/handler.py:48-117): when the request carries
    ``thinking={"type":"enabled",...}`` (which Claude Code always sends with
    an effort level) AND the provider is OpenAI, it prefixes the model name
    with ``responses/`` to route through the Responses API.

    For providers like 360 that only accept /chat/completions (or whose
    Responses endpoint mangles the ``openai/`` model prefix), this
    re-routing causes a 400. Patch the method to respect our
    ``use_chat_completions_url_for_anthropic_messages`` flag and skip the
    ``responses/`` prefix when it is set.
    """
    from litellm.llms.anthropic.experimental_pass_through.adapters.handler import (
        LiteLLMMessagesToCompletionTransformationHandler as _H,
    )

    _orig = _H._route_openai_thinking_to_responses_api_if_needed

    @staticmethod
    def _patched(completion_kwargs, *, thinking=None):
        if litellm.use_chat_completions_url_for_anthropic_messages:
            return  # honour the global flag: stay on chat/completions
        return _orig(completion_kwargs, thinking=thinking)

    _H._route_openai_thinking_to_responses_api_if_needed = _patched


def _patch_litellm_count_tokens_endpoint():
    """Route litellm's Anthropic count_tokens to OUR anthropic api_base.

    litellm hard-codes ``https://api.anthropic.com/v1/messages/count_tokens``
    (AnthropicCountTokensConfig.get_anthropic_count_tokens_endpoint). With a
    360 deployment the request goes to api.anthropic.com with the 360 key →
    401 → litellm falls back to a local tokenizer that misses system/tools
    and under-counts, which skews Claude Code's context-window accounting.

    360's anthropic endpoint natively supports /v1/messages/count_tokens
    (verified: exact counts including system+tools, beta header optional).
    Patch the endpoint builder to return our upstream base instead.
    """
    import os as _os

    upstream = _os.environ.get("GLM_ANTHROPIC_BASE", "https://api.360.cn").rstrip("/")

    from litellm.llms.anthropic.count_tokens.transformation import (
        AnthropicCountTokensConfig,
    )

    def _patched(self):
        return f"{upstream}/v1/messages/count_tokens"

    AnthropicCountTokensConfig.get_anthropic_count_tokens_endpoint = _patched
    logger.info("Patched count_tokens endpoint -> %s", upstream)


def _patch_streaming_reasoning_detection():
    """Fix litellm stream adapter to detect reasoning_content from gpt-5*.

    gpt-5.5 returns reasoning via ``delta.reasoning_content`` (OpenAI format),
    not ``delta.thinking_blocks`` (Anthropic format). litellm's streaming
    adapter ``_translate_streaming_openai_chunk_to_anthropic_content_block``
    only checks ``thinking_blocks`` → misses ``reasoning_content`` → the
    reasoning delta is sent for a *text* content block instead of starting a
    new *thinking* block → claude_code panics with "Content block not found".

    Patch: check ``reasoning_content`` BEFORE falling through to "text".
    """
    from litellm.llms.anthropic.experimental_pass_through.adapters.transformation import (
        LiteLLMAnthropicMessagesAdapter,
    )

    _orig = LiteLLMAnthropicMessagesAdapter._translate_streaming_openai_chunk_to_anthropic_content_block

    def _patched(self, choices):
        for choice in choices:
            rc = getattr(choice.delta, "reasoning_content", None)
            if rc and len(rc) > 0:
                from litellm.types.llms.openai import ChatCompletionThinkingBlock

                return "thinking", ChatCompletionThinkingBlock(
                    type="thinking", thinking="", signature=""
                )
        return _orig(self, choices)

    LiteLLMAnthropicMessagesAdapter._translate_streaming_openai_chunk_to_anthropic_content_block = _patched


def setup_proxy(
    manager: BudgetManager,
    config_path: str | None = None,
    admin_key: str | None = None,
    block_web_search: bool = True,
):
    """Configure litellm proxy with budget tracking.

    Must be called before uvicorn starts the app. Sets env vars that
    litellm proxy reads during its startup lifespan event.

    Args:
        manager: BudgetManager instance for key tracking.
        config_path: Path to litellm proxy YAML config.
        admin_key: Key required to access /budget/* endpoints.
            If None, auto-generated.
        block_web_search: When True (default), reject requests that would
            invoke provider-side web search. Set False to allow web search.
    """
    global _admin_key
    _admin_key = admin_key or f"cgym-admin-{uuid4().hex[:24]}"
    logger.info("Admin key for /budget endpoints: %s", _admin_key)

    _patch_litellm_server_tool_use_dict()
    _patch_litellm_thinking_responses_routing()
    _patch_litellm_count_tokens_endpoint()
    _patch_streaming_reasoning_detection()

    # Route /v1/messages based on provider mode (detected from the config).
    #
    # Native-anthropic configs (model: anthropic/<name>, i.e. GLM_PROVIDER=
    # anthropic → 360's own /v1/messages endpoint) MUST keep the flag False so
    # litellm passes requests through untouched: no chat/completions
    # translation, no anthropic→chat→anthropic double conversion, and the
    # middleware injects the 'thinking' param always-thinking models require.
    #
    # OpenAI-provider configs force the flag True: litellm would otherwise
    # route OpenAI /v1/messages through the Responses API
    # (_RESPONSES_API_PROVIDERS = {'openai'}), which 360 doesn't support —
    # chat/completions is the only working path there.
    native_anthropic = False
    if config_path:
        try:
            cfg_text = Path(config_path).read_text()
            native_anthropic = "anthropic/" in cfg_text
        except OSError:
            pass
    litellm.use_chat_completions_url_for_anthropic_messages = not native_anthropic
    logger.info(
        "use_chat_completions_url_for_anthropic_messages = %s (native_anthropic=%s)",
        litellm.use_chat_completions_url_for_anthropic_messages,
        native_anthropic,
    )

    # Set internal master key for litellm proxy
    os.environ["LITELLM_MASTER_KEY"] = INTERNAL_MASTER_KEY
    # Remove DATABASE_URL so litellm skips Prisma/Postgres entirely
    os.environ.pop("DATABASE_URL", None)

    # Point litellm to the config file — it loads this during startup
    if config_path:
        os.environ["CONFIG_FILE_PATH"] = config_path
        logger.debug("Using config file: %s", config_path)

    # Register budget callback
    callback = BudgetCallback(manager)
    litellm.callbacks.append(callback)
    logger.debug("Registered BudgetCallback with litellm")

    # Add auth middleware (pure ASGI, no BaseHTTPMiddleware to avoid
    # starlette TaskGroup/ExceptionGroup crash under high concurrency).
    app.middleware_stack = None
    app.add_middleware(
        BudgetAuthMiddleware,
        manager=manager,
        master_key=INTERNAL_MASTER_KEY,
        block_web_search=block_web_search,
    )
    logger.debug("Added BudgetAuthMiddleware (block_web_search=%s)", block_web_search)

    # Add traceback-redaction middleware (pure ASGI).
    app.add_middleware(TracebackRedactionMiddleware)
    logger.debug("Added TracebackRedactionMiddleware")

    # Add budget management endpoints
    @app.post("/budget/generate_key")
    async def generate_key(request: Request):
        body = await request.json()
        max_budget = body.get("max_budget", manager.default_max_budget)
        allowed_models = body.get("allowed_models")
        logger.debug(
            "Endpoint /budget/generate_key: max_budget=$%.2f models=%s",
            max_budget,
            allowed_models or "any",
        )
        key = manager.generate_key(max_budget=max_budget, allowed_models=allowed_models)
        return {
            "key": key,
            "max_budget": max_budget,
            "allowed_models": allowed_models,
        }

    @app.get("/budget/usage/{key}")
    async def get_usage(key: str):
        logger.debug("Endpoint /budget/usage: key=%s...%s", key[:8], key[-4:])
        usage = manager.get_usage(key)
        if usage is None:
            logger.debug("Endpoint /budget/usage: key not found")
            return JSONResponse(status_code=404, content={"error": "Key not found"})
        return usage

    @app.delete("/budget/key/{key}")
    async def delete_key(key: str):
        logger.debug("Endpoint /budget/key DELETE: key=%s...%s", key[:8], key[-4:])
        usage = manager.delete_key(key)
        if usage is None:
            logger.debug("Endpoint /budget/key DELETE: key not found")
            return JSONResponse(status_code=404, content={"error": "Key not found"})
        return usage

    # ── Diagnostics: dump all thread stacks on demand ──────────────────
    # When the proxy's event loop freezes, every request times out and
    # nothing is written to the log. This endpoint dumps faulthandler
    # output (all thread stacks, including what's blocking the loop) to
    # the log AND the response, so a single curl pinpoints the culprit.
    # NOTE: faulthandler.dump_traceback is signal-safe and can be called
    # from any thread — but if the event loop itself is blocked this
    # endpoint won't respond either; use the file trigger instead:
    #   touch /tmp/cybergym_proxy_stack_dump  (watched via faulthandler
    #   registered in __main__).
    _diag_state = {"last_dump": ""}

    @app.get("/health/dump")
    async def dump_stacks():
        import faulthandler
        import io
        import threading

        buf = io.StringIO()
        buf.write(
            f"=== stack dump at {time.time()} ({threading.active_count()} threads) ===\n"
        )
        faulthandler.dump_traceback(file=buf)
        dump = buf.getvalue()
        _diag_state["last_dump"] = dump
        logger.info("Stack dump requested:\n%s", dump)
        return {"stacks": dump}


def _capture_loop_lazily():
    """One-time capture of the running event loop for the stack-dump
    watcher thread (registered by cybergym.llm_proxy.__main__).

    litellm's app is created with lifespan=proxy_startup_event, which
    makes FastAPI IGNORE on_event("startup") hooks — so this is called
    from BudgetAuthMiddleware.__call__ on the first request instead.
    """
    if _diag_loop_ref["loop"] is None:
        import asyncio

        try:
            _diag_loop_ref["loop"] = asyncio.get_running_loop()
            logger.info("Diagnostics: captured running event loop")
        except RuntimeError:
            pass


def get_proxy_app():
    """Get the configured litellm proxy FastAPI app."""
    return app
