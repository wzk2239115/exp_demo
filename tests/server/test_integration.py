"""Integration tests for cybergym.server module using real task arvo:36476/exp.none.

These tests use real Docker containers and should be run with:
    pytest -v -m integration tests/server/test_integration.py

To skip integration tests:
    pytest -v -m "not integration"
"""

import asyncio
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import docker
from cybergym.server.controller import ServerManager
from cybergym.server.types import DEFAULT_API_KEY, ServerRequest
from cybergym.task.token import generate_token, verify_token

# Mark for integration tests
pytestmark = pytest.mark.integration

# Token salt shared by every ServerManager and token in this module; the
# manager verifies tokens with this salt, so generation must use it too.
SALT = "CyberGymExploit2026"


@pytest.fixture(scope="module")
def check_docker_available():
    """Check if Docker is available, skip tests if not."""
    # get_docker_client() is @lru_cache'd; mock-based unit tests can leave a
    # fake client cached. Drop it so these tests bind a real Docker client.
    from cybergym.utils import get_docker_client

    get_docker_client.cache_clear()
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception as e:
        pytest.skip(f"Docker is not available: {e}")


@pytest.fixture(scope="module")
def shared_server_manager(check_docker_available):
    """Create a shared ServerManager instance for all tests in the module."""
    manager = ServerManager(
        salt=SALT, flag_seed="integration_test_seed", server_ttl=3600
    )
    yield manager
    # Cleanup all servers when done
    try:
        for key in list(manager._servers.keys()):
            agent_id, task_info = key
            try:
                req = ServerRequest(
                    agent_id=agent_id, token=generate_token(task_info, salt=SALT)[1]
                )
                manager.delete_server(req)
            except:
                pass
    except:
        pass


@pytest.fixture(scope="module")
def shared_real_server(shared_server_manager, check_docker_available):
    """Create a shared server instance that can be reused across tests."""
    task_info = "user:cybergym/arvo_36476/exp.none/EXEC"
    agent_id, token = generate_token(task_info, salt=SALT)
    req = ServerRequest(agent_id=agent_id, token=token)

    # Create server
    info = shared_server_manager.create_server(req)

    # Yield the info along with agent details
    yield {
        "manager": shared_server_manager,
        "agent_id": agent_id,
        "token": token,
        "task_info": task_info,
        "server_info": info,
        "request": req,
    }

    # Cleanup
    try:
        shared_server_manager.delete_server(req)
    except:
        pass


@pytest.fixture
def docker_cleanup():
    """Cleanup Docker containers after tests."""
    containers_to_cleanup = []

    yield containers_to_cleanup

    # Cleanup
    try:
        client = docker.from_env()
        for container_id in containers_to_cleanup:
            try:
                container = client.containers.get(container_id)
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
    except Exception:
        pass


@pytest.fixture
def real_task_info():
    """Real task info for arvo:36476/exp.none."""
    return "user:cybergym/arvo_36476/exp.none/EXEC"


@pytest.fixture
def real_agent_and_token(real_task_info):
    """Generate real agent_id and token for arvo:36476/exp.none."""
    agent_id, token = generate_token(real_task_info, salt=SALT)
    return agent_id, token


