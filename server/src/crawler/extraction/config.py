"""抽取配置加载与点分路径取值。

职责：
    读取平台旁的 extract.json；按 ``a.b.c`` 路径从 dict 取值；
    支持缓存、热加载与小节原子写回，供 DOM 自动修复写盘。

设计说明：
    - 路径列表按顺序试，命中第一个非空值
    - ``.`` / 空串表示当前对象本身
    - 写回后 ``reload`` 使进程内缓存立即生效
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.crawler.extraction")

_CACHE: dict[str, dict[str, Any]] = {}


def extract_json_path(beside: str | Path) -> Path:
    """与 ``beside``（通常 ``__file__``）同目录的 ``extract.json`` 路径。"""
    return Path(beside).resolve().parent / "extract.json"


def load_extract_json(beside: str | Path, *, force: bool = False) -> dict[str, Any]:
    """加载 extract.json；默认按绝对路径缓存。"""
    path = extract_json_path(beside)
    key = str(path)
    if not force and key in _CACHE:
        return _CACHE[key]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"extract.json 根须为 object: {path}")
    _CACHE[key] = data
    logger.info("extract config loaded path=%s version=%s force=%s", path, data.get("version"), force)
    return data


def reload_extract_json(beside: str | Path) -> dict[str, Any]:
    """强制从磁盘重读并刷新缓存。"""
    return load_extract_json(beside, force=True)


def write_extract_section(
    beside: str | Path,
    section_name: str,
    section_data: dict[str, Any],
) -> dict[str, Any]:
    """原子合并写回某一小节，并刷新缓存。

    小节内按 key 合并：补丁只覆盖它带的键，其余（root / img_attrs / 正则等）
    原样保留；再刷新缓存供热加载。
    """
    path = extract_json_path(beside)
    current = load_extract_json(beside, force=True)
    merged = dict(current)
    existing = current.get(section_name)
    section_merged = dict(existing) if isinstance(existing, dict) else {}
    section_merged.update(section_data)
    merged[section_name] = section_merged
    text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix="extract-",
        suffix=".json",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    logger.info(
        "extract section written path=%s section=%s keys=%s",
        path,
        section_name,
        sorted(section_data.keys())[:20],
    )
    return reload_extract_json(beside)


def section(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    """取配置小节；缺失则为空 dict。"""
    value = cfg.get(name)
    return value if isinstance(value, dict) else {}


def path_list(section_cfg: dict[str, Any], key: str) -> list[str]:
    """取路径列表配置。"""
    raw = section_cfg.get(key)
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x).strip()]


def dig(obj: Any, path: str) -> Any:
    """点分路径取值；``path`` 为 ``.`` 或空则返回 ``obj`` 本身。

    数字段按 list 下标取（如 ``info_list.0.url``）。
    """
    text = (path or "").strip()
    if text in ("", "."):
        return obj
    cur: Any = obj
    for part in text.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        if isinstance(cur, list) and part.isdigit():
            index = int(part)
            cur = cur[index] if 0 <= index < len(cur) else None
            continue
        return None
    return cur


def dig_first(obj: Any, paths: list[str] | tuple[str, ...] | None) -> Any:
    """按路径列表依次尝试，返回第一个非 ``None`` / 非空串的值。"""
    if not paths:
        return None
    for path in paths:
        value = dig(obj, str(path))
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def dig_str(obj: Any, paths: list[str] | tuple[str, ...] | None) -> str:
    """``dig_first`` 后转 strip 字符串；没有则 ``""``。"""
    value = dig_first(obj, paths)
    if value is None:
        return ""
    return str(value).strip()
