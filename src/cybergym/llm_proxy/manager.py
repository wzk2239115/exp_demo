"""API key manager that talks to the CyberGym proxy.

Drop-in replacement for LiteLLMAPIKeyManager. Generates keys with
budgets, tracks spend, and cleans up via the proxy's /budget/ endpoints.

The proxy wraps litellm and supports Anthropic, OpenAI, Vertex AI, etc.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Under high concurrency (30+ workers) the proxy's event loop may take
# >10s to respond to budget endpoints while processing inference requests.
# Use a generous timeout with retry to survive startup spikes.
_BUDGET_TIMEOUT = 30.0
_BUDGET_RETRIES = 3
_BUDGET_RETRY_DELAY = 2.0


class ProxyKeyManager:
    """Manage API keys via the CyberGym proxy.

    Usage::

        manager = ProxyKeyManager(
            proxy_url="http://localhost:4000",
            admin_key="cgym-admin-...",
        )
        key = manager.generate_api_key(max_budget=10.0)
        # pass manager.api_base_url as api_base_url, key as api_key
        usage = manager.get_api_key_usage(key)
        manager.delete_api_key(key)
    """

    def __init__(
        self,
        proxy_url: str = "http://localhost:4000",
        default_max_budget: float = 20.0,
        admin_key: str | None = None,
        default_allowed_models: list[str] | None = None,
    ):
        self.proxy_url = proxy_url.rstrip("/")
        self.default_max_budget = default_max_budget
        self.admin_key = admin_key
        self.default_allowed_models = default_allowed_models
        self._alive_keys: set[str] = set()

    @property
    def api_base_url(self) -> str:
        return self.proxy_url

    def _admin_headers(self) -> dict[str, str]:
        if self.admin_key:
            return {"x-admin-key": self.admin_key}
        return {}

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Send a budget request with retry on timeout/connection error."""
        last_exc: Exception | None = None
        for attempt in range(_BUDGET_RETRIES):
            try:
                with httpx.Client(
                    base_url=self.proxy_url,
                    timeout=_BUDGET_TIMEOUT,
                    headers=self._admin_headers(),
                ) as client:
                    resp = getattr(client, method)(url, **kwargs)
                    resp.raise_for_status()
                    return resp
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                logger.warning(
                    "Budget request %s %s failed (attempt %d/%d): %s",
                    method,
                    url,
                    attempt + 1,
                    _BUDGET_RETRIES,
                    e,
                )
                if attempt < _BUDGET_RETRIES - 1:
                    time.sleep(_BUDGET_RETRY_DELAY)
        raise last_exc  # type: ignore[misc]

    def generate_api_key(
        self,
        max_budget: float | None = None,
        allowed_models: list[str] | None = None,
    ) -> str:
        budget = max_budget or self.default_max_budget
        models = (
            allowed_models
            if allowed_models is not None
            else self.default_allowed_models
        )
        logger.debug(
            "Requesting new key from proxy (budget $%.2f, models=%s)",
            budget,
            models or "any",
        )
        payload: dict = {"max_budget": budget}
        if models:
            payload["allowed_models"] = list(models)
        resp = self._request_with_retry("post", "/budget/generate_key", json=payload)
        key = resp.json()["key"]
        self._alive_keys.add(key)
        logger.info(
            "Generated proxy key %s...%s (budget $%.2f)", key[:8], key[-4:], budget
        )
        return key

    def get_api_key_usage(self, api_key: str) -> dict:
        key_hint = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else api_key
        logger.debug("Fetching usage for key %s", key_hint)
        resp = self._request_with_retry("get", f"/budget/usage/{api_key}")
        data = resp.json()
        logger.debug(
            "Usage for %s: spend=$%.4f remaining=$%.4f requests=%d",
            key_hint,
            data.get("spend", 0),
            data.get("remaining", 0),
            data.get("requests", 0),
        )
        return data

    def delete_api_key(self, api_key: str):
        key_hint = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else api_key
        logger.debug("Deleting key %s from proxy", key_hint)
        self._request_with_retry("delete", f"/budget/key/{api_key}")
        self._alive_keys.discard(api_key)
        logger.info("Deleted proxy key %s...%s", api_key[:8], api_key[-4:])

    def revoke_all(self):
        """Delete all alive keys tracked by this manager."""
        logger.debug("Revoking all %d alive keys", len(self._alive_keys))
        for key in list(self._alive_keys):
            try:
                self.delete_api_key(key)
            except Exception as e:
                logger.warning("Failed to revoke key: %s", e)