class TestRealTaskIntegration:
    """Integration tests using real task arvo:36476/exp.none with real Docker."""

    def test_generate_and_verify_token(self, real_task_info):
        """Test generating and verifying a real token for the arvo task."""
        agent_id, token = generate_token(real_task_info, salt=SALT)

        # Verify token
        verified_task_info = verify_token(agent_id, token, salt=SALT)
        assert verified_task_info == real_task_info
        assert verified_task_info == "user:cybergym/arvo_36476/exp.none/EXEC"

    def test_token_verification_with_wrong_agent_id(
        self, real_agent_and_token, real_task_info
    ):
        """Test that token verification fails with wrong agent_id."""
        agent_id, token = real_agent_and_token

        # Verify with wrong agent_id
        wrong_agent_id = "wrong_agent_id"
        verified_task_info = verify_token(wrong_agent_id, token, salt=SALT)
        assert verified_task_info is None

    def test_server_exists_and_running(self, shared_real_server):
        """Test that the shared server is created and running."""
        server_data = shared_real_server

        assert server_data["server_info"].agent_id == server_data["agent_id"]
        assert server_data["server_info"].ip is not None
        assert server_data["server_info"].port == 8000
        assert isinstance(server_data["server_info"].created_at, float)

        # Verify container exists
        client = docker.from_env()
        container_id = (
            server_data["manager"]
            ._servers[(server_data["agent_id"], server_data["task_info"])]
            .container_id
        )
        container = client.containers.get(container_id)
        assert container.status == "running"

    def test_health_check_with_shared_server(self, shared_real_server):
        """Test health check on shared server."""
        server_data = shared_real_server
        manager = server_data["manager"]
        req = server_data["request"]

        health = manager.health_check(req)
        assert health.status == "running"
        assert health.ip == server_data["server_info"].ip
        assert health.port == 8000
        assert health.uptime_seconds >= 0

    def test_idempotent_create_with_shared_server(self, shared_real_server):
        """Test that create_server is idempotent using shared server."""
        server_data = shared_real_server
        manager = server_data["manager"]
        req = server_data["request"]
        original_info = server_data["server_info"]

        # Create again - should return same server
        create_info = manager.create_server(req)
        assert create_info.ip == original_info.ip
        assert create_info.port == original_info.port
        assert create_info.created_at == original_info.created_at

    def test_complete_workflow_with_real_task(
        self,
        shared_server_manager,
        docker_cleanup,
        real_agent_and_token,
        real_task_info,
    ):
        """Test complete workflow: create -> health -> restart -> delete."""
        agent_id, token = real_agent_and_token
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # Step 1: Create server
            create_info = shared_server_manager.create_server(req)
            container_id = shared_server_manager._servers[
                (agent_id, real_task_info)
            ].container_id
            docker_cleanup.append(container_id)
            created_at_1 = create_info.created_at

            # Step 2: Health check (should be running)
            health = shared_server_manager.health_check(req)
            assert health.status == "running"
            assert health.ip == create_info.ip
            assert health.port == 8000
            assert health.uptime_seconds >= 0

            # Step 3: Create again (idempotent - should return same server)
            time.sleep(0.1)  # Small delay
            create_info_2 = shared_server_manager.create_server(req)
            assert create_info_2.ip == create_info.ip
            assert create_info_2.port == create_info.port
            assert create_info_2.created_at == created_at_1  # Same creation time

            # Step 4: Delete server
            result = shared_server_manager.delete_server(req)
            assert result["message"] == "Server deleted"

            # Step 5: Health check after delete (should not be found)
            health_after = shared_server_manager.health_check(req)
            assert health_after.status == "not_found"
            assert health_after.ip is None
            assert health_after.port is None
        finally:
            # Ensure cleanup
            try:
                shared_server_manager.delete_server(req)
            except:
                pass

    def test_multiple_agents_same_task(
        self, shared_server_manager, docker_cleanup, real_task_info
    ):
        """Test multiple agents accessing the same task type."""
        # Generate tokens for two different agents
        agent_id_1, token_1 = generate_token(real_task_info, salt=SALT)
        agent_id_2, token_2 = generate_token(real_task_info, salt=SALT)

        req_1 = ServerRequest(agent_id=agent_id_1, token=token_1)
        req_2 = ServerRequest(agent_id=agent_id_2, token=token_2)

        try:
            # Create servers for both agents using shared manager
            info_1 = shared_server_manager.create_server(req_1)
            docker_cleanup.append(info_1.ip)
            info_2 = shared_server_manager.create_server(req_2)
            docker_cleanup.append(info_2.ip)

            # Both should have their own servers (plus potentially the shared one)
            assert info_1.agent_id == agent_id_1
            assert info_2.agent_id == agent_id_2
            assert len(shared_server_manager._servers) >= 2

            # Health check for both
            health_1 = shared_server_manager.health_check(req_1)
            health_2 = shared_server_manager.health_check(req_2)

            assert health_1.status == "running"
            assert health_2.status == "running"
            assert health_1.agent_id == agent_id_1
            assert health_2.agent_id == agent_id_2
        finally:
            # Cleanup both servers
            try:
                shared_server_manager.delete_server(req_1)
            except:
                pass
            try:
                shared_server_manager.delete_server(req_2)
            except:
                pass

    def test_server_expiry_with_real_task(
        self, check_docker_available, docker_cleanup, real_agent_and_token
    ):
        """Test server auto-expiry with real task."""
        agent_id, token = real_agent_and_token

        # Set very short TTL
        server_manager = ServerManager(
            salt=SALT,
            flag_seed="expiry_test_seed",
            server_ttl=0.5,  # 500ms
        )

        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # Create server
            info = server_manager.create_server(req)
            docker_cleanup.append(info.ip)
            assert len(server_manager._servers) == 1

            # Wait for expiry
            time.sleep(0.8)

            # Expire servers
            expired_count = server_manager._expire_servers()
            assert expired_count == 1
            assert len(server_manager._servers) == 0
        finally:
            try:
                server_manager.delete_server(req)
            except:
                pass

    @pytest.mark.asyncio
    async def test_cleanup_loop_integration(
        self, check_docker_available, docker_cleanup, real_agent_and_token
    ):
        """Test cleanup loop with real task."""
        agent_id, token = real_agent_and_token

        server_manager = ServerManager(
            salt=SALT, flag_seed="cleanup_test_seed", server_ttl=3600
        )

        req = ServerRequest(agent_id=agent_id, token=token)

        # Start cleanup loop
        await server_manager.start_cleanup_loop()

        try:
            # Create server
            info = server_manager.create_server(req)
            docker_cleanup.append(info.ip)
            assert len(server_manager._servers) == 1

            # Let cleanup loop run for a bit
            await asyncio.sleep(0.2)

            # Server should still exist (TTL not expired)
            assert len(server_manager._servers) == 1
        finally:
            # Stop cleanup loop (should destroy all servers)
            await server_manager.stop_cleanup_loop()

            # All servers should be destroyed
            assert len(server_manager._servers) == 0

    def test_docker_container_properties(
        self,
        check_docker_available,
        docker_cleanup,
        real_agent_and_token,
        real_task_info,
    ):
        """Test that Docker container has correct properties."""
        agent_id, token = real_agent_and_token

        server_manager = ServerManager(
            salt=SALT, flag_seed="container_test_seed"
        )
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # Create server
            info = server_manager.create_server(req)
            container_id = server_manager._servers[
                (agent_id, real_task_info)
            ].container_id
            print(f"Created container {container_id} for agent {agent_id}")

            docker_cleanup.append(container_id)

            # Get container details
            client = docker.from_env()
            container = client.containers.get(container_id)
            nets = container.attrs["NetworkSettings"]["Networks"]
            assert nets, f"No network found for container {container_id}"
            ip = list(nets.values())[0]["IPAddress"]
            assert ip == info.ip

            # Verify image
            assert "cybergym/arvo:36476-vul.exp.none" in container.image.tags[0]

            # Verify container is running
            assert container.status == "running"
        finally:
            server_manager.delete_server(req)


