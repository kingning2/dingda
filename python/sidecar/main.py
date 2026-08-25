"""DingDa AI sidecar entrypoint — 委托 runtime.serve。"""

from __future__ import annotations

import argparse

from crawlers.core.logging import configure_logging
from runtime.server import serve


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="DingDa Python sidecar")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
