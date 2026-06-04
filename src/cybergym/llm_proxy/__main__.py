"""Run the API proxy with budget tracking.

Wraps litellm proxy with in-memory per-key budget enforcement.

Usage:
    # With Anthropic
    ANTHROPIC_API_KEY=sk-ant-... python -m cybergym.llm_proxy --port 4000

    # With a litellm config file (multi-provider)
    python -m cybergym.llm_proxy --port 4000 --config proxy_config.yaml

Example proxy_config.yaml:
    model_list:
      - model_name: claude-opus-4-6
        litellm_params:
          model: anthropic/claude-opus-4-6
          api_key: os.environ/ANTHROPIC_API_KEY
      - model_name: gpt-4o
        litellm_params:
          model: openai/gpt-4o
          api_key: os.environ/OPENAI_API_KEY
"""

import argparse
import logging

import uvicorn

from cybergym.llm_proxy.budget import BudgetManager
from cybergym.llm_proxy.server import get_proxy_app, setup_proxy


def main():
    parser = argparse.ArgumentParser(description="CyberGym API Proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=4000, help="Port to bind")
    parser.add_argument("--config", default=None, help="litellm proxy config YAML file")
    parser.add_argument(
        "--default-budget",
        type=float,
        default=20.0,
        help="Default max budget per key (USD)",
    )
    parser.add_argument(
        "--admin-key",
        default=None,
        help="Admin key for /budget endpoints (default: auto-generated, env: CYBERGYM_ADMIN_KEY)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
    )
    logging.getLogger("cybergym.llm_proxy").setLevel(args.log_level)

    # Suppress litellm's own verbose loggers to avoid duplicate output
    for name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # Use default config if none provided
    config_path = args.config
    if config_path is None:
        from pathlib import Path

        config_path = str(Path(__file__).parent / "default_config.yaml")

    import os

    admin_key = args.admin_key or os.environ.get("CYBERGYM_ADMIN_KEY")

    manager = BudgetManager(default_max_budget=args.default_budget)
    setup_proxy(manager, config_path=config_path, admin_key=admin_key)
    app = get_proxy_app()

    logging.getLogger(__name__).info(
        "Starting proxy on %s:%d (default budget: $%.2f)",
        args.host,
        args.port,
        args.default_budget,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
