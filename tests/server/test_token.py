"""Unit tests for cybergym.task.token module."""

import pytest

from cybergym.task.token import (
    generate_flag,
    generate_secret,
    generate_token,
    require_secret,
    resolve_secret,
    verify_token,
)

SALT = "test_salt"


class TestGenerateSecret:
    """Tests for generate_secret function."""

    def test_prefixed_and_unique(self):
        s1 = generate_secret("cg")
        s2 = generate_secret("cg")
        assert s1.startswith("cg-") and s2.startswith("cg-")
        assert s1 != s2

    def test_uuid_shaped_suffix(self):
        suffix = generate_secret("sf").removeprefix("sf-")
        assert len(suffix) == 36  # uuid4 with dashes


class TestRequireSecret:
    """Tests for require_secret function."""

    def test_returns_value(self):
        assert require_secret("abc", name="Salt", env_var="CG_SALT") == "abc"

    @pytest.mark.parametrize("missing", [None, ""])
    def test_rejects_missing(self, missing):
        with pytest.raises(ValueError, match="CG_SALT"):
            require_secret(missing, name="Salt", env_var="CG_SALT")


class TestResolveSecret:
    """Tests for resolve_secret function."""

    def test_argument_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("CG_SALT", "from_env")
        assert resolve_secret("explicit", name="Salt", env_var="CG_SALT") == "explicit"

    def test_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("CG_SALT", "from_env")
        assert resolve_secret(None, name="Salt", env_var="CG_SALT") == "from_env"

    def test_rejects_when_unset(self, monkeypatch):
        monkeypatch.delenv("CG_SALT", raising=False)
        with pytest.raises(ValueError, match="Salt is not configured"):
            resolve_secret(None, name="Salt", env_var="CG_SALT")


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

    def test_seed_is_required(self):
        """There is no default seed — it must be passed explicitly."""
        with pytest.raises(TypeError):
            generate_flag("task1")  # type: ignore[call-arg]

    def test_empty_seed_rejected(self):
        with pytest.raises(ValueError, match="seed"):
            generate_flag("task1", seed="")

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
        result = generate_token("task1", salt=SALT)
        assert isinstance(result, tuple)
        assert len(result) == 2
        agent_id, token = result
        assert isinstance(agent_id, str)
        assert isinstance(token, str)

    def test_auto_generates_agent_id(self):
        agent_id, _ = generate_token("task1", salt=SALT)
        assert len(agent_id) == 32  # uuid4 hex

    def test_custom_agent_id(self):
        agent_id, _ = generate_token("task1", salt=SALT, agent_id="my_agent")
        assert agent_id == "my_agent"

    def test_task_info_too_long(self):
        with pytest.raises(ValueError, match="too long"):
            generate_token("x" * 64, salt=SALT)

    def test_max_length_task_info(self):
        """Task info at exactly MAX_TASK_ID_LENGTH should work."""
        agent_id, token = generate_token("x" * 63, salt=SALT)
        assert agent_id is not None
        assert token is not None

    def test_salt_is_required(self):
        """There is no default salt — it must be passed explicitly."""
        with pytest.raises(TypeError):
            generate_token("task1")  # type: ignore[call-arg]

    def test_empty_salt_rejected(self):
        with pytest.raises(ValueError, match="salt"):
            generate_token("task1", salt="")


class TestVerifyToken:
    """Tests for verify_token function."""

    def test_roundtrip(self):
        """generate_token → verify_token recovers task_info."""
        agent_id, token = generate_token("v8:abc123", salt=SALT)
        task_info = verify_token(agent_id, token, salt=SALT)
        assert task_info == "v8:abc123"

    def test_roundtrip_with_custom_salt(self):
        agent_id, token = generate_token("task1", salt="custom")
        assert verify_token(agent_id, token, salt="custom") == "task1"

    def test_wrong_salt_fails(self):
        agent_id, token = generate_token("task1", salt="salt_a")
        assert verify_token(agent_id, token, salt="salt_b") is None

    def test_wrong_agent_id_fails(self):
        agent_id, token = generate_token("task1", salt=SALT)
        assert verify_token("wrong_agent", token, salt=SALT) is None

    def test_corrupted_token_fails(self):
        agent_id, token = generate_token("task1", salt=SALT)
        assert verify_token(agent_id, token + "x", salt=SALT) is None

    def test_empty_token_fails(self):
        assert verify_token("agent", "", salt=SALT) is None

    def test_salt_is_required(self):
        agent_id, token = generate_token("task1", salt=SALT)
        with pytest.raises(TypeError):
            verify_token(agent_id, token)  # type: ignore[call-arg]

    def test_empty_salt_rejected(self):
        with pytest.raises(ValueError, match="salt"):
            verify_token("agent", "token", salt="")

    def test_complex_task_info(self):
        """Verify tokens with slashes and special chars in task_info."""
        task_info = "kernel:abc123def456/63"
        agent_id, token = generate_token(task_info, salt=SALT)
        assert verify_token(agent_id, token, salt=SALT) == task_info
