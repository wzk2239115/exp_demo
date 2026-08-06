"""
Standalone server-lifecycle management service.

Endpoints:
    POST /create_server   - create (or return existing) task server
    POST /delete_server   - tear down a task server
    POST /restart_server  - delete + create in one call
    POST /health_check    - query server status

Run:
    python -m cybergym.server.server_app [--host HOST] [--port PORT] ...
"""

import argparse
import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Security,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from cybergym.server.controller import ServerManager
from cybergym.server.types import (
    API_KEY_NAME,
    RunCommandRequest,
    ServerConfig,
    ServerHealthResponse,
    ServerInfo,
    ServerRequest,
)

server_config = ServerConfig()
server_manager: ServerManager | None = None

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == server_config.api_key:
        return api_key
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def _get_server_manager() -> ServerManager:
    if server_manager is None:
        raise RuntimeError("Server manager is not initialized")
    return server_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global server_manager
    server_manager = ServerManager(
        salt=server_config.salt,
        flag_seed=server_config.flag_seed,
        network=server_config.network,
        resources_by_type={
            "kernel": server_config.kernel_resources,
            "v8": server_config.v8_resources,
            "user": server_config.user_resources,
        },
    )
    await server_manager.start_cleanup_loop()

    yield

    await server_manager.stop_cleanup_loop()


app = FastAPI(
    title="CyberGym Server Manager", lifespan=lifespan, docs_url=None, redoc_url=None
)
public_router = APIRouter()
private_router = APIRouter(dependencies=[Depends(get_api_key)])

logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# ── Endpoints ────────────────────────────────────────────────────────


@public_router.post("/create_server")
def create_server(req: ServerRequest) -> ServerInfo:
    return _get_server_manager().create_server(req)


@public_router.post("/delete_server")
def delete_server(req: ServerRequest) -> dict:
    return _get_server_manager().delete_server(req)


@public_router.post("/restart_server")
def restart_server(req: ServerRequest) -> ServerInfo:
    return _get_server_manager().restart_server(req)


@public_router.post("/health_check")
def health_check(req: ServerRequest) -> ServerHealthResponse:
    return _get_server_manager().health_check(req)


@private_router.post("/run_command", include_in_schema=False)
def run_command(req: RunCommandRequest) -> tuple[int, str]:
    return _get_server_manager().run_command(req)


# Include routers in the application
app.include_router(public_router)
app.include_router(private_router)


def main() -> None:
    parser = argparse.ArgumentParser(description="CyberGym Server Manager")
    parser.add_argument(
        "--host", type=str, default=server_config.host, help="Host to bind"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=server_config.port,
        help="Port to bind (default: 8666)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    parser.add_argument(
        "--log_dir",
        type=Path,
        default=server_config.log_dir,
        help="Directory to store logs",
    )
    parser.add_argument(
        "--network",
        type=str,
        default=server_config.network,
        help="Docker network name for task containers (e.g. cybergym-internal for proxy enforcement)",
    )

    args = parser.parse_args()
    server_config.host = args.host
    server_config.port = args.port
    server_config.log_dir = args.log_dir
    server_config.network = args.network

    # Configure logging
    server_config.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = server_config.log_dir / "server_manager.log"

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting CyberGym Server Manager on {server_config.host}:{args.port}")
    logger.info(f"Log level: {args.log_level}")

    # The token salt, flag seed, and API key are generated per process unless
    # they came in via the environment. The agent-side harness must use the same
    # values, so log them here — this is the only place they can be recovered
    # from (scripts/setup/pre_run.py parses these lines when it reuses a
    # controller it did not start).
    logger.info(
        "Controller secrets — export these for the agent runner:\n%s",
        "\n".join(f"  {k}={v}" for k, v in server_config.secret_env().items()),
    )

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = (
        "%(asctime)s - %(levelprefix)s %(message)s"
    )
    log_config["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    log_config["formatters"]["access"]["fmt"] = (
        '%(asctime)s - %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    log_config["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run(app, host=server_config.host, port=args.port)


if __name__ == "__main__":
    main()
