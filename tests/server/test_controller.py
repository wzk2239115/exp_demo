"""Unit tests for cybergym.server.controller module."""

import asyncio
import socket
import time
from unittest.mock import MagicMock, Mock, call, patch

import docker.errors
import pytest
from fastapi import HTTPException

from cybergym.server.controller import (
    CLEANUP_INTERVAL,
    DEFAULT_SERVER_TTL,
    RATE_LIMIT_INTERVAL,
    ServerManager,
    _destroy_container,
    _health_check_container,
    _launch_container,
    _ServerRecord,
)
from cybergym.server.types import (
    RunCommandRequest,
    ServerHealthResponse,
    ServerInfo,
    ServerRequest,
)


@pytest.fixture
def mock_docker_client():
    """Mock docker client for testing.

    Both controller.py (destroy/health) and task_handler.py (launch) use
    docker.from_env(), so we patch both and wire them to the same mock client.
    """
    mock_container = MagicMock()
    mock_container.id = "container_123"
    mock_container.attrs = {
        "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.2"}}}
    }

    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container
    mock_client.containers.get.return_value = mock_container

    with (
        patch("cybergym.server.controller.get_docker_client", return_value=mock_client),
        patch(
            "cybergym.server.task_handler.get_docker_client", return_value=mock_client
        ),
        patch("cybergym.server.controller.docker") as mock_ctrl_docker,
        patch("cybergym.server.task_handler.docker") as mock_handler_docker,
        patch("cybergym.utils.subprocess") as mock_subprocess,
    ):
        # Production code now reads through get_docker_client (patched above);
        # the docker-module patches remain so `docker.errors.NotFound` and the
        # legacy `.from_env.return_value` lookup used by the existing test
        # bodies keep resolving to the same mock_client.
        for mock_docker in (mock_ctrl_docker, mock_handler_docker):
            mock_docker.errors = docker.errors
            mock_docker.from_env.return_value = mock_client

        yield mock_ctrl_docker


@pytest.fixture
def mock_verify_token():
    """Mock token verification."""
    with patch("cybergym.server.controller.verify_token") as mock_verify:
        mock_verify.return_value = "arvo_12345/asan/EXEC"
        yield mock_verify


@pytest.fixture
def mock_task_metadata():
    """Mock TASK_METADATA."""
    mock_meta = {
        "arvo_12345": MagicMock(
            binary="target_binary",
            images={"asan": "test-image:asan", "ubsan": "test-image:ubsan"},
            env={"ENV_VAR": "value"},
        )
    }
    with patch("cybergym.server.task_handler.TASK_METADATA", mock_meta):
        yield mock_meta


@pytest.fixture
def mock_health_check():
    """Mock health check to always return True."""
    with patch(
        "cybergym.server.controller._health_check_container", return_value=True
    ) as mock_check:
        yield mock_check


class TestLaunchContainer:
    """Tests for _launch_container function."""

    def test_launch_container_success(self, mock_docker_client, mock_task_metadata):
        """Test successful container launch."""
        ip, port, container_id = _launch_container("arvo_12345/asan/EXEC", "test_seed")

        assert ip == "172.17.0.2"
        assert port == 8000
        assert container_id == "container_123"

        # Verify container.run was called with correct parameters
        client = mock_docker_client.from_env.return_value
        assert client.containers.run.called

    def test_launch_container_with_flag_seed(
        self, mock_docker_client, mock_task_metadata
    ):
        """Test container launch — derived flag must NOT appear in command args."""
        from cybergym.task.token import generate_flag

        flag_seed = "custom_seed"
        task_info = "arvo_12345/asan/EXEC"
        ip, port, container_id = _launch_container(task_info, flag_seed)

        client = mock_docker_client.from_env.return_value
        call_args = client.containers.run.call_args

        # Derived flag should NOT be in the command (injected via docker_cp instead)
        derived_flag = generate_flag(task_info, seed=flag_seed)
        assert derived_flag not in call_args[1]["command"]


