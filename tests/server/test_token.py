"""Unit tests for cybergym.task.token module."""

import pytest

from cybergym.task.token import (
    DEFAULT_FLAG_SEED,
    DEFAULT_SALT,
    generate_flag,
    generate_token,
    verify_token,
)


class TestGenerateFlag:
    """Tests for generate_flag function."""

    def test_deterministic(self):
        """Same seed + task_id always produces the same flag."""
        f1 = generate_flag("v8:abc123", seed="myseed")
        f2 = generate_flag("v8:abc123", seed="myseed")
        assert f1 == f2

    def test_format(self):
        """Flag has format flag{<32 hex chars>}."""
        flag = generate_flag("task1", seed="seed")
        assert flag.startswith("flag{")
        assert flag.endswith("}")
        hex_part = flag[5:-1]
        assert len(hex_part) == 32
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_different_task_ids(self):
        """Different task_ids produce different flags."""
        f1 = generate_flag("v8:abc123", seed="seed")
        f2 = generate_flag("v8:def456", seed="seed")
        assert f1 != f2

    def test_different_seeds(self):
        """Different seeds produce different flags."""
        f1 = generate_flag("task1", seed="seed_a")
        f2 = generate_flag("task1", seed="seed_b")
        assert f1 != f2

    def test_default_seed(self):
        """Calling without seed uses DEFAULT_FLAG_SEED."""
        f1 = generate_flag("task1")
        f2 = generate_flag("task1", seed=DEFAULT_FLAG_SEED)
        assert f1 == f2

    def test_empty_task_id(self):
        """Empty task_id still produces a valid flag."""
        flag = generate_flag("", seed="seed")
        assert flag.startswith("flag{") and flag.endswith("}")

    def test_long_task_id(self):
        """Long task_id works correctly."""
        flag = generate_flag("kernel:abc123def456/63", seed="seed")
        assert flag.startswith("flag{") and flag.endswith("}")

    def test_special_characters_in_task_id(self):
        """Task IDs with slashes and colons produce valid flags."""
        flag = generate_flag("kernel:abc123def456/9", seed="seed")
        assert flag.startswith("flag{") and flag.endswith("}")
        assert len(flag) == 38


class TestGenerateToken:
    """Tests for generate_token function."""

    def test_returns_agent_id_and_token(self):
        result = generate_token("task1")
        assert isinstance(result, tuple)
        assert len(result) == 2
        agent_id, token = result
        assert isinstance(agent_id, str)
        assert isinstance(token, str)

    def test_auto_generates_agent_id(self):
        agent_id, _ = generate_token("task1")
        assert len(agent_id) == 32  # uuid4 hex

    def test_custom_agent_id(self):
        agent_id, _ = generate_token("task1", agent_id="my_agent")
        assert agent_id == "my_agent"

    def test_task_info_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            generate_token("x" * 64)

    def test_max_length_task_info(self):
        """Task info at exactly MAX_TASK_ID_LENGTH should work."""
        agent_id, token = generate_token("x" * 63)
        assert agent_id is not None
        assert token is not None


class TestVerifyToken:
    """Tests for verify_token function."""

    def test_roundtrip(self):
        """generate_token → verify_token recovers task_info."""
        agent_id, token = generate_token("v8:abc123")
        task_info = verify_token(agent_id, token)
        assert task_info == "v8:abc123"

    def test_roundtrip_with_custom_salt(self):
        agent_id, token = generate_token("task1", salt="custom")
        assert verify_token(agent_id, token, salt="custom") == "task1"

    def test_wrong_salt_fails(self):
        agent_id, token = generate_token("task1", salt="salt_a")
        assert verify_token(agent_id, token, salt="salt_b") is None

    def test_wrong_agent_id_fails(self):
        agent_id, token = generate_token("task1")
        assert verify_token("wrong_agent", token) is None

    def test_corrupted_token_fails(self):
        agent_id, token = generate_token("task1")
        assert verify_token(agent_id, token + "x") is None

    def test_empty_token_fails(self):
        assert verify_token("agent", "") is None

    def test_default_salt(self):
        agent_id, token = generate_token("task1")
        result = verify_token(agent_id, token, salt=DEFAULT_SALT)
        assert result == "task1"

    def test_complex_task_info(self):
        """Verify tokens with slashes and special chars in task_info."""
        task_info = "kernel:abc123def456/63"
        agent_id, token = generate_token(task_info)
        assert verify_token(agent_id, token) == task_info