class TestFastAPIIntegrationWithRealTask:
    """Integration tests for FastAPI endpoints with real task and real Docker."""

    @pytest.fixture
    def test_app_client(self, check_docker_available, real_agent_and_token):
        """Create test client with real task setup."""
        agent_id, token = real_agent_and_token

        # Create real server manager instance
        real_manager = ServerManager(
            salt=SALT, flag_seed="api_integration_test_seed"
        )

        # Import app
        import cybergym.server.__main__ as main_module
        from cybergym.server.__main__ import app

        main_module.server_manager = real_manager
        # TestClient triggers the app lifespan, which rebuilds server_manager
        # using server_config.salt — align it so SALT-minted tokens verify.
        main_module.server_config.salt = SALT

        with TestClient(app) as client:
            yield client, agent_id, token, real_manager

    def test_full_api_workflow_with_real_task(self, test_app_client, docker_cleanup):
        """Test full API workflow with arvo:36476/exp.none."""
        client, agent_id, token, manager = test_app_client

        try:
            # Create server
            create_response = client.post(
                "/create_server", json={"agent_id": agent_id, "token": token}
            )
            assert create_response.status_code == 200
            create_data = create_response.json()
            docker_cleanup.append(create_data["ip"])
            assert create_data["agent_id"] == agent_id

            # Health check
            health_response = client.post(
                "/health_check", json={"agent_id": agent_id, "token": token}
            )
            assert health_response.status_code == 200
            health_data = health_response.json()
            assert health_data["status"] == "running"

            # Delete
            delete_response = client.post(
                "/delete_server", json={"agent_id": agent_id, "token": token}
            )
            assert delete_response.status_code == 200
            assert delete_response.json()["message"] == "Server deleted"

            # Health check after delete
            health_after = client.post(
                "/health_check", json={"agent_id": agent_id, "token": token}
            )
            assert health_after.status_code == 200
            assert health_after.json()["status"] == "not_found"
        finally:
            # Ensure cleanup
            try:
                req = ServerRequest(agent_id=agent_id, token=token)
                manager.delete_server(req)
            except:
                pass

    def test_api_with_invalid_token_for_real_task(self, test_app_client):
        """Test API with invalid token."""
        client, agent_id, token, manager = test_app_client

        # Try to create server with wrong agent_id
        response = client.post(
            "/create_server", json={"agent_id": "wrong_agent", "token": token}
        )
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_api_idempotent_create_with_real_task(
        self, test_app_client, docker_cleanup
    ):
        """Test that create is idempotent for real task."""
        client, agent_id, token, manager = test_app_client

        try:
            # Create server first time
            response1 = client.post(
                "/create_server", json={"agent_id": agent_id, "token": token}
            )
            data1 = response1.json()
            docker_cleanup.append(data1["ip"])

            # Create server second time
            response2 = client.post(
                "/create_server", json={"agent_id": agent_id, "token": token}
            )
            data2 = response2.json()

            # Should return same server
            assert data1["ip"] == data2["ip"]
            assert data1["port"] == data2["port"]
            assert data1["created_at"] == data2["created_at"]
        finally:
            try:
                req = ServerRequest(agent_id=agent_id, token=token)
                manager.delete_server(req)
            except:
                pass


