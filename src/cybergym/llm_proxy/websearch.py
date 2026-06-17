"""Detect requests that let a model fetch external content via the provider.

The proxy uses this as a fail-closed guard. The threat is *provider-side*
retrieval/egress: features the LLM provider runs on its own servers (not in the
firewalled agent container), so they reach the open web / external data
regardless of the container's network isolation. Covered vectors:

  * Web search / web fetch tools (Anthropic, OpenAI, Gemini grounding).
  * Gemini URL context and enterprise web search.
  * Remote MCP tools / connectors (OpenAI ``mcp`` tool, Anthropic
    ``mcp_servers``, ``server_url`` / ``connector_id``).
  * Remote file / URL / image inputs (``file_url``, ``image_url``, Gemini
    ``file_uri``, Anthropic URL document sources). Inline ``data:`` images are
    allowed (no external fetch).
  * Server-side code execution (OpenAI ``code_interpreter``, Anthropic
    ``code_execution``), hosted retrieval (``file_search``), and hosted shells
    with outbound network (``network_policy``).
  * Hosted web-search and deep-research model names.

Client-side tools the agent runs itself are NOT matched — they execute inside
the firewalled container: OpenAI ``function`` tools, Anthropic custom tools
(``input_schema``), and the client-executed ``bash`` / ``text_editor`` /
``computer`` tools.

This is a *vendored* detector (not imported from litellm) so the guard does not
depend on litellm-internal modules. Each rule links to the provider API docs.
"""

import re

# --- Rule 1: model names -------------------------------------------------------
# Hosted web-search models search the web on every request; deep-research models
# REQUIRE an external data source (web search / MCP / file search), so deny them
# outright. The leading \b keeps "search"/"research" from matching inside
# unrelated names (e.g. "deep-research" must not trip on "research").
#   *-search-preview / *-search-api:
#     https://developers.openai.com/api/docs/guides/tools-web-search
#   *-deep-research:
#     https://platform.openai.com/docs/guides/deep-research
_BLOCKED_MODEL_RE = re.compile(
    r"\bsearch-(?:preview|api)\b|\bdeep-research\b", re.IGNORECASE
)

# Model embedded in a Gemini-style route path, e.g.
# /v1beta/models/<model>:generateContent
_PATH_MODEL_RE = re.compile(r"/models/([^/:]+)")

# --- Rule 2: top-level params --------------------------------------------------
# OpenAI Chat Completions web search:
#   https://platform.openai.com/docs/api-reference/chat/create#chat-create-web_search_options
# Anthropic MCP connector list:
#   https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector
_BLOCKED_TOP_LEVEL_KEYS = ("web_search_options", "mcp_servers")

# --- Rule 3: tools -------------------------------------------------------------
# Provider-hosted tool `type`s matched by prefix (the version suffix varies):
#   web_search* / web_fetch* — Anthropic & OpenAI web search / fetch
#     https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool
#     https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-fetch-tool
#     https://developers.openai.com/api/docs/guides/tools-web-search
#   code_execution*          — Anthropic server-side code execution (has egress)
#     https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool
_BLOCKED_TOOL_TYPE_PREFIXES = ("web_search", "web_fetch", "code_execution")
# ... and by exact match:
#   mcp                       — OpenAI remote MCP tool (https://developers.openai.com/api/docs/mcp)
#   code_interpreter / file_search — OpenAI hosted execution / retrieval
_BLOCKED_TOOL_TYPES = frozenset({"mcp", "code_interpreter", "file_search"})

# Web-search tool *names* used across formats: LiteLLM standard, Claude Code's
# Anthropic-native name, and the legacy interception marker.
_WEB_SEARCH_TOOL_NAMES = frozenset({"litellm_web_search", "web_search", "WebSearch"})

# Gemini grounding / retrieval tool keys (snake_case and camelCase).
#   google_search(_retrieval): https://ai.google.dev/gemini-api/docs/google-search
#   url_context:               https://ai.google.dev/gemini-api/docs/url-context
#   enterprise_web_search:     https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/web-grounding-enterprise
_GEMINI_RETRIEVAL_KEYS = frozenset(
    {
        "google_search",
        "googleSearch",
        "google_search_retrieval",
        "googleSearchRetrieval",
        "url_context",
        "urlContext",
        "enterprise_web_search",
        "enterpriseWebSearch",
    }
)

