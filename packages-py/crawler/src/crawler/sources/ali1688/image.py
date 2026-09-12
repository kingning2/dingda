"""1688 以图搜图：本地图预处理。

职责：
    URL 透传；本地图校验、可选缩放并转 JPEG，产出 imgBase64 所需路径信息。

设计说明：
    - 仅被 ali1688 crawler / compare 使用
    - 依赖 Pillow（server 已声明）
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from core.errors import AppError

logger = logging.getLogger("dingda.crawler.ali1688.image")

_JPEG_EXT = {".jpg", ".jpeg"}
_MAX_SIZE_MB = 10.0
_MAX_DIM = (1600, 1600)


def preprocess_image(image_path: str) -> dict[str, Any]:
    """预处理图片：URL 或本地路径 → {type, url|path, converted?}。"""
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return {"type": "url", "url": image_path}
    return _process_local(image_path)


def _process_local(path: str) -> dict[str, Any]:
    """本地图：过大或非 JPEG 时转临时 JPEG。"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise AppError("crawler.ali1688_image", f"图片不存在：{path}", status_code=400)

    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > _MAX_SIZE_MB:
        raise AppError(
            "crawler.ali1688_image",
            f"图片太大 ({size_mb:.1f}MB)，最大支持 {_MAX_SIZE_MB}MB",
            status_code=400,
        )

    ext = Path(path).suffix.lower()
    needs_resize = False
    try:
        with Image.open(path) as img:
            if img.width > _MAX_DIM[0] or img.height > _MAX_DIM[1]:
                needs_resize = True
    except Exception:
        pass

    converted = False
    if needs_resize or ext not in _JPEG_EXT:
        path = _convert_to_jpeg(path, resize=needs_resize)
        converted = True
        logger.info("image preprocessed converted=%s path=%s", converted, path)

    return {
        "type": "local",
        "path": path,
        "converted": converted,
        "size_bytes": os.path.getsize(path),
    }


def _convert_to_jpeg(src_path: str, *, resize: bool, quality: int = 90) -> str:
    """转 JPEG 临时文件；失败抛 AppError。"""
    try:
        img = Image.open(src_path)
    except Exception as exc:
        raise AppError("crawler.ali1688_image", f"无法打开图片: {exc}", status_code=400) from exc

    if resize:
        img.thumbnail(_MAX_DIM, Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    except OSError:
        fallback = os.path.dirname(os.path.abspath(src_path))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=fallback)

    try:
        img.save(tmp, format="JPEG", quality=quality)
        tmp.close()
    except Exception as exc:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise AppError("crawler.ali1688_image", f"图片转换失败: {exc}", status_code=400) from exc

    return tmp.name
