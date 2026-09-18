"""Tests for the pure-ASGI BudgetAuthMiddleware.

These tests verify the concurrency-safety fixes that replaced
BaseHTTPMiddleware with a raw ASGI implementation:

1. _ReplayReceive instances are independent (no shared mutable state).
2. Body replay works correctly under concurrent requests.
3. The middleware forwards the correct body to the downstream app.
4. Auth headers are swapped correctly.
5. Health/budget endpoints pass through.
6. Invalid keys are rejected.
7. Concurrent requests don't clobber each other's receive state.
"""

import asyncio
import json

import pytest

from cybergym.llm_proxy.budget import BudgetManager
from cybergym.llm_proxy.server import (
    INTERNAL_MASTER_KEY,
    BudgetAuthMiddleware,
    _ReplayReceive,
)

# ── _ReplayReceive unit tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_receive_returns_body_once():
    r = _ReplayReceive(b'{"hello": "world"}')
    msg1 = await r()
    assert msg1 == {
        "type": "http.request",
        "body": b'{"hello": "world"}',
        "more_body": False,
    }
    msg2 = await r()
    assert msg2 == {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
async def test_replay_receive_empty_body():
    r = _ReplayReceive(b"")
    msg1 = await r()
    assert msg1 == {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
async def test_replay_receive_instances_are_independent():
    """Critical: concurrent requests must not share _sent state."""
    r1 = _ReplayReceive(b"body1")
    r2 = _ReplayReceive(b"body2")

    # Interleave calls: r1 first, then r2, then r1 again.
    msg1a = await r1()
    msg2a = await r2()
    msg1b = await r1()
    msg2b = await r2()

    assert msg1a["body"] == b"body1"
    assert msg2a["body"] == b"body2"
    assert msg1b["body"] == b""  # second call returns empty
    assert msg2b["body"] == b""


# ── Helper: build a minimal ASGI app for testing ───────────────────────


class _CaptureApp:
    """Minimal ASGI app that captures the request body and headers."""

    def __init__(self):
        self.received_bodies = []
        self.received_headers = []
        self.call_count = 0

    async def __call__(self, scope, receive, send):
        self.call_count += 1
        body = b""
        while True:
            msg = await receive()
            if msg["type"] != "http.request":
                continue
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        self.received_bodies.append(body)
        # Capture auth header
        headers = dict(
            (k.decode("latin-1"), v.decode("latin-1"))
            for k, v in scope.get("headers", [])
        )
        self.received_headers.append(headers)

        resp = json.dumps({"ok": True}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(resp)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": resp, "more_body": False})


class _CollectSend:
    """Collects ASGI send messages."""

    def __init__(self):
        self.messages = []
        self.status = None
        self.body = b""

    async def __call__(self, message):
        self.messages.append(message)
        if message["type"] == "http.response.start":
            self.status = message.get("status", 200)
        elif message["type"] == "http.response.body":
            self.body += message.get("body", b"")


def _make_scope(
    path="/v1/messages",
    method="POST",
    api_key="cgym-test-key-12345678",
    body=b'{"model": "deepseek-v4.1-flash", "messages": [{"role": "user", "content": "hi"}]}',
    extra_headers=None,
):
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("latin-1")),
        (b"x-api-key", api_key.encode("latin-1")),
    ]
    if extra_headers:
        for k, v in extra_headers:
            headers.append((k.encode("latin-1"), v.encode("latin-1")))
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "query_string": b"",
    }


def _make_receive(body: bytes):
    return _ReplayReceive(body)


# ── Middleware integration tests ───────────────────────────────────────


@pytest.fixture
def manager():
    return BudgetManager(default_max_budget=1000.0)


@pytest.fixture
def middleware(manager):
    app = _CaptureApp()
    mw = BudgetAuthMiddleware(
        app=app,
        manager=manager,
        master_key=INTERNAL_MASTER_KEY,
        block_web_search=False,
    )
    return mw, app


def _make_valid_key(manager):
    return manager.generate_key(max_budget=1000.0)