class TestDestroyContainer:
    """Tests for _destroy_container function."""

    def test_destroy_container_success(self, mock_docker_client):
        """Test successful container destruction."""
        record = _ServerRecord(
            task_info="arvo_12345/asan/EXEC",
            agent_id="agent1",
            ip="172.17.0.2",
            port=8000,
            created_at=time.time(),
            container_id="container_123",
        )

        _destroy_container(record)

        client = mock_docker_client.from_env.return_value
        client.containers.get.assert_called_once_with("container_123")
        client.containers.get.return_value.remove.assert_called_once()

    def test_destroy_container_not_found(self, mock_docker_client):
        """Test destroying a non-existent container."""

        client = mock_docker_client.from_env.return_value
        client.containers.get.side_effect = docker.errors.NotFound(
            "Container not found"
        )

        record = _ServerRecord(
            task_info="arvo_12345/asan/EXEC",
            agent_id="agent1",
            ip="172.17.0.2",
            port=8000,
            created_at=time.time(),
            container_id="nonexistent",
        )

        # Should not raise, just log warning
        _destroy_container(record)


class TestHealthCheckContainer:
    """Tests for _health_check_container function."""

    def test_health_check_returns_true_when_running(self):
        """Test that health check returns True when container is running and port is listening."""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = MagicMock(exit_code=0)

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with (
            patch(
                "cybergym.server.controller.get_docker_client",
                return_value=mock_client,
            ),
            patch("cybergym.server.controller.docker") as mock_docker,
        ):
            mock_docker.errors = docker.errors
            mock_docker.from_env.return_value = mock_client

            record = _ServerRecord(
                task_info="arvo_12345/asan/EXEC",
                agent_id="agent1",
                ip="172.17.0.2",
                port=8000,
                created_at=time.time(),
                container_id="container_123",
            )

            result = _health_check_container(record)
            assert result is True


