"""可选：手动预取 OCR 依赖与模型（不参与启动 / prepare:server）。

职责：
    确认 rapidocr-onnxruntime 可导入、ONNX 模型在包内、引擎可初始化。
    启动与构建默认不跑；需要时手动执行。

使用示例：
    uv run python scripts/prefetch_ocr.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """预加载 RapidOCR；失败以非 0 退出。"""
    print("[prefetch_ocr] importing rapidocr_onnxruntime…")
    try:
        import rapidocr_onnxruntime as rapidocr_pkg
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        print(f"[prefetch_ocr] FAIL: {exc}", file=sys.stderr)
        print("[prefetch_ocr] 请先在 server/ 执行: uv sync --frozen", file=sys.stderr)
        return 1

    root = Path(rapidocr_pkg.__file__).resolve().parent
    models = list((root / "models").glob("*.onnx")) if (root / "models").is_dir() else []
    print(f"[prefetch_ocr] package={root}")
    print(f"[prefetch_ocr] onnx_models={len(models)}")
    for path in models:
        print(f"[prefetch_ocr]   - {path.name} ({path.stat().st_size} bytes)")
    if len(models) < 3:
        print("[prefetch_ocr] FAIL: 缺少 ONNX 模型（wheel 应自带 det/rec/cls）", file=sys.stderr)
        return 1

    print("[prefetch_ocr] initializing RapidOCR engine…")
    engine = RapidOCR()
    # 1x1 白图走通推理路径，触发任意懒加载
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (64, 32), color=(255, 255, 255)).save(buf, format="JPEG")
    result, _ = engine(buf.getvalue())
    print(f"[prefetch_ocr] smoke_ok result_rows={0 if not result else len(result)}")
    print("[prefetch_ocr] ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