class TestRealTaskMetadata:
    """Tests for verifying real task metadata."""

    def test_arvo_36476_metadata_exists(self):
        """Test that arvo_36476 metadata exists and is correct."""
        from cybergym.task.metadata import TASK_METADATA

        assert "user:cybergym/arvo_36476" in TASK_METADATA
        task_meta = TASK_METADATA["user:cybergym/arvo_36476"]

        assert task_meta.binary == "fuzz"
        assert task_meta.project_name == "libtpms"
        assert task_meta.entry_name == "cybergym/arvo_36476"
        assert task_meta.task_id.startswith("user:")
        assert "exp.none" in task_meta.images
        assert task_meta.images["exp.none"] == "cybergym/arvo:36476-vul.exp.none-nogit"

    def test_task_info_format(self, real_task_info):
        """Test that task_info follows the user-task
        '<task_id>/<image_mode>/<target>' format."""
        # task_id itself contains a '/', so peel from the right like the handler.
        head, _, target = real_task_info.rpartition("/")
        task_id, _, image_type = head.rpartition("/")

        assert task_id == "user:cybergym/arvo_36476"
        assert image_type == "exp.none"
        assert target == "EXEC"

        # Verify in metadata
        from cybergym.task.metadata import TASK_METADATA

        assert task_id in TASK_METADATA
        assert image_type in TASK_METADATA[task_id].images


