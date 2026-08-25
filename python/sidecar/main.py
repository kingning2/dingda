"""DingDa AI sidecar 入口 — 优先 IPC 长连接，缺省回退 HTTP（本地开发）。

解析 ``--ipc`` / ``--port``，配置 JSON 日志后进入对应服务循环。"""

from __future__ import annotations

import argparse

from crawlers.core.logging import configure_logging
from runtime.ipc_server import serve_ipc
from runtime.server import serve


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="DingDa Python sidecar")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--ipc",
        metavar="PATH",
        default=None,
        help="IPC 端点（Windows Named Pipe 名或 Unix socket 路径）；由 Rust 传入",
    )
    parser.add_argument(
        "--shm",
        metavar="PATH",
        default=None,
        help=argparse.SUPPRESS,  # 遗留参数，忽略
    )
    args = parser.parse_args()

    if args.ipc:
        serve_ipc(args.ipc)
        return
    serve(args.port)


if __name__ == "__main__":
    main()
