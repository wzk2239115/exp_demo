"""Unit tests for cybergym.server.__main__ FastAPI application."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cybergym.server.types import DEFAULT_API_KEY, ServerHealthResponse, ServerInfo


@pytest.fixture
def mock_server_manager():
    """Mock ServerManager for testing."""
    manager = MagicMock()

    # Mock create_server
    manager.create_server.return_value = ServerInfo(
        agent_id="agent1",
        ip="172.17.0.2",
        port=8000,
        created_at=1234567890.0,
    )

    # Mock delete_server
    manager.delete_server.return_value = {
        "message": "Server deleted",
        "agent_id": "agent1",
    }

    # Mock restart_server
    manager.restart_server.return_value = ServerInfo(
        agent_id="agent1",
        ip="172.17.0.2",
        port=8000,
        created_at=1234567900.0,
    )

    # Mock health_check
    manager.health_check.return_value = ServerHealthResponse(
        agent_id="agent1",
        status="running",
        ip="172.17.0.2",
        port=8000,
        uptime_seconds=123.45,
    )

    # Mock async methods
    manager.start_cleanup_loop = AsyncMock()
    manager.stop_cleanup_loop = AsyncMock()

    return manager


@pytest.fixture
def test_client(mock_server_manager):
    """Create a test client with mocked dependencies."""
    # Patch ServerManager before importing the app
    with patch(
        "cybergym.server.__main__.ServerManager", return_value=mock_server_manager
    ):
        # Import app after patching
        # Manually set the server_manager global
        import cybergym.server.__main__ as main_module
        from cybergym.server.__main__ import app

        main_module.server_manager = mock_server_manager

        with TestClient(app) as client:
            yield client


class TestCreateServerEndpoint:
    """Tests for POST /create_server endpoint."""

    def test_create_server_success(self, test_client, mock_server_manager):
        """Test successful server creation."""
        response = test_client.post(
            "/create_server", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent1"
        assert data["ip"] == "172.17.0.2"
        assert data["port"] == 8000
        assert "created_at" in data

        # Verify manager was called
        mock_server_manager.create_server.assert_called_once()

    def test_create_server_invalid_request(self, test_client):
        """Test create_server with invalid request body."""
        response = test_client.post(
            "/create_server",
            json={"agent_id": "agent1"},  # Missing token
        )

        assert response.status_code == 422  # Validation error

    def test_create_server_unauthorized(self, test_client, mock_server_manager):
        """Test create_server with unauthorized token."""
        from fastapi import HTTPException

        mock_server_manager.create_server.side_effect = HTTPException(
            status_code=401, detail="Invalid token"
        )

        response = test_client.post(
            "/create_server", json={"agent_id": "agent1", "token": "invalid_token"}
        )

        assert response.status_code == 401


class TestDeleteServerEndpoint:
    """Tests for POST /delete_server endpoint."""

    def test_delete_server_success(self, test_client, mock_server_manager):
        """Test successful server deletion."""
        response = test_client.post(
            "/delete_server", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Server deleted"
        assert data["agent_id"] == "agent1"

        mock_server_manager.delete_server.assert_called_once()

    def test_delete_server_not_found(self, test_client, mock_server_manager):
        """Test deleting a non-existent server."""
        from fastapi import HTTPException

        mock_server_manager.delete_server.side_effect = HTTPException(
            status_code=404, detail="No server found for this agent/task pair"
        )

        response = test_client.post(
            "/delete_server", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 404

    def test_delete_server_invalid_request(self, test_client):
        """Test delete_server with invalid request body."""
        response = test_client.post(
            "/delete_server",
            json={},  # Missing required fields
        )

        assert response.status_code == 422


class TestRestartServerEndpoint:
    """Tests for POST /restart_server endpoint."""

    def test_restart_server_success(self, test_client, mock_server_manager):
        """Test successful server restart."""
        response = test_client.post(
            "/restart_server", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent1"
        assert data["ip"] == "172.17.0.2"
        assert data["port"] == 8000

        mock_server_manager.restart_server.assert_called_once()

    def test_restart_server_unauthorized(self, test_client, mock_server_manager):
        """Test restart_server with unauthorized token."""
        from fastapi import HTTPException

        mock_server_manager.restart_server.side_effect = HTTPException(
            status_code=401, detail="Invalid token"
        )

        response = test_client.post(
            "/restart_server", json={"agent_id": "agent1", "token": "invalid_token"}
        )

        assert response.status_code == 401


class TestHealthCheckEndpoint:
    """Tests for POST /health_check endpoint."""

    def test_health_check_running(self, test_client, mock_server_manager):
        """Test health check for a running server."""
        response = test_client.post(
            "/health_check", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent1"
        assert data["status"] == "running"
        assert data["ip"] == "172.17.0.2"
        assert data["port"] == 8000
        assert data["uptime_seconds"] == 123.45

        mock_server_manager.health_check.assert_called_once()

    def test_health_check_not_found(self, test_client, mock_server_manager):
        """Test health check for a non-existent server."""
        mock_server_manager.health_check.return_value = ServerHealthResponse(
            agent_id="agent1", status="not_found"
        )

        response = test_client.post(
            "/health_check", json={"agent_id": "agent1", "token": "valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_found"
        assert data["ip"] is None
        assert data["port"] is None


class TestAppConfiguration:
    """Tests for application configuration and lifecycle."""

    def test_app_title(self):
        """Test that app has correct title."""
        from cybergym.server.__main__ import app

        assert app.title == "CyberGym Server Manager"

    def test_lifespan_startup(self, mock_server_manager):
        """Test lifespan startup behavior."""
        # This is tested implicitly through the test_client fixture
        # which triggers the lifespan context
        with patch(
            "cybergym.server.__main__.ServerManager", return_value=mock_server_manager
        ):
            from cybergym.server.__main__ import app

            with TestClient(app):
                # During lifespan, start_cleanup_loop should be called
                pass

    @patch("cybergym.server.__main__.uvicorn")
    @patch("cybergym.server.__main__.argparse.ArgumentParser.parse_args")
    def test_main_default_args(self, mock_parse_args, mock_uvicorn, tmp_path):
        """main() should wire parsed args into uvicorn.run."""
        from cybergym.server.__main__ import app, main
        from cybergym.server.types import ServerConfig

        mock_args = MagicMock()
        mock_args.host = "127.0.0.1"
        mock_args.port = 8667
        mock_args.log_level = "INFO"
        mock_args.log_dir = tmp_path  # real dir so logging FileHandler can open
        mock_args.network = None
        mock_parse_args.return_value = mock_args

        # main() mutates the module-global server_config; use a throwaway copy
        # so it doesn't leak into other tests.
        with patch("cybergym.server.__main__.server_config", ServerConfig()):
            main()

        mock_uvicorn.run.assert_called_once_with(app, host="127.0.0.1", port=8667)

    def test_server_config_initialization(self):
        """Test ServerConfig initialization in main module."""
        from cybergym.server.__main__ import server_config

        assert server_config.host == "127.0.0.1"
        assert server_config.port == 8666
        assert isinstance(server_config.salt, str)
        assert isinstance(server_config.flag_seed, str)


class TestEndToEndFlow:
    """End-to-end integration tests."""

    def test_create_health_delete_flow(self, test_client, mock_server_manager):
        """Test complete workflow: create -> health check -> delete."""
        # Create server
        create_response = test_client.post(
            "/create_server", json={"agent_id": "agent1", "token": "valid_token"}
        )
        assert create_response.status_code == 200

        # Health check
        health_response = test_client.post(
            "/health_check", json={"agent_id": "agent1", "token": "valid_token"}
        )
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "running"

        # Delete server
        delete_response = test_client.post(
            "/delete_server", json={"agent_id": "agent1", "token": "valid_token"}
        )
        assert delete_response.status_code == 200

        # Verify all manager methods were called
        assert mock_server_manager.create_server.called
        assert mock_server_manager.health_check.called
        assert mock_server_manager.delete_server.called

    def test_restart_workflow(self, test_client, mock_server_manager):
        """Test restart workflow."""
        # Restart (which may or may not have an existing server)
        restart_response = test_client.post(
            "/restart_server", json={"agent_id": "agent1", "token": "valid_token"}
        )
        assert restart_response.status_code == 200

        # Health check after restart
        health_response = test_client.post(
            "/health_check", json={"agent_id": "agent1", "token": "valid_token"}
        )
        assert health_response.status_code == 200

        mock_server_manager.restart_server.assert_called_once()


class TestRunCommandEndpoint:
    """Tests for POST /run_command endpoint (private route)."""

    def test_run_command_without_api_key(self, test_client):
        """Test run_command without API key (should fail)."""
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls", "-la"],
            },
        )

        # Should return 404 (not authorized, endpoint hidden)
        assert response.status_code == 404

    def test_run_command_with_invalid_api_key(self, test_client):
        """Test run_command with invalid API key."""
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls", "-la"],
            },
            headers={"X-API-Key": "invalid-key"},
        )

        # Should return 404 (not authorized)
        assert response.status_code == 404

    def test_run_command_with_valid_api_key(self, test_client, mock_server_manager):
        """Test run_command with valid API key."""
        from cybergym.server.types import DEFAULT_API_KEY

        # Setup mock to return command result
        mock_server_manager.run_command.return_value = (0, "command output")

        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["echo", "hello"],
            },
            headers={"X-API-Key": DEFAULT_API_KEY},
        )

        assert response.status_code == 200
        # FastAPI returns tuple as array
        data = response.json()
        assert data == [0, "command output"]

        mock_server_manager.run_command.assert_called_once()

    def test_run_command_server_not_found(self, test_client, mock_server_manager):
        """Test run_command when server doesn't exist."""
        from fastapi import HTTPException

        from cybergym.server.types import DEFAULT_API_KEY

        mock_server_manager.run_command.side_effect = HTTPException(
            status_code=404, detail="No server found for this agent/task pair"
        )

        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls"],
            },
            headers={"X-API-Key": DEFAULT_API_KEY},
        )

        assert response.status_code == 404

    def test_run_command_invalid_request(self, test_client):
        """Test run_command with invalid request body."""
        from cybergym.server.types import DEFAULT_API_KEY

        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                # Missing 'command' field
            },
            headers={"X-API-Key": DEFAULT_API_KEY},
        )

        assert response.status_code == 422  # Validation error


