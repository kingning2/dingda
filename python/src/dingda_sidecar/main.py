"""Sidecar 入口 — 产品路径仅 pipe；可选 hybrid 留给大文件。

产品：``--ipc``（业务 ``sidecar.invoke`` + Event）
预留：``--shm`` + ``--ipc``（hybrid SHM，非默认）
调试：仅 ``--port`` HTTP
"""

from __future__ import annotations

import argparse
import logging
import sys

from dingda_sidecar.crawlers.core.logging import configure_logging

logger = logging.getLogger("dingda.sidecar")


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="DingDa Python sidecar")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="仅本地手工调试 HTTP；产品启动器不传此参数",
    )
    parser.add_argument(
        "--ipc",
        metavar="PATH",
        default=None,
        help="IPC 端点（Windows Named Pipe 名或 Unix socket 路径）",
    )
    parser.add_argument(
        "--shm",
        metavar="PATH",
        default=None,
        help="共享内存段路径（预留大文件；产品默认不传）",
    )
    args = parser.parse_args()

    if args.shm and args.ipc:
        from dingda_sidecar.runtime.hybrid_server import serve_hybrid

        logger.warning(
            "hybrid SHM+IPC 为预留路径，产品默认仅 --ipc",
            extra={"event": "sidecar.hybrid.legacy", "feature": "runtime"},
        )
        serve_hybrid(args.shm, args.ipc)
        return

    if args.ipc and not args.shm:
        from dingda_sidecar.runtime.ipc_server import serve_ipc

        serve_ipc(args.ipc)
        return

    if args.port is not None and not args.shm and not args.ipc:
        from dingda_sidecar.runtime.server import serve

        logger.warning(
            "仅 --port 启动 HTTP 调试服务；产品通讯请使用 --ipc",
            extra={"event": "sidecar.http.debug", "feature": "runtime"},
        )
        serve(args.port)
        return

    logger.error(
        "产品入口要求 --ipc（收到 shm=%s ipc=%s port=%s）",
        args.shm,
        args.ipc,
        args.port,
        extra={"event": "sidecar.bad_args", "feature": "runtime"},
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
