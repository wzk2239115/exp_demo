"""
agent_id, token

token: hex(len(task_id) (one byte) + task_info + checksum + random_data)
checksum = sha256(agent_id + task_info + salt)


len(task_info) <= 30
len(checksum) = 32

len(token_bytes) <= 62

Both the token salt and the flag seed are per-deployment secrets: an agent that
learns them can forge a task token or derive the expected flag without
exploiting anything. They are therefore never hardcoded — the controller mints
fresh ones on startup (see ``cybergym.server.types.ServerConfig``) and every
helper here requires the value to be passed in explicitly.
"""

import base64
import hashlib
import hmac
import os
from uuid import uuid4

MAX_TASK_ID_LENGTH = 63
TOKEN_BYTE_LENGTH = 96


def generate_secret(prefix: str) -> str:
    """Mint a fresh random secret, e.g. ``generate_secret("cg")`` → ``cg-<uuid4>``."""
    return f"{prefix}-{uuid4()}"


def require_secret(value: str | None, *, name: str, env_var: str) -> str:
    """Return *value*, rejecting an unset or blank secret.

    Args:
        value: The configured secret, or None/"" when unconfigured.
        name: Human-readable name used in the error message.
        env_var: Environment variable that can supply the value.

    Raises:
        ValueError: If *value* is not set.
    """
    if not value:
        raise ValueError(
            f"{name} is not configured. It is a per-deployment secret shared with "
            f"the controller: export {env_var}=<value> (the controller logs the "
            "values it generated at startup), or pass it explicitly."
        )
    return value


def resolve_secret(value: str | None, *, name: str, env_var: str) -> str:
    """Return *value*, falling back to ``os.environ[env_var]``.

    Raises:
        ValueError: If neither the argument nor the environment supplies it.
    """
    candidate = os.environ.get(env_var) if value is None else value
    return require_secret(candidate, name=name, env_var=env_var)


def generate_token(
    task_info: str, *, salt: str, agent_id: str | None = None
) -> tuple[str, str]:
    task_info_len = len(task_info)
    if task_info_len > MAX_TASK_ID_LENGTH:
        raise ValueError("task_info is too long")
    if not salt:
        raise ValueError("salt must be a non-empty per-deployment secret")
    if agent_id is None:
        agent_id = uuid4().hex
    checksum = hashlib.sha256(f"{agent_id}{task_info}{salt}".encode()).digest()
    token_bytes = bytes([task_info_len]) + task_info.encode() + checksum
    # Pad with random bytes to reach TOKEN_BYTE_LENGTH
    token_bytes += uuid4().bytes
    token_bytes = token_bytes[:TOKEN_BYTE_LENGTH]
    token = base64.urlsafe_b64encode(token_bytes).decode()
    return agent_id, token


def generate_flag(task_id: str, *, seed: str) -> str:
    """Derive a deterministic flag from *seed* and *task_id* via HMAC-SHA256.

    Returns a string like ``flag{<hex>}`` (32 hex chars).
    """
    if not seed:
        raise ValueError("seed must be a non-empty per-deployment secret")
    mac = hmac.new(seed.encode(), task_id.encode(), hashlib.sha256).hexdigest()
    return f"flag{{{mac[:32]}}}"


def verify_token(agent_id: str, token: str, *, salt: str) -> str | None:
    if not salt:
        raise ValueError("salt must be a non-empty per-deployment secret")
    try:
        token_bytes = base64.urlsafe_b64decode(token.encode())
        task_info_len = token_bytes[0]
        task_info = token_bytes[1 : 1 + task_info_len].decode()
        checksum = token_bytes[1 + task_info_len : 1 + task_info_len + 32]
        expected_checksum = hashlib.sha256(
            f"{agent_id}{task_info}{salt}".encode()
        ).digest()
        if hmac.compare_digest(checksum, expected_checksum):
            return task_info
    except Exception:
        pass
    return None