class TestPublicPrivateRouting:
    """Tests for public vs private endpoint routing and authentication."""

    def test_public_endpoints_accessible_without_api_key(self, test_client):
        """Test that public endpoints are accessible without API key."""
        public_endpoints = [
            "/create_server",
            "/delete_server",
            "/restart_server",
            "/health_check",
        ]

        for endpoint in public_endpoints:
            response = test_client.post(
                endpoint,
                json={"agent_id": "agent1", "token": "valid_token"},
            )
            # Should not return 403/404 due to missing API key
            # May return 401 for invalid token, but that's a different auth layer
            assert response.status_code in [200, 401, 404, 422]

    def test_private_endpoint_requires_api_key(self, test_client):
        """Test that private endpoint requires API key."""
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls"],
            },
        )

        # Without API key, should return 404 (endpoint hidden)
        assert response.status_code == 404

    def test_api_key_header_name(self, test_client, mock_server_manager):
        """Test that API key must be in X-API-Key header."""

        # Setup mock to return proper tuple for run_command
        mock_server_manager.run_command.return_value = (0, "test output")

        # Try with wrong header name
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls"],
            },
            headers={"Authorization": f"Bearer {DEFAULT_API_KEY}"},
        )

        # Should fail - wrong header name
        assert response.status_code == 404

        # Try with correct header name
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls"],
            },
            headers={"X-API-Key": DEFAULT_API_KEY},
        )

        # Should succeed (or return error from manager, not auth)
        assert response.status_code in [200, 404]  # 404 if server not found

    def test_api_key_case_sensitive(self, test_client):
        """Test that API key is case sensitive."""
        from cybergym.server.types import DEFAULT_API_KEY

        # Try with wrong case
        response = test_client.post(
            "/run_command",
            json={
                "agent_id": "agent1",
                "token": "valid_token",
                "command": ["ls"],
            },
            headers={"X-API-Key": DEFAULT_API_KEY.upper()},
        )

        # Should fail if key is different case
        if DEFAULT_API_KEY != DEFAULT_API_KEY.upper():
            assert response.status_code == 404

    def test_router_inclusion(self):
        """Test that routers are properly included in app."""
        from cybergym.server.__main__ import app

        # Get all routes
        routes = [route.path for route in app.routes]

        # Verify public endpoints are registered
        assert "/create_server" in routes
        assert "/delete_server" in routes
        assert "/restart_server" in routes
        assert "/health_check" in routes

        # Verify private endpoint is registered
        assert "/run_command" in routes

    def test_public_router_no_dependencies(self):
        """Test that public router has no auth dependencies."""
        from cybergym.server.__main__ import public_router

        # Public router should have no dependencies
        assert len(public_router.dependencies) == 0

    def test_private_router_has_dependencies(self):
        """Test that private router has auth dependencies."""
        from cybergym.server.__main__ import private_router

        # Private router should have API key dependency
        assert len(private_router.dependencies) > 0
