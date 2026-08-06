"""Unit tests for cybergym.server.types module."""

from pathlib import Path

import pytest

from cybergym.server.types import (
    API_KEY_ENV_VAR,
    FLAG_SEED_ENV_VAR,
    SALT_ENV_VAR,
    ContainerResources,
    KernelContainerResources,
    ServerConfig,
    ServerHealthResponse,
    ServerInfo,
    ServerRequest,
)

SECRET_ENV_VARS = (SALT_ENV_VAR, FLAG_SEED_ENV_VAR, API_KEY_ENV_VAR)


@pytest.fixture
def no_secret_env(monkeypatch):
    """Run with the controller secrets absent from the environment."""
    for var in SECRET_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestServerConfig:
    """Tests for ServerConfig settings model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8666
        assert config.log_dir == Path("./logs")
        assert isinstance(config.salt, str)

    def test_secrets_generated_not_hardcoded(self, no_secret_env):
        """Salt, flag seed, and API key are minted per instance, never shipped."""
        first = ServerConfig()
        second = ServerConfig()
        for field in ("salt", "flag_seed", "api_key"):
            assert getattr(first, field)
            assert getattr(first, field) != getattr(second, field), (
                f"{field} is not freshly generated"
            )

    def test_secrets_from_env(self, monkeypatch, no_secret_env):
        """Exported values win over generation, so both ends can agree."""
        monkeypatch.setenv(SALT_ENV_VAR, "env_salt")
        monkeypatch.setenv(FLAG_SEED_ENV_VAR, "env_seed")
        monkeypatch.setenv(API_KEY_ENV_VAR, "env_key")
        config = ServerConfig()
        assert config.salt == "env_salt"
        assert config.flag_seed == "env_seed"
        assert config.api_key == "env_key"

    def test_secret_env_round_trip(self, no_secret_env):
        """secret_env() names the vars the harness must export."""
        config = ServerConfig()
        assert config.secret_env() == {
            SALT_ENV_VAR: config.salt,
            FLAG_SEED_ENV_VAR: config.flag_seed,
            API_KEY_ENV_VAR: config.api_key,
        }

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = ServerConfig(
            host="0.0.0.0",
            port=9000,
            flag_seed="custom_seed",
            log_dir=Path("/custom/logs"),
            salt="custom_salt",
        )
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.flag_seed == "custom_seed"
        assert config.log_dir == Path("/custom/logs")
        assert config.salt == "custom_salt"

    def test_env_prefix(self):
        """Test that environment variables with correct prefix are used."""
        # This test verifies the env_prefix setting
        assert ServerConfig.model_config["env_prefix"] == "CYBERGYM_SERVER_"

    def test_default_verification_resources(self):
        """Each task type ships a non-empty resource budget with mem/CPU/pids
        caps and swap disabled (memswap == mem). Value-agnostic so the budgets
        can be tuned without test churn."""
        config = ServerConfig()
        for budget in (
            config.kernel_resources.to_run_kwargs(),
            config.v8_resources.to_run_kwargs(),
            config.user_resources.to_run_kwargs(),
        ):
            assert budget["mem_limit"]
            assert budget["nano_cpus"]
            assert budget["pids_limit"]
            # memswap == mem disables swap so an over-budget container is killed
            # instead of swapping the host.
            assert budget["memswap_limit"] == budget["mem_limit"]

    def test_resource_env_override_preserves_other_fields(self, monkeypatch):
        """Overriding one nested field via env must not reset the sibling
        caps to None (the footgun the typed-subclass design prevents)."""
        monkeypatch.setenv("CYBERGYM_SERVER_KERNEL_RESOURCES__MEM_LIMIT", "99g")
        config = ServerConfig()
        cls_defaults = KernelContainerResources()
        assert config.kernel_resources.mem_limit == "99g"  # the override
        # All other fields keep their KernelContainerResources class defaults.
        for field in ("memswap_limit", "nano_cpus", "pids_limit", "shm_size"):
            assert getattr(config.kernel_resources, field) == getattr(
                cls_defaults, field
            ), f"{field} was reset by env override"


class TestContainerResources:
    """Tests for the ContainerResources budget model."""

    def test_to_run_kwargs_drops_none(self):
        """Only set fields are forwarded to containers.run(...)."""
        res = ContainerResources(mem_limit="1g", nano_cpus=2_000_000_000)
        assert res.to_run_kwargs() == {
            "mem_limit": "1g",
            "nano_cpus": 2_000_000_000,
        }

    def test_to_run_kwargs_empty_when_unset(self):
        """A fully-unset budget leaves Docker defaults (no kwargs)."""
        assert ContainerResources().to_run_kwargs() == {}


class TestServerRequest:
    """Tests for ServerRequest model."""

    def test_valid_request(self):
        """Test creating a valid server request."""
        req = ServerRequest(agent_id="agent123", token="abc123def456")
        assert req.agent_id == "agent123"
        assert req.token == "abc123def456"

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        req = ServerRequest(agent_id="agent123", token="token123")
        json_data = req.model_dump()
        assert json_data == {"agent_id": "agent123", "token": "token123"}

        # Deserialize
        req2 = ServerRequest.model_validate(json_data)
        assert req2.agent_id == "agent123"
        assert req2.token == "token123"

    def test_missing_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(Exception):  # pydantic ValidationError
            ServerRequest(agent_id="agent123")

        with pytest.raises(Exception):
            ServerRequest(token="token123")


class TestServerInfo:
    """Tests for ServerInfo model."""

    def test_valid_server_info(self):
        """Test creating valid server info."""
        info = ServerInfo(
            agent_id="agent123",
            ip="172.17.0.2",
            port=8000,
            created_at=1234567890.0,
        )
        assert info.agent_id == "agent123"
        assert info.ip == "172.17.0.2"
        assert info.port == 8000
        assert info.created_at == 1234567890.0

    def test_json_serialization(self):
        """Test JSON serialization."""
        info = ServerInfo(
            agent_id="agent1",
            ip="127.0.0.1",
            port=8000,
            created_at=1234567890.0,
        )
        json_data = info.model_dump()
        assert "agent_id" in json_data
        assert "ip" in json_data
        assert "port" in json_data
        assert "created_at" in json_data


class TestServerHealthResponse:
    """Tests for ServerHealthResponse model."""

    def test_running_status(self):
        """Test health response with running status."""
        health = ServerHealthResponse(
            agent_id="agent1",
            status="running",
            ip="172.17.0.2",
            port=8000,
            uptime_seconds=123.45,
        )
        assert health.agent_id == "agent1"
        assert health.status == "running"
        assert health.ip == "172.17.0.2"
        assert health.port == 8000
        assert health.uptime_seconds == 123.45

    def test_not_found_status(self):
        """Test health response with not_found status."""
        health = ServerHealthResponse(agent_id="agent1", status="not_found")
        assert health.status == "not_found"
        assert health.ip is None
        assert health.port is None
        assert health.uptime_seconds is None

    def test_optional_fields_none(self):
        """Test that optional fields can be None."""
        health = ServerHealthResponse(
            agent_id="agent1",
            status="not_found",
            ip=None,
            port=None,
            uptime_seconds=None,
        )
        assert health.ip is None
        assert health.port is None
        assert health.uptime_seconds is None
