"""DingDa AI sidecar entrypoint — 优先共享内存，缺省回退 HTTP。"""

from __future__ import annotations

import argparse

from crawlers.core.logging import configure_logging
from runtime.server import serve
from runtime.shm_server import serve_shm


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="DingDa Python sidecar")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--shm",
        metavar="PATH",
        default=None,
        help="共享内存段文件路径；传入则启用共享内存 IPC（由 Rust 控制调用时机），否则回退 HTTP",
    )
    args = parser.parse_args()

    if args.shm:
        serve_shm(args.shm)
        return
    serve(args.port)


if __name__ == "__main__":
    main()
