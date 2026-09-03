"""命令行入口模块。"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from src.app import create_app
from src.core.config import Settings
from src.core.logging import configure_logging, error, uvicorn_log_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="DingDa v2 FastAPI backend")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )

    configure_logging(level=settings.log_level)
    app = create_app(settings)
    try:
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            reload=settings.reload,
            log_config=uvicorn_log_config(settings.log_level),
        )
    except KeyboardInterrupt:
        pass
    except Exception:
        error("backend failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
