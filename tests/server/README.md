# Server Module Tests

This directory contains comprehensive tests for the `cybergym.server` module.

## Test Structure

- **test_types.py** - Unit tests for data models and types
- **test_controller.py** - Unit tests for ServerManager with mocked Docker
- **test_main.py** - Unit tests for FastAPI endpoints with mocked dependencies
- **test_integration.py** - Integration tests using real Docker containers

## Running Tests

### Run all tests (unit only)
```bash
pytest tests/server/ -v -m "not integration"
```

### Run unit tests only
```bash
pytest tests/server/test_types.py tests/server/test_controller.py tests/server/test_main.py -v
```

### Run integration tests (requires Docker)
```bash
pytest tests/server/test_integration.py -v -m integration
```

### Run all tests including integration
```bash
pytest tests/server/ -v
```

## Integration Tests Requirements

Integration tests require:
1. **Docker daemon running** - Tests will be skipped if Docker is unavailable
2. **Task image available** - The image `cybergym/arvo:36476-vul.exp.none` should be pulled:
   ```bash
   docker pull cybergym/arvo:36476-vul.exp.none
   ```
3. **Network access** - Docker containers need network connectivity

## Test Coverage

### Unit Tests (Mocked)
- Configuration and settings validation
- Token authentication and verification
- Server lifecycle management (create, delete, restart, health check)
- Thread safety and concurrent operations
- Server expiry and cleanup loops
- FastAPI endpoint behavior
- Error handling and edge cases

### Integration Tests (Real Docker)
- End-to-end workflows with real containers
- Token generation and verification with real tasks
- Docker container creation and management
- Multiple agents with concurrent containers
- Server TTL and auto-expiration
- API endpoint integration with real backend
- Container property verification

## Example: Running Specific Tests

```bash
# Run just the token tests
pytest tests/server/test_integration.py::TestRealTaskIntegration::test_generate_and_verify_token -v

# Run the complete workflow test
pytest tests/server/test_integration.py::TestRealTaskIntegration::test_complete_workflow_with_real_task -v -m integration

# Run all API integration tests
pytest tests/server/test_integration.py::TestFastAPIIntegrationWithRealTask -v -m integration
```

## Debugging Failed Tests

If integration tests fail:

1. **Check Docker daemon**: `docker ps`
2. **Check image availability**: `docker images | grep arvo:36476`
3. **Check running containers**: `docker ps -a`
4. **Clean up stale containers**: `docker container prune -f`
5. **View test logs**: Add `-s` flag to pytest to see print statements

## CI/CD Considerations

In CI/CD pipelines:
- Unit tests should run on every commit
- Integration tests should run on pull requests or scheduled builds
- Use `-m "not integration"` to exclude integration tests from fast feedback loops