class TestRunCommandIntegration:
    """Integration tests for run_command endpoint with real Docker containers."""

    def test_run_command_basic(
        self,
        shared_real_server,
    ):
        """Test running a basic command in a real container."""
        server_data = shared_real_server
        agent_id = server_data["agent_id"]
        token = server_data["token"]
        manager = server_data["manager"]

        # Wait for container to be fully ready
        time.sleep(0.5)

        # Run command
        from cybergym.server.types import RunCommandRequest

        cmd_req = RunCommandRequest(
            agent_id=agent_id, token=token, command=["echo", "hello"]
        )
        exit_code, output = manager.run_command(cmd_req)

        assert exit_code == 0
        assert "hello" in output

    def test_run_command_ls(
        self,
        shared_real_server,
    ):
        """Test running ls command in real container."""
        server_data = shared_real_server
        agent_id = server_data["agent_id"]
        token = server_data["token"]
        manager = server_data["manager"]

        time.sleep(0.5)

        # Run ls command
        from cybergym.server.types import RunCommandRequest

        cmd_req = RunCommandRequest(
            agent_id=agent_id, token=token, command=["ls", "/out"]
        )
        exit_code, output = manager.run_command(cmd_req)

        assert exit_code == 0
        # Should list files in /out directory, including the binary
        assert "fuzz" in output or len(output) > 0

    def test_run_command_nonzero_exit(
        self,
        shared_real_server,
    ):
        """Test running command that returns non-zero exit code."""
        server_data = shared_real_server
        agent_id = server_data["agent_id"]
        token = server_data["token"]
        manager = server_data["manager"]

        time.sleep(0.5)

        # Run command that fails
        from cybergym.server.types import RunCommandRequest

        cmd_req = RunCommandRequest(
            agent_id=agent_id, token=token, command=["ls", "/nonexistent"]
        )
        exit_code, output = manager.run_command(cmd_req)

        # ls on nonexistent directory should fail
        assert exit_code != 0

    def test_run_command_server_not_found(
        self, check_docker_available, real_agent_and_token
    ):
        """Test running command when no server exists."""
        agent_id, token = real_agent_and_token

        server_manager = ServerManager(
            salt=SALT, flag_seed="no_server_test_seed"
        )

        from cybergym.server.types import RunCommandRequest

        cmd_req = RunCommandRequest(
            agent_id=agent_id, token=token, command=["echo", "test"]
        )

        with pytest.raises(HTTPException) as exc_info:
            server_manager.run_command(cmd_req)

        assert exc_info.value.status_code == 404
        assert "No server found" in exc_info.value.detail

    def test_run_command_via_api(self, check_docker_available, docker_cleanup):
        """Test run_command via FastAPI endpoint with real container."""

        agent_id, token = generate_token("user:cybergym/arvo_36476/exp.none/EXEC", salt=SALT)

        # Create real server manager
        real_manager = ServerManager(
            salt=SALT, flag_seed="api_run_cmd_seed"
        )

        # Import app
        import cybergym.server.__main__ as main_module
        from cybergym.server.__main__ import app

        main_module.server_manager = real_manager
        # TestClient triggers the app lifespan, which rebuilds server_manager
        # using server_config.salt — align it so SALT-minted tokens verify.
        main_module.server_config.salt = SALT

        with TestClient(app) as client:
            try:
                # Create server
                create_response = client.post(
                    "/create_server", json={"agent_id": agent_id, "token": token}
                )
                assert create_response.status_code == 200
                docker_cleanup.append(create_response.json()["ip"])
                time.sleep(1)

                # Run command with API key
                cmd_response = client.post(
                    "/run_command",
                    json={
                        "agent_id": agent_id,
                        "token": token,
                        "command": ["echo", "api_test"],
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )

                assert cmd_response.status_code == 200
                exit_code, output = cmd_response.json()
                assert exit_code == 0
                assert "api_test" in output

                # Try without API key (should fail)
                cmd_response_no_key = client.post(
                    "/run_command",
                    json={
                        "agent_id": agent_id,
                        "token": token,
                        "command": ["echo", "test"],
                    },
                )
                assert cmd_response_no_key.status_code == 404
            finally:
                try:
                    req = ServerRequest(agent_id=agent_id, token=token)
                    real_manager.delete_server(req)
                except:
                    pass


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with real containers."""

    def test_rate_limit_on_create(
        self,
        check_docker_available,
        docker_cleanup,
        real_agent_and_token,
        real_task_info,
    ):
        """Test rate limiting when creating servers rapidly."""
        agent_id, token = real_agent_and_token

        server_manager = ServerManager(
            salt=SALT, flag_seed="rate_limit_test_seed"
        )
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # First create should succeed
            info1 = server_manager.create_server(req)
            docker_cleanup.append(info1.ip)
            assert info1 is not None

            # Delete the server
            server_manager.delete_server(req)

            # Immediate create should fail due to rate limit
            with pytest.raises(HTTPException) as exc_info:
                server_manager.create_server(req)

            assert exc_info.value.status_code == 429
            assert "Rate limit exceeded" in exc_info.value.detail
        finally:
            try:
                server_manager.delete_server(req)
            except:
                pass

    def test_rate_limit_on_restart(
        self,
        check_docker_available,
        docker_cleanup,
        real_agent_and_token,
        real_task_info,
    ):
        """Test rate limiting when restarting servers rapidly."""
        agent_id, token = real_agent_and_token

        server_manager = ServerManager(
            salt=SALT, flag_seed="restart_rate_limit_seed"
        )
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # First restart should succeed
            info1 = server_manager.restart_server(req)
            docker_cleanup.append(info1.ip)
            assert info1 is not None

            # Immediate second restart should fail
            with pytest.raises(HTTPException) as exc_info:
                server_manager.restart_server(req)

            assert exc_info.value.status_code == 429
        finally:
            try:
                server_manager.delete_server(req)
            except:
                pass

    def test_rate_limit_per_agent(
        self, shared_server_manager, docker_cleanup, real_task_info
    ):
        """Test that rate limiting is per-agent (agents are independent)."""

        agent_id_1, token_1 = generate_token(real_task_info, salt=SALT)
        agent_id_2, token_2 = generate_token(real_task_info, salt=SALT)

        req_1 = ServerRequest(agent_id=agent_id_1, token=token_1)
        req_2 = ServerRequest(agent_id=agent_id_2, token=token_2)

        try:
            # Agent 1 creates and deletes
            info_1 = shared_server_manager.create_server(req_1)
            docker_cleanup.append(info_1.ip)
            shared_server_manager.delete_server(req_1)

            # Agent 1 should be rate limited
            with pytest.raises(HTTPException) as exc_info:
                shared_server_manager.create_server(req_1)
            assert exc_info.value.status_code == 429

            # Agent 2 should NOT be rate limited
            info_2 = shared_server_manager.create_server(req_2)
            docker_cleanup.append(info_2.ip)
            assert info_2 is not None
            assert info_2.agent_id == agent_id_2
        finally:
            try:
                shared_server_manager.delete_server(req_2)
            except:
                pass

    def test_rate_limit_via_api(self, check_docker_available, docker_cleanup):
        """Test rate limiting through API endpoints."""
        from cybergym.task.token import generate_token

        agent_id, token = generate_token("user:cybergym/arvo_36476/exp.none/EXEC", salt=SALT)

        # Create real server manager
        real_manager = ServerManager(
            salt=SALT, flag_seed="api_rate_limit_seed"
        )

        # Import app
        import cybergym.server.__main__ as main_module
        from cybergym.server.__main__ import app

        main_module.server_manager = real_manager
        # TestClient triggers the app lifespan, which rebuilds server_manager
        # using server_config.salt — align it so SALT-minted tokens verify.
        main_module.server_config.salt = SALT

        with TestClient(app) as client:
            try:
                # First create
                response1 = client.post(
                    "/create_server", json={"agent_id": agent_id, "token": token}
                )
                assert response1.status_code == 200
                docker_cleanup.append(response1.json()["ip"])

                # Delete
                delete_response = client.post(
                    "/delete_server", json={"agent_id": agent_id, "token": token}
                )
                assert delete_response.status_code == 200

                # Immediate create should fail with 429
                response2 = client.post(
                    "/create_server", json={"agent_id": agent_id, "token": token}
                )
                assert response2.status_code == 429
                assert "Rate limit" in response2.json()["detail"]
            finally:
                try:
                    req = ServerRequest(agent_id=agent_id, token=token)
                    real_manager.delete_server(req)
                except:
                    pass


class TestV8TaskIntegration:
    """Integration tests for V8 exploitation task handler with real Docker."""

    V8_TASK_INFO = "v8:7fd848c90a72"

    @pytest.fixture
    def v8_agent_and_token(self):
        """Generate real agent_id and token for a V8 task."""
        agent_id, token = generate_token(self.V8_TASK_INFO, salt=SALT)
        return agent_id, token

    @pytest.fixture
    def v8_server_manager(self, check_docker_available):
        """Create a ServerManager for V8 tests."""
        manager = ServerManager(
            salt=SALT, flag_seed="v8_integration_test_seed"
        )
        yield manager
        # Cleanup
        for key in list(manager._servers.keys()):
            agent_id, task_info = key
            try:
                req = ServerRequest(
                    agent_id=agent_id, token=generate_token(task_info, salt=SALT)[1]
                )
                manager.delete_server(req)
            except Exception:
                pass

    def test_v8_metadata_exists(self):
        """Test that V8 task metadata is loaded."""
        from cybergym.task.metadata import V8_TASK_METADATA

        assert "v8:clusterfuzz/323698305" in V8_TASK_METADATA
        task_meta = V8_TASK_METADATA["v8:clusterfuzz/323698305"]
        assert task_meta.image == "cybergym/v8:clusterfuzz-323698305-buildable"
        assert task_meta.entry_name == "clusterfuzz/323698305"

    def test_v8_create_server(
        self, v8_server_manager, v8_agent_and_token, docker_cleanup
    ):
        """Test creating a V8 challenge server."""
        agent_id, token = v8_agent_and_token
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            info = v8_server_manager.create_server(req)

            assert info.agent_id == agent_id
            assert info.ip is not None and info.ip != ""
            assert info.port == 1337

            # Verify container is running
            client = docker.from_env()
            record = v8_server_manager._servers[(agent_id, self.V8_TASK_INFO)]
            container = client.containers.get(record.container_id)
            docker_cleanup.append(record.container_id)
            assert container.status == "running"
        finally:
            try:
                v8_server_manager.delete_server(req)
            except Exception:
                pass

    def test_v8_health_check(
        self, v8_server_manager, v8_agent_and_token, docker_cleanup
    ):
        """Test health check on a V8 server."""
        agent_id, token = v8_agent_and_token
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            info = v8_server_manager.create_server(req)
            record = v8_server_manager._servers[(agent_id, self.V8_TASK_INFO)]
            docker_cleanup.append(record.container_id)

            health = v8_server_manager.health_check(req)
            assert health.status == "running"
            assert health.ip == info.ip
            assert health.port == 1337
        finally:
            try:
                v8_server_manager.delete_server(req)
            except Exception:
                pass

    def test_v8_send_js(self, v8_server_manager, v8_agent_and_token, docker_cleanup):
        """Test sending JavaScript to the V8 socat server."""
        import socket as sock_mod

        agent_id, token = v8_agent_and_token
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            info = v8_server_manager.create_server(req)
            record = v8_server_manager._servers[(agent_id, self.V8_TASK_INFO)]
            docker_cleanup.append(record.container_id)

            # Send JS and read response
            s = sock_mod.create_connection((info.ip, info.port), timeout=10)
            s.sendall(b'console.log("v8_integration_test")\n')
            s.shutdown(sock_mod.SHUT_WR)
            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
            s.close()

            assert b"v8_integration_test" in response
        finally:
            try:
                v8_server_manager.delete_server(req)
            except Exception:
                pass

    def test_v8_full_lifecycle(
        self, v8_server_manager, v8_agent_and_token, docker_cleanup
    ):
        """Test full V8 server lifecycle: create -> health -> delete."""
        agent_id, token = v8_agent_and_token
        req = ServerRequest(agent_id=agent_id, token=token)

        try:
            # Create
            info = v8_server_manager.create_server(req)
            record = v8_server_manager._servers[(agent_id, self.V8_TASK_INFO)]
            docker_cleanup.append(record.container_id)
            assert info.port == 1337

            # Health check
            health = v8_server_manager.health_check(req)
            assert health.status == "running"

            # Idempotent create
            info2 = v8_server_manager.create_server(req)
            assert info2.ip == info.ip
            assert info2.created_at == info.created_at

            # Delete
            result = v8_server_manager.delete_server(req)
            assert result["message"] == "Server deleted"

            # Health check after delete
            health_after = v8_server_manager.health_check(req)
            assert health_after.status == "not_found"
        finally:
            try:
                v8_server_manager.delete_server(req)
            except Exception:
                pass