class TestServerManager:
    """Tests for ServerManager class."""

    @pytest.fixture
    def server_manager(self):
        """Create a ServerManager instance for testing."""
        return ServerManager(salt="test_salt", flag_seed="test_seed", server_ttl=3600)

    def test_initialization(self, server_manager):
        """Test ServerManager initialization."""
        assert server_manager._salt == "test_salt"
        assert server_manager._flag_seed == "test_seed"
        assert server_manager._server_ttl == 3600
        assert server_manager._servers == {}
        assert server_manager._cleanup_task is None

    def test_verify_valid_token(
        self, server_manager, mock_verify_token, mock_task_metadata
    ):
        """Test token verification with valid token."""
        req = ServerRequest(agent_id="agent1", token="valid_token")
        task_info = server_manager._verify(req)

        assert task_info == "arvo_12345/asan/EXEC"
        mock_verify_token.assert_called_once_with(
            "agent1", "valid_token", salt="test_salt"
        )

    def test_verify_invalid_token(self, server_manager, mock_verify_token):
        """Test token verification with invalid token."""
        mock_verify_token.return_value = None

        req = ServerRequest(agent_id="agent1", token="invalid_token")

        with pytest.raises(HTTPException) as exc_info:
            server_manager._verify(req)

        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_verify_unknown_task_id(self, server_manager, mock_verify_token):
        """Test verification with unknown task_id."""
        mock_verify_token.return_value = "unknown_task/asan/EXEC"

        with patch("cybergym.server.task_handler.TASK_METADATA", {}):
            req = ServerRequest(agent_id="agent1", token="valid_token")

            with pytest.raises(HTTPException) as exc_info:
                server_manager._verify(req)

            assert exc_info.value.status_code == 400

    def test_create_server_new(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test creating a new server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        info = server_manager.create_server(req)

        assert isinstance(info, ServerInfo)
        assert info.agent_id == "agent1"
        assert info.ip == "172.17.0.2"
        assert info.port == 8000
        assert isinstance(info.created_at, float)

    def test_create_server_idempotent(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that create_server is idempotent."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # Create server first time
        info1 = server_manager.create_server(req)

        # Create server second time (should return existing)
        info2 = server_manager.create_server(req)

        assert info1.ip == info2.ip
        assert info1.port == info2.port
        assert info1.created_at == info2.created_at

        # Docker container should only be launched once
        client = mock_docker_client.from_env.return_value
        assert client.containers.run.call_count == 1

    def test_delete_server_existing(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test deleting an existing server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # Create server first
        server_manager.create_server(req)

        # Delete server
        result = server_manager.delete_server(req)

        assert result["message"] == "Server deleted"
        assert result["agent_id"] == "agent1"

        # Verify server is removed from registry
        assert len(server_manager._servers) == 0

    def test_delete_server_not_found(
        self, server_manager, mock_verify_token, mock_task_metadata
    ):
        """Test deleting a non-existent server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        with pytest.raises(HTTPException) as exc_info:
            server_manager.delete_server(req)

        assert exc_info.value.status_code == 404
        assert "No server found" in exc_info.value.detail

    def test_restart_server_new(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test restarting a server that doesn't exist."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        info = server_manager.restart_server(req)

        assert isinstance(info, ServerInfo)
        assert info.agent_id == "agent1"

    def test_restart_server_existing(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test restarting an existing server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # Create server first
        info1 = server_manager.create_server(req)
        created_at_1 = info1.created_at

        # Mock time to simulate waiting beyond rate limit
        with patch("cybergym.server.controller.time.time") as mock_time:
            # Set time to be after rate limit interval
            mock_time.return_value = created_at_1 + RATE_LIMIT_INTERVAL + 1

            # Restart server
            info2 = server_manager.restart_server(req)

            # Times should be different
            assert info2.created_at > info1.created_at

        # Container should be destroyed and recreated
        client = mock_docker_client.from_env.return_value
        assert client.containers.run.call_count == 2

    def test_health_check_running(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test health check for a running server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # Create server
        server_manager.create_server(req)

        # Small delay to ensure uptime > 0
        time.sleep(0.01)

        # Health check
        health = server_manager.health_check(req)

        assert isinstance(health, ServerHealthResponse)
        assert health.agent_id == "agent1"
        assert health.status == "running"
        assert health.ip == "172.17.0.2"
        assert health.port == 8000
        assert health.uptime_seconds > 0

    def test_health_check_not_found(
        self, server_manager, mock_verify_token, mock_task_metadata
    ):
        """Test health check for a non-existent server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        health = server_manager.health_check(req)

        assert health.agent_id == "agent1"
        assert health.status == "not_found"
        assert health.ip is None
        assert health.port is None
        assert health.uptime_seconds is None

    def test_expire_servers_old(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that old servers are expired."""
        # Set very short TTL
        server_manager._server_ttl = 0.1

        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Wait for TTL to expire
        time.sleep(0.15)

        expired_count = server_manager._expire_servers()

        assert expired_count == 1
        assert len(server_manager._servers) == 0

    def test_expire_servers_young(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that young servers are not expired."""
        server_manager._server_ttl = 3600

        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        expired_count = server_manager._expire_servers()

        assert expired_count == 0
        assert len(server_manager._servers) == 1

    @pytest.mark.asyncio
    async def test_cleanup_loop_lifecycle(self, server_manager):
        """Test starting and stopping the cleanup loop."""
        # Start cleanup loop
        await server_manager.start_cleanup_loop()
        assert server_manager._cleanup_task is not None
        assert not server_manager._cleanup_task.done()

        # Short delay
        await asyncio.sleep(0.1)

        # Stop cleanup loop
        await server_manager.stop_cleanup_loop()
        assert (
            server_manager._cleanup_task.cancelled()
            or server_manager._cleanup_task.done()
        )

    @pytest.mark.asyncio
    async def test_stop_cleanup_destroys_remaining_servers(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that stopping cleanup loop destroys remaining servers."""
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        assert len(server_manager._servers) == 1

        # Start and immediately stop cleanup (simulating shutdown)
        await server_manager.start_cleanup_loop()
        await server_manager.stop_cleanup_loop()

        # All servers should be destroyed
        assert len(server_manager._servers) == 0

        # Container should be removed
        client = mock_docker_client.from_env.return_value
        assert client.containers.get.return_value.remove.called

    def test_thread_safety_concurrent_creates(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test thread safety with concurrent create operations."""
        import threading

        req = ServerRequest(agent_id="agent1", token="valid_token")
        results = []

        def create():
            info = server_manager.create_server(req)
            results.append(info)

        threads = [threading.Thread(target=create) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All creates should return the same server (idempotent)
        assert len(results) == 5
        ips = {r.ip for r in results}
        ports = {r.port for r in results}
        assert len(ips) == 1  # All same IP
        assert len(ports) == 1  # All same port

    def test_concurrent_same_key_launches_once(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_health_check,
    ):
        """Concurrent creates for the same key launch exactly one container;
        the rest attach to the in-flight creation."""
        import threading
        import time as _time

        launches: list[str] = []
        launch_lock = threading.Lock()

        def slow_launch(task_info, flag_seed, *, network=None, resources_by_type=None):
            with launch_lock:
                launches.append(task_info)
            _time.sleep(0.2)  # hold so the other callers pile up as waiters
            return ("172.17.0.2", 8000, "cid")

        req = ServerRequest(agent_id="agent1", token="valid_token")
        results: list[ServerInfo] = []

        def go():
            results.append(server_manager.create_server(req))

        with patch(
            "cybergym.server.controller._launch_container", side_effect=slow_launch
        ):
            threads = [threading.Thread(target=go) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(launches) == 1  # only one real launch
        assert len(results) == 5
        assert len({(r.ip, r.port) for r in results}) == 1  # all the same server

    def test_concurrent_different_keys_not_serialized(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_health_check,
    ):
        """Creations for different keys run concurrently — they are not
        serialized behind one global lock during the (slow) launch.

        Regression guard: under a single lock held across the launch, the
        second creation could not reach the barrier while the first is
        mid-launch, so the barrier would time out and raise.
        """
        import threading

        barrier = threading.Barrier(2, timeout=5)

        def launch(task_info, flag_seed, *, network=None, resources_by_type=None):
            barrier.wait()  # only passes if both launches run concurrently
            return ("172.17.0.2", 8000, "cid")

        errors: list[Exception] = []

        def go(agent_id: str):
            try:
                # Same task_info (mock), different agent_id => different key.
                server_manager.create_server(
                    ServerRequest(agent_id=agent_id, token="valid_token")
                )
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        with patch("cybergym.server.controller._launch_container", side_effect=launch):
            threads = [
                threading.Thread(target=go, args=(a,)) for a in ("agentA", "agentB")
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, f"creations were serialized: {errors}"

    def test_restart_waits_for_in_flight_create(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_health_check,
    ):
        """A restart racing an in-flight create for the same key must wait for
        the create to publish, then tear that container down — never launch a
        second one concurrently and orphan it."""
        import threading
        import time as _time

        launches: list[str] = []
        destroyed: list[str] = []
        launch_lock = threading.Lock()
        create_launch_started = threading.Event()
        release_create_launch = threading.Event()

        def launch(task_info, flag_seed, *, network=None, resources_by_type=None):
            with launch_lock:
                n = len(launches) + 1
                launches.append(f"cid{n}")
            if n == 1:  # the create's launch — hold it open
                create_launch_started.set()
                assert release_create_launch.wait(timeout=5)
            return ("172.17.0.2", 8000, f"cid{n}")

        def destroy(rec):
            destroyed.append(rec.container_id)

        req = ServerRequest(agent_id="agent1", token="valid_token")

        with (
            patch("cybergym.server.controller._launch_container", side_effect=launch),
            patch("cybergym.server.controller._destroy_container", side_effect=destroy),
            # Drop the rate-limit gate so the restart actually proceeds to relaunch.
            patch("cybergym.server.controller.RATE_LIMIT_INTERVAL", 0),
        ):
            create_result: list[ServerInfo] = []
            create_thread = threading.Thread(
                target=lambda: create_result.append(server_manager.create_server(req))
            )
            create_thread.start()
            assert create_launch_started.wait(timeout=5)

            # Restart while the create is still mid-launch (key is in _pending).
            restart_result: list[ServerInfo] = []
            restart_thread = threading.Thread(
                target=lambda: restart_result.append(server_manager.restart_server(req))
            )
            restart_thread.start()

            # The restart must block in _wait_for_pending, not launch yet.
            _time.sleep(0.2)
            assert launches == ["cid1"], "restart launched concurrently with create"

            # Let the create finish; restart should then proceed.
            release_create_launch.set()
            create_thread.join(timeout=5)
            restart_thread.join(timeout=5)

        # Exactly two launches, serialized: create's cid1 then restart's cid2.
        assert launches == ["cid1", "cid2"]
        # The create's container was torn down by the restart — no orphan.
        assert destroyed == ["cid1"]
        # The registry holds only the restart's fresh server.
        assert (
            server_manager._servers[("agent1", "arvo_12345/asan/EXEC")].container_id
            == "cid2"
        )
        assert restart_result[0].port == 8000

    def test_multiple_agents_different_servers(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that different agents get different servers."""
        req1 = ServerRequest(agent_id="agent1", token="token1")
        req2 = ServerRequest(agent_id="agent2", token="token2")

        info1 = server_manager.create_server(req1)
        info2 = server_manager.create_server(req2)

        # Two separate servers should exist
        assert len(server_manager._servers) == 2
        assert info1.agent_id != info2.agent_id


class TestRunCommand:
    """Tests for run_command endpoint."""

    @pytest.fixture
    def server_manager(self):
        """Create a ServerManager instance for testing."""
        return ServerManager(salt="test_salt", flag_seed="test_seed", server_ttl=3600)

    def test_run_command_success(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test running a command successfully."""
        # Create server first
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Setup mock for exec_run
        client = mock_docker_client.from_env.return_value
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = b"command output"
        client.containers.get.return_value.exec_run.reset_mock()
        client.containers.get.return_value.exec_run.return_value = mock_result

        # Run command
        cmd_req = RunCommandRequest(
            agent_id="agent1", token="valid_token", command=["ls", "-la"]
        )
        exit_code, output = server_manager.run_command(cmd_req)

        assert exit_code == 0
        assert output == "command output"
        client.containers.get.return_value.exec_run.assert_called_once_with(
            ["ls", "-la"]
        )

    def test_run_command_server_not_found(
        self, server_manager, mock_verify_token, mock_task_metadata
    ):
        """Test running command on non-existent server."""
        cmd_req = RunCommandRequest(
            agent_id="agent1", token="valid_token", command=["echo", "hello"]
        )

        with pytest.raises(HTTPException) as exc_info:
            server_manager.run_command(cmd_req)

        assert exc_info.value.status_code == 404
        assert "No server found" in exc_info.value.detail

    def test_run_command_container_not_found(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test running command when container doesn't exist."""
        # Create server first
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Setup mock to raise NotFound
        client = mock_docker_client.from_env.return_value
        client.containers.get.side_effect = docker.errors.NotFound(
            "Container not found"
        )

        cmd_req = RunCommandRequest(
            agent_id="agent1", token="valid_token", command=["ls"]
        )

        with pytest.raises(HTTPException) as exc_info:
            server_manager.run_command(cmd_req)

        assert exc_info.value.status_code == 404
        assert "Container not found" in exc_info.value.detail

    def test_run_command_with_exit_code(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test running command that returns non-zero exit code."""
        # Create server first
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Setup mock for exec_run with non-zero exit
        client = mock_docker_client.from_env.return_value
        mock_result = MagicMock()
        mock_result.exit_code = 1
        mock_result.output = b"error message"
        client.containers.get.return_value.exec_run.return_value = mock_result

        # Run command
        cmd_req = RunCommandRequest(
            agent_id="agent1", token="valid_token", command=["false"]
        )
        exit_code, output = server_manager.run_command(cmd_req)

        assert exit_code == 1
        assert output == "error message"

    def test_run_command_with_special_characters(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test running command with special characters in output."""
        # Create server first
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Setup mock with special characters
        client = mock_docker_client.from_env.return_value
        mock_result = MagicMock()
        mock_result.exit_code = 0
        mock_result.output = "output with émojis 🚀 and spëcial chars".encode("utf-8")
        client.containers.get.return_value.exec_run.return_value = mock_result

        # Run command
        cmd_req = RunCommandRequest(
            agent_id="agent1", token="valid_token", command=["echo", "test"]
        )
        exit_code, output = server_manager.run_command(cmd_req)

        assert exit_code == 0
        assert "émojis" in output or "mojis" in output  # handles encoding


class TestHealthCheckEnhanced:
    """Enhanced tests for health_check functionality."""

    @pytest.fixture
    def server_manager(self):
        """Create a ServerManager instance for testing."""
        return ServerManager(salt="test_salt", flag_seed="test_seed", server_ttl=3600)

    def test_health_check_unhealthy_server(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test health check for an unhealthy server."""
        # Create server
        req = ServerRequest(agent_id="agent1", token="valid_token")
        server_manager.create_server(req)

        # Mock health check to return False
        with patch(
            "cybergym.server.controller._health_check_container", return_value=False
        ):
            health = server_manager.health_check(req)

            assert health.agent_id == "agent1"
            assert health.status == "unhealthy"
            assert health.ip == "172.17.0.2"
            assert health.port == 8000
            assert health.uptime_seconds is None

    def test_health_check_container_running_port_listening(self):
        """Test _health_check_container with running container and listening port."""
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = MagicMock(exit_code=0)

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with (
            patch(
                "cybergym.server.controller.get_docker_client",
                return_value=mock_client,
            ),
            patch("cybergym.server.controller.docker") as mock_docker,
        ):
            mock_docker.errors = docker.errors
            mock_docker.from_env.return_value = mock_client

            record = _ServerRecord(
                task_info="arvo_12345/asan/EXEC",
                agent_id="agent1",
                ip="172.17.0.2",
                port=8000,
                created_at=time.time(),
                container_id="container_123",
            )

            result = _health_check_container(record)
            assert result is True

    def test_health_check_container_not_running(self):
        """Test _health_check_container with stopped container."""
        mock_container = MagicMock()
        mock_container.status = "exited"

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with (
            patch(
                "cybergym.server.controller.get_docker_client",
                return_value=mock_client,
            ),
            patch("cybergym.server.controller.docker") as mock_docker,
        ):
            mock_docker.errors = docker.errors
            mock_docker.from_env.return_value = mock_client

            record = _ServerRecord(
                task_info="arvo_12345/asan/EXEC",
                agent_id="agent1",
                ip="172.17.0.2",
                port=8000,
                created_at=time.time(),
                container_id="container_123",
            )

            result = _health_check_container(record)
            assert result is False

    def test_health_check_container_not_found(self):
        """Test _health_check_container when container doesn't exist."""
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = docker.errors.NotFound("gone")

        with (
            patch(
                "cybergym.server.controller.get_docker_client",
                return_value=mock_client,
            ),
            patch("cybergym.server.controller.docker") as mock_docker,
        ):
            mock_docker.errors = docker.errors
            mock_docker.from_env.return_value = mock_client

            record = _ServerRecord(
                task_info="arvo_12345/asan/EXEC",
                agent_id="agent1",
                ip="172.17.0.2",
                port=8000,
                created_at=time.time(),
                container_id="container_123",
            )

            result = _health_check_container(record)
            assert result is False


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.fixture
    def server_manager(self):
        """Create a ServerManager instance for testing."""
        return ServerManager(salt="test_salt", flag_seed="test_seed", server_ttl=3600)

    def test_rate_limit_on_create_server(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test rate limiting on create_server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # First create should succeed
        info1 = server_manager.create_server(req)
        assert info1 is not None

        # Delete the server
        server_manager.delete_server(req)

        # Immediate create should fail due to rate limit
        with pytest.raises(HTTPException) as exc_info:
            server_manager.create_server(req)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert "seconds before launching again" in exc_info.value.detail

    def test_rate_limit_on_restart_server(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test rate limiting on restart_server."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # First restart should succeed (creates new server)
        info1 = server_manager.restart_server(req)
        assert info1 is not None

        # Immediate second restart should fail due to rate limit
        with pytest.raises(HTTPException) as exc_info:
            server_manager.restart_server(req)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    def test_rate_limit_allows_after_interval(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that requests are allowed after rate limit interval."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # First create
        server_manager.create_server(req)

        # Delete
        server_manager.delete_server(req)

        # Mock time to simulate waiting beyond rate limit
        original_time = time.time()
        with patch("cybergym.server.controller.time.time") as mock_time:
            # Set time to be after rate limit interval
            mock_time.return_value = original_time + RATE_LIMIT_INTERVAL + 1

            # Should succeed now
            info = server_manager.create_server(req)
            assert info is not None

    def test_rate_limit_per_key_isolation(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that rate limiting is per-key (different agents not affected)."""
        req1 = ServerRequest(agent_id="agent1", token="token1")
        req2 = ServerRequest(agent_id="agent2", token="token2")

        # Create server for agent1
        server_manager.create_server(req1)

        # Delete it
        server_manager.delete_server(req1)

        # agent1 should be rate limited
        with pytest.raises(HTTPException) as exc_info:
            server_manager.create_server(req1)
        assert exc_info.value.status_code == 429

        # agent2 should NOT be rate limited
        info2 = server_manager.create_server(req2)
        assert info2 is not None
        assert info2.agent_id == "agent2"

    def test_rate_limit_check_method(self, server_manager):
        """Test _check_rate_limit method directly."""
        key = ("agent1", "arvo_12345/asan/EXEC")

        # No previous launch - should not raise
        server_manager._check_rate_limit(key)

        # Set last launch to now
        now = time.time()
        server_manager._last_launch[key] = now

        # Immediate check should raise
        with pytest.raises(HTTPException) as exc_info:
            server_manager._check_rate_limit(key)
        assert exc_info.value.status_code == 429

        # Check after interval should not raise
        server_manager._last_launch[key] = now - RATE_LIMIT_INTERVAL - 1
        server_manager._check_rate_limit(key)  # Should not raise

    def test_rate_limit_remaining_time_accuracy(
        self,
        server_manager,
        mock_verify_token,
        mock_task_metadata,
        mock_docker_client,
        mock_health_check,
    ):
        """Test that remaining time in rate limit message is accurate."""
        req = ServerRequest(agent_id="agent1", token="valid_token")

        # Create and delete
        server_manager.create_server(req)
        server_manager.delete_server(req)

        # Try to create again immediately
        try:
            server_manager.create_server(req)
        except HTTPException as e:
            # Extract remaining time from error message
            assert "Rate limit exceeded" in e.detail
            # Should mention seconds
            assert "second" in e.detail.lower()
            # Remaining time should be close to RATE_LIMIT_INTERVAL
            import re

            match = re.search(r"(\d+\.?\d*)\s*seconds?", e.detail)
            if match:
                remaining = float(match.group(1))
                # Should be close to the full interval (allowing small timing variance)
                assert 0 < remaining <= RATE_LIMIT_INTERVAL