@pytest.mark.asyncio
async def test_middleware_forwards_body_correctly(middleware):
    mw, app = middleware
    manager = mw.manager
    key = _make_valid_key(manager)

    body = json.dumps(
        {"model": "test", "messages": [{"role": "user", "content": "hi"}]}
    ).encode()
    scope = _make_scope(api_key=key, body=body)
    receive = _make_receive(body)
    send = _CollectSend()

    await mw(scope, receive, send)

    assert app.call_count == 1
    assert app.received_bodies[0] == body


@pytest.mark.asyncio
async def test_middleware_swaps_auth_header(middleware):
    mw, app = middleware
    manager = mw.manager
    key = _make_valid_key(manager)

    body = b'{"model": "test", "messages": []}'
    scope = _make_scope(api_key=key, body=body)
    receive = _make_receive(body)
    send = _CollectSend()

    await mw(scope, receive, send)

    # Downstream app should see the master key, not the cgym key
    received = app.received_headers[0]
    assert received.get("x-api-key") == INTERNAL_MASTER_KEY


@pytest.mark.asyncio
async def test_middleware_health_passthrough(middleware):
    mw, app = middleware
    scope = _make_scope(path="/health/liveliness", method="GET", body=b"")
    receive = _make_receive(b"")
    send = _CollectSend()

    await mw(scope, receive, send)
    # Health endpoints pass through to the app (which is litellm's own handler
    # in production; here our _CaptureApp stands in)
    assert app.call_count == 1


@pytest.mark.asyncio
async def test_middleware_rejects_invalid_key(middleware):
    mw, app = middleware
    body = b'{"model": "test", "messages": []}'
    scope = _make_scope(api_key="invalid-key", body=body)
    receive = _make_receive(body)
    send = _CollectSend()

    await mw(scope, receive, send)

    assert send.status == 401
    assert app.call_count == 0


@pytest.mark.asyncio
async def test_middleware_rejects_missing_key(middleware):
    mw, app = middleware
    scope = _make_scope(api_key="", body=b'{"model": "test"}')
    receive = _make_receive(b'{"model": "test"}')
    send = _CollectSend()

    await mw(scope, receive, send)

    assert send.status == 401
    assert app.call_count == 0


@pytest.mark.asyncio
async def test_middleware_count_tokens_passes_through(middleware):
    """/v1/messages/count_tokens now passes through to the downstream app
    (litellm), whose endpoint is patched to forward to OUR upstream (360
    native count_tokens). The old local estimate (~4 chars/token,
    messages-only) under-counted and skewed cc's context accounting."""
    mw, app = middleware
    manager = mw.manager
    key = _make_valid_key(manager)

    body = json.dumps(
        {
            "model": "deepseek-v4.1-flash",
            "messages": [{"role": "user", "content": "hello world"}],
            "system": "You are a test.",
            "tools": [{"name": "bash", "description": "run bash"}],
        }
    ).encode()
    scope = _make_scope(path="/v1/messages/count_tokens", api_key=key, body=body)
    receive = _make_receive(body)
    send = _CollectSend()

    await mw(scope, receive, send)

    # Reaches the downstream app (litellm count_tokens route)
    assert app.call_count == 1
    # Body forwarded intact (incl. system + tools)
    forwarded = json.loads(app.received_bodies[0])
    assert forwarded["system"] == "You are a test."
    assert forwarded["tools"][0]["name"] == "bash"
    # Auth header swapped to master key
    assert app.received_headers[0].get("x-api-key") == INTERNAL_MASTER_KEY


# ── Concurrency test: the critical regression test ────────────────────