# --- Rule 4: remote-fetch fields anywhere in the body --------------------------
# String-valued fields that point the provider at an external resource. We
# require a string value so a custom function tool that merely *declares* a
# parameter named e.g. "file_url" in its JSON schema is not flagged.
#   file_url            — OpenAI Responses input_file by URL
#     https://platform.openai.com/docs/api-reference/responses
#   server_url          — remote MCP server endpoint
#   connector_id        — hosted connector id (https://developers.openai.com/api/docs/mcp)
#   file_uri / fileUri  — Gemini external file/URI input (YouTube, GCS, …)
#     https://ai.google.dev/gemini-api/docs/video-understanding
_BLOCKED_FETCH_KEYS = frozenset(
    {"file_url", "server_url", "connector_id", "file_uri", "fileUri"}
)


def _is_external_url(value: object) -> bool:
    """True if *value* is a remote image URL (string or {"url": ...}), not inline data.

    Handles OpenAI's two image_url shapes — Chat Completions
    ``{"image_url": {"url": "https://..."}}`` and Responses
    ``{"image_url": "https://..."}`` — and lets inline ``data:`` URIs through
    since those carry no external fetch.
    https://developers.openai.com/api/docs/guides/images-vision
    """
    if isinstance(value, dict):
        value = value.get("url")
    return isinstance(value, str) and bool(value) and not value.startswith("data:")


def _blocked_tool_label(tool: object) -> str | None:
    """Return a label if *tool* is a provider-hosted retrieval/egress tool."""
    if not isinstance(tool, dict):
        return None

    tool_type = tool.get("type")
    if isinstance(tool_type, str):
        if tool_type.startswith(_BLOCKED_TOOL_TYPE_PREFIXES):
            return tool_type
        if tool_type in _BLOCKED_TOOL_TYPES:
            return tool_type

    if tool.get("name") in _WEB_SEARCH_TOOL_NAMES:
        return tool["name"]

    # OpenAI Chat Completions wraps tools as {"type": "function", "function": {...}}.
    if tool_type == "function" and isinstance(tool.get("function"), dict):
        if tool["function"].get("name") in _WEB_SEARCH_TOOL_NAMES:
            return tool["function"]["name"]

    matched = _GEMINI_RETRIEVAL_KEYS.intersection(tool)
    if matched:
        return next(iter(matched))

    return None


def _find_remote_fetch(node: object) -> str | None:
    """Recursively find a remote-fetch field (file_url / image_url / MCP / …)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _BLOCKED_FETCH_KEYS and isinstance(value, str) and value:
                return key
            # Remote image input (OpenAI), in string or {"url": ...} form. Inline
            # data: URIs are allowed since they carry no external fetch.
            if key == "image_url" and _is_external_url(value):
                return "image_url"
            # Hosted shell with outbound network access (OpenAI shell tool). The
            # client-executed local_shell carries no network_policy.
            # https://developers.openai.com/api/docs/guides/tools-shell
            if key == "network_policy" and value:
                return "shell network_policy"
            # Anthropic document/image URL source: {"type": "url", "url": "..."}.
            # https://docs.anthropic.com/en/docs/build-with-claude/files
            if key == "type" and value == "url" and "url" in node:
                return "url source"
            found = _find_remote_fetch(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_remote_fetch(item)
            if found:
                return found
    return None


def find_web_search(body: object, path: str = "") -> str | None:
    """Return a short reason if the request would fetch external content, else None.

    *body* is the parsed JSON request body (or None); *path* is the request URL
    path (used to catch a model named in a Gemini-style route).
    """
    # Rule 1 — blocked model in the body or the route path.
    models: list[str] = []
    if isinstance(body, dict) and isinstance(body.get("model"), str):
        models.append(body["model"])
    path_match = _PATH_MODEL_RE.search(path or "")
    if path_match:
        models.append(path_match.group(1))
    for model in models:
        if _BLOCKED_MODEL_RE.search(model):
            return f"web-search/deep-research model '{model}'"

    if not isinstance(body, dict):
        return None

    # Rule 2 — top-level params (web_search_options, mcp_servers). Presence is
    # enough: an empty `web_search_options: {}` still enables web search.
    for key in _BLOCKED_TOP_LEVEL_KEYS:
        if body.get(key) is not None:
            return f"'{key}'"

    # Rule 3 — provider-hosted tools (any provider format).
    tools = body.get("tools")
    if isinstance(tools, dict):  # Gemini may send a single tool object.
        tools = [tools]
    if isinstance(tools, list):
        for tool in tools:
            label = _blocked_tool_label(tool)
            if label is not None:
                return f"tool '{label}'"

    # Rule 4 — remote-fetch fields anywhere (file_url, MCP url, URL sources).
    found = _find_remote_fetch(body)
    if found:
        return found

    return None
