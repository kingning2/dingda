"""扫码登录冒烟：启动真实 QR 会话，在终端/默认看图程序展示二维码。

用法（在 server 目录）：
    uv run python tooling/qr_smoke.py xianyu
    uv run python tooling/qr_smoke.py xiaohongshu
"""

from __future__ import annotations

import argparse
import sys


def _run_service(platform: str) -> None:
    from src.channels.qr_terminal import show_qr_in_terminal
    from src.contracts.channel import QrStartRequest
    from src.domains.channel.qr_service import get_channel_qr_service

    result = get_channel_qr_service().start(QrStartRequest(platform=platform))  # type: ignore[arg-type]
    if not result.qr_base64:
        raise SystemExit(f"No QR returned: status={result.status} detail={result.detail}")

    print(f"platform={platform}")
    print(f"session_id={result.session_id}")
    print(f"status={result.status}")
    print(f"qr_base64_len={len(result.qr_base64)}")
    show_qr_in_terminal(result.qr_base64, qr_url=result.qr_url)


def _run_http(platform: str, base_url: str) -> None:
    import httpx

    from src.channels.qr_terminal import show_qr_in_terminal

    with httpx.Client(base_url=base_url, timeout=120.0) as client:
        response = client.post("/v1/channel/qr/start", json={"platform": platform})
        response.raise_for_status()
        payload = response.json()

    qr_base64 = payload.get("qr_base64")
    if not qr_base64:
        raise SystemExit(f"HTTP missing qr_base64: {payload}")

    print(f"http_ok platform={platform}")
    print(f"session_id={payload.get('session_id')}")
    print(f"status={payload.get('status')}")
    show_qr_in_terminal(qr_base64, qr_url=payload.get("qr_url"))


def main() -> None:
    parser = argparse.ArgumentParser(description="QR login smoke test")
    parser.add_argument(
        "platform",
        choices=["xianyu", "xiaohongshu"],
        help="xianyu or xiaohongshu",
    )
    parser.add_argument(
        "--http",
        metavar="URL",
        help="Call running FastAPI, e.g. http://127.0.0.1:8787",
    )
    args = parser.parse_args()

    if args.http:
        _run_http(args.platform, args.http.rstrip("/"))
    else:
        _run_service(args.platform)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