@pytest.mark.asyncio
async def test_concurrent_requests_body_isolation(middleware):
    """Critical regression test: concurrent requests must not clobber
    each other's _ReplayReceive state.

    This is the exact bug that caused proxy event loop to freeze:
    closures captured shared _sent[0], so request A's receive would
    return request B's body (or empty), causing litellm to block.
    """
    mw, app = middleware
    manager = mw.manager

    # Launch 30 concurrent requests with distinct bodies
    bodies = [
        json.dumps(
            {"model": "test", "messages": [{"role": "user", "content": f"request-{i}"}]}
        ).encode()
        for i in range(30)
    ]
    keys = [_make_valid_key(manager) for _ in range(30)]

    async def single_request(idx):
        body = bodies[idx]
        scope = _make_scope(api_key=keys[idx], body=body)
        receive = _make_receive(body)
        send = _CollectSend()
        await mw(scope, receive, send)
        return send.status

    # Run all 30 concurrently
    statuses = await asyncio.gather(*[single_request(i) for i in range(30)])

    # All should succeed (200)
    assert all(s == 200 for s in statuses), f"Some requests failed: {statuses}"
    assert app.call_count == 30

    # Each request must have received its OWN body, not someone else's
    for i, received in enumerate(app.received_bodies):
        expected = bodies[i]
        assert received == expected, (
            f"Request {i} got wrong body: expected {expected!r}, got {received!r}"
        )


@pytest.mark.asyncio
async def test_concurrent_requests_header_isolation(middleware):
    """Each concurrent request must get the master key swapped in its
    own scope, not a shared one."""
    mw, app = middleware
    manager = mw.manager

    keys = [_make_valid_key(manager) for _ in range(20)]
    bodies = [b'{"model": "test", "messages": []}'] * 20

    async def single_request(idx):
        scope = _make_scope(api_key=keys[idx], body=bodies[idx])
        receive = _make_receive(bodies[idx])
        send = _CollectSend()
        await mw(scope, receive, send)
        return send.status

    statuses = await asyncio.gather(*[single_request(i) for i in range(20)])

    assert all(s == 200 for s in statuses)
    # All should have received the master key
    for headers in app.received_headers:
        assert headers.get("x-api-key") == INTERNAL_MASTER_KEY


# ── Budget endpoint test ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_budget_endpoint_requires_admin_key(manager):
    app = _CaptureApp()
    mw = BudgetAuthMiddleware(
        app=app,
        manager=manager,
        master_key=INTERNAL_MASTER_KEY,
        block_web_search=False,
    )

    scope = _make_scope(
        path="/budget/generate_key", method="POST", body=b'{"max_budget": 10}'
    )
    receive = _make_receive(b'{"max_budget": 10}')
    send = _CollectSend()

    await mw(scope, receive, send)

    # No admin key → 401
    assert send.status == 401
    assert app.call_count == 0


@pytest.mark.asyncio
async def test_non_inference_route_rejected(manager):
    app = _CaptureApp()
    mw = BudgetAuthMiddleware(
        app=app,
        manager=manager,
        master_key=INTERNAL_MASTER_KEY,
        block_web_search=False,
    )
    key = _make_valid_key(manager)

    scope = _make_scope(path="/admin/users", api_key=key, body=b"")
    receive = _make_receive(b"")
    send = _CollectSend()

    await mw(scope, receive, send)

    assert send.status == 403
    assert app.call_count == 0


# ── Stress test: high concurrency with mixed body sizes ────────────────


@pytest.mark.asyncio
async def test_high_concurrency_mixed_body_sizes(middleware):
    """Simulate real proxy load: 50 concurrent requests with varying
    body sizes (small preflight 'hi' + large inference requests)."""
    mw, app = middleware
    manager = mw.manager

    bodies = []
    keys = []
    for i in range(50):
        if i % 5 == 0:
            # Small preflight body (like run_as.sh's 'hi' test)
            b = b'{"model": "test", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 4}'
        else:
            # Larger body (simulating real inference request)
            content = "x" * (1000 * (i + 1))
            b = json.dumps(
                {
                    "model": "test",
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 8192,
                }
            ).encode()
        bodies.append(b)
        keys.append(_make_valid_key(manager))

    async def single_request(idx):
        scope = _make_scope(api_key=keys[idx], body=bodies[idx])
        receive = _make_receive(bodies[idx])
        send = _CollectSend()
        await mw(scope, receive, send)
        return send.status, idx

    results = await asyncio.gather(*[single_request(i) for i in range(50)])

    for status, idx in results:
        assert status == 200, f"Request {idx} failed with status {status}"
        assert app.received_bodies[idx] == bodies[idx], (
            f"Request {idx} body mismatch: expected {len(bodies[idx])} bytes, "
            f"got {len(app.received_bodies[idx])} bytes"
        )

    assert app.call_count == 50
