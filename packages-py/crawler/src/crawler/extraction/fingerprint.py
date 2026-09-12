"""Scrapling 风格 DOM 指纹：save / relocate。

职责：
    按 platform+section+field 存节点指纹（tag、class 语义片段、文案特征）；
    选择器失效时在 dump 树里找相似度最高的节点并生成 ``[class*="…"]``。

设计说明：
    - 指纹存 JSON 文件（非 Scrapling SQLite），路径在用户数据目录旁
    - 仅借鉴 adaptive 思想，不依赖 scrapling 包
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.crawler.fingerprint")

_STORE: Path | None = None


def _store_path() -> Path:
    global _STORE
    if _STORE is not None:
        return _STORE
    root = Path.home() / ".dingda" / "v2" / "dom_fingerprints.json"
    root.parent.mkdir(parents=True, exist_ok=True)
    _STORE = root
    return root


def _load() -> dict[str, Any]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict[str, Any]) -> None:
    path = _store_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(platform: str, section: str, field: str) -> str:
    return f"{platform}|{section}|{field}"


def _class_frag(name: str) -> str:
    return re.sub(r"--[a-zA-Z0-9_-]{4,}$", "", name)[:36]


def fingerprint_from_node(node: dict[str, Any]) -> dict[str, Any]:
    """从 dump 节点收指纹。"""
    classes = node.get("classes") if isinstance(node.get("classes"), list) else []
    frags = [_class_frag(str(c)) for c in classes if str(c).strip()]
    return {
        "tag": str(node.get("tag") or ""),
        "frags": [f for f in frags if f],
        "text": str(node.get("text") or "")[:60],
    }


def save_fingerprint(
    platform: str,
    section: str,
    field: str,
    node: dict[str, Any],
) -> None:
    """保存字段指纹。"""
    data = _load()
    data[_key(platform, section, field)] = fingerprint_from_node(node)
    _save(data)
    logger.info("fingerprint saved platform=%s section=%s field=%s", platform, section, field)


def _score(fp: dict[str, Any], node: dict[str, Any]) -> int:
    score = 0
    if str(fp.get("tag") or "") == str(node.get("tag") or ""):
        score += 2
    frags = fp.get("frags") if isinstance(fp.get("frags"), list) else []
    classes = " ".join(str(c) for c in (node.get("classes") or []))
    for frag in frags:
        if frag and frag in classes:
            score += 3
    fp_text = str(fp.get("text") or "").strip()
    node_text = str(node.get("text") or "").strip()
    if fp_text and node_text and (fp_text in node_text or node_text in fp_text):
        score += 2
    return score


def _walk(node: dict[str, Any] | None, out: list[dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return
    out.append(node)
    kids = node.get("kids") if isinstance(node.get("kids"), list) else []
    for kid in kids:
        _walk(kid if isinstance(kid, dict) else None, out)


def nodes_from_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """展平 dump 树为节点列表。"""
    nodes: list[dict[str, Any]] = []
    trees = tree.get("trees") if isinstance(tree.get("trees"), list) else []
    for row in trees:
        if isinstance(row, dict):
            _walk(row.get("node") if isinstance(row.get("node"), dict) else None, nodes)
    return nodes


def selector_class_tokens(selector: str) -> list[str]:
    """从 CSS 选择器里取 class 语义片段。

    支持 ``[class*="price"]`` 与 ``.price--x`` 两种写法；取第一个非空片段。
    """
    tokens = [
        m.group(1) or m.group(2)
        for m in re.finditer(r'class\*=\s*["\']([^"\']+)["\']|\.([A-Za-z_][\w-]*)', selector or "")
    ]
    return [t for t in tokens if t]


def node_has_class(node: dict[str, Any], fragment: str) -> bool:
    """节点任一 class 名含 ``fragment``（大小写敏感）。"""
    for cls in node.get("classes") or []:
        if fragment and fragment in str(cls):
            return True
    return False


def best_node_for_selector(
    nodes: list[dict[str, Any]],
    selector: str,
) -> dict[str, Any] | None:
    """在节点里找 class 语义最贴近该选择器的节点（取最深命中）。"""
    tokens = selector_class_tokens(selector)
    if not tokens:
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for node in nodes:
        score = sum(1 for tok in tokens if node_has_class(node, tok))
        if score > best_score:
            best_score = score
            best = node
    return best


def relocate(
    platform: str,
    section: str,
    field: str,
    tree: dict[str, Any],
    *,
    min_score: int = 5,
) -> str | None:
    """在 dump 树中重定位字段，返回 ``[class*="frag"]`` 或 None。"""
    fp = _load().get(_key(platform, section, field))
    if not isinstance(fp, dict):
        return None
    nodes: list[dict[str, Any]] = []
    trees = tree.get("trees") if isinstance(tree.get("trees"), list) else []
    for row in trees:
        if isinstance(row, dict):
            _walk(row.get("node") if isinstance(row.get("node"), dict) else None, nodes)
    best: dict[str, Any] | None = None
    best_score = 0
    for node in nodes:
        sc = _score(fp, node)
        if sc > best_score:
            best_score = sc
            best = node
    if best is None or best_score < min_score:
        logger.info(
            "fingerprint miss platform=%s field=%s best=%s",
            platform,
            field,
            best_score,
        )
        return None
    classes = best.get("classes") if isinstance(best.get("classes"), list) else []
    frags = fp.get("frags") if isinstance(fp.get("frags"), list) else []
    for frag in frags:
        for cls in classes:
            if frag and frag in str(cls):
                sel = f'[class*="{frag}"]'
                logger.info(
                    "fingerprint hit platform=%s field=%s score=%s sel=%s",
                    platform,
                    field,
                    best_score,
                    sel,
                )
                return sel
    if classes:
        frag = _class_frag(str(classes[0]))
        if frag:
            return f'[class*="{frag}"]'
    return None


def relocate_section(
    platform: str,
    section: str,
    fields: list[str],
    tree: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any] | None:
    """尝试为多个字段重定位；至少命中一个则返回合并后的 selectors。"""
    out = dict(base)
    hits = 0
    for field in fields:
        sel = relocate(platform, section, field, tree)
        if sel:
            out[field] = sel
            hits += 1
    return out if hits else None
