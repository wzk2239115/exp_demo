"""In-memory per-key budget tracking for Anthropic API proxy.

Each key has a max budget (USD). Spend is accumulated from response usage.
Requests are rejected when the key's budget is exhausted.

Cost calculation is delegated to litellm's model cost database.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from uuid import uuid4

from litellm import completion_cost
from litellm.types.utils import Choices, Message, ModelResponse, Usage

logger = logging.getLogger(__name__)


def calculate_cost(model: str, usage: dict) -> float:
    """Calculate USD cost from Anthropic API usage dict using litellm."""
    try:
        resp = ModelResponse(
            model=model,
            choices=[
                Choices(
                    message=Message(role="assistant", content=""),
                    index=0,
                    finish_reason="end_turn",
                )
            ],
            usage=Usage(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            ),
        )
        return completion_cost(completion_response=resp)
    except Exception as e:
        logger.warning("Failed to calculate cost for model %s: %s", model, e)
        return 0.0


@dataclass
class ModelUsage:
    """Per-model token & request counters within a single key's record."""

    spend: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 0

    def as_dict(self) -> dict:
        return {
            "spend": self.spend,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "requests": self.requests,
        }


@dataclass
class KeyRecord:
    key: str
    max_budget: float
    # Models this key may call. None means no restriction (any model). Matched
    # exactly against the model string in the request (body `model` or, for
    # Gemini, the route path).
    allowed_models: frozenset[str] | None = None
    spend: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    # Subset of output_tokens spent on hidden reasoning (OpenAI o-series).
    # Anthropic extended-thinking also consumes output budget but is not
    # separately reported by the API, so this stays 0 for Anthropic models.
    reasoning_tokens: int = 0
    requests: int = 0
    # Per-model breakdown. Top-level counters above remain the sum across
    # all models so existing consumers reading `input_tokens`, `requests`
    # etc. don't need to change. Useful when an agent CLI fans out to a
    # main model plus auxiliary helpers (e.g. Gemini CLI's classifier
    # calls to gemini-flash) — each lands in its own bucket here.
    per_model: dict[str, ModelUsage] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class BudgetManager:
    """Thread-safe in-memory budget manager for API keys."""

    def __init__(self, default_max_budget: float = 20.0):
        self.default_max_budget = default_max_budget
        self._keys: dict[str, KeyRecord] = {}
        self._lock = threading.Lock()

    def generate_key(
        self,
        max_budget: float | None = None,
        allowed_models: list[str] | None = None,
    ) -> str:
        """Create a new API key with a budget. Returns the key string.

        If *allowed_models* is given, the key may only call those models
        (matched exactly against the request's model string); None allows any.
        """
        key = f"cgym-{uuid4().hex[:24]}"
        budget = max_budget or self.default_max_budget
        allowed = frozenset(allowed_models) if allowed_models else None
        with self._lock:
            self._keys[key] = KeyRecord(
                key=key, max_budget=budget, allowed_models=allowed
            )
        logger.info(
            "Generated key %s...%s with budget $%.2f (models=%s)",
            key[:8],
            key[-4:],
            budget,
            sorted(allowed) if allowed else "any",
        )
        return key

    def validate_key(self, key: str) -> KeyRecord | None:
        """Check if key exists and has remaining budget. Returns record or None."""
        key_hint = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
        with self._lock:
            record = self._keys.get(key)
        if record is None:
            logger.debug("validate_key: %s not found", key_hint)
            return None
        if record.spend >= record.max_budget:
            logger.debug(
                "validate_key: %s budget exhausted ($%.4f / $%.2f)",
                key_hint,
                record.spend,
                record.max_budget,
            )
            return None
        logger.debug(
            "validate_key: %s OK (spend $%.4f / $%.2f, %d requests)",
            key_hint,
            record.spend,
            record.max_budget,
            record.requests,
        )
        return record

    def record_usage(
        self, key: str, model: str, usage: dict, cost: float | None = None
    ) -> float:
        """Record usage for a key. Returns the cost of this request.

        If cost is provided (e.g. from litellm callback), uses it directly.
        Otherwise calculates from usage dict.
        """
        key_hint = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
        if cost is None:
            cost = calculate_cost(model, usage)
            logger.debug(
                "record_usage: calculated cost $%.6f for %s on model %s",
                cost,
                key_hint,
                model,
            )
        else:
            logger.debug(
                "record_usage: using provided cost $%.6f for %s on model %s",
                cost,
                key_hint,
                model,
            )
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_create = usage.get("cache_creation_input_tokens", 0)
        reasoning = usage.get("reasoning_tokens", 0)
        with self._lock:
            record = self._keys.get(key)
            if record is None:
                logger.debug("record_usage: key %s not found, skipping", key_hint)
                return cost
            record.spend += cost
            record.input_tokens += in_tokens
            record.output_tokens += out_tokens
            record.cache_read_tokens += cache_read
            record.cache_creation_tokens += cache_create
            record.reasoning_tokens += reasoning
            record.requests += 1
            # Per-model bucket. Empty/missing model name still gets its own
            # bucket so it's visible rather than silently merged.
            mu = record.per_model.setdefault(model or "", ModelUsage())
            mu.spend += cost
            mu.input_tokens += in_tokens
            mu.output_tokens += out_tokens
            mu.cache_read_tokens += cache_read
            mu.cache_creation_tokens += cache_create
            mu.reasoning_tokens += reasoning
            mu.requests += 1
            logger.debug(
                "record_usage: %s now at $%.4f / $%.2f (%d requests, %d in + %d out tokens; "
                "per-model %s: $%.4f / %d req)",
                key_hint,
                record.spend,
                record.max_budget,
                record.requests,
                record.input_tokens,
                record.output_tokens,
                model or "<unknown>",
                mu.spend,
                mu.requests,
            )
        return cost

    def get_usage(self, key: str) -> dict | None:
        """Get usage info for a key.

        Top-level fields are aggregated across all models. The ``models``
        field maps each model name to its own counter dict (same schema
        as the top-level totals minus ``max_budget``/``remaining``).
        """
        with self._lock:
            record = self._keys.get(key)
            if record is None:
                return None
            per_model = {
                name: usage.as_dict() for name, usage in record.per_model.items()
            }
            return {
                "key": record.key,
                "spend": record.spend,
                "max_budget": record.max_budget,
                "remaining": max(0, record.max_budget - record.spend),
                "allowed_models": (
                    sorted(record.allowed_models) if record.allowed_models else None
                ),
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "cache_read_tokens": record.cache_read_tokens,
                "cache_creation_tokens": record.cache_creation_tokens,
                "reasoning_tokens": record.reasoning_tokens,
                "requests": record.requests,
                "models": per_model,
                "created_at": record.created_at,
            }

    def delete_key(self, key: str) -> dict | None:
        """Delete a key and return its final usage."""
        key_hint = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
        usage = self.get_usage(key)
        with self._lock:
            self._keys.pop(key, None)
        if usage:
            logger.debug(
                "Deleted key %s (final spend $%.4f / $%.2f, %d requests)",
                key_hint,
                usage["spend"],
                usage["max_budget"],
                usage["requests"],
            )
        else:
            logger.debug("delete_key: %s not found", key_hint)
        return usage
