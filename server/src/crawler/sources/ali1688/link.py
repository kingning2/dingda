"""1688/淘宝/天猫链接解析与主图抽取。

职责：
    解析商品 URL 或纯 ID；HTTP 拉详情页并用正则抽主图。
    仅抽图，不做搜品（搜品走 find_product API）。

设计说明：
    - 从 1688-product-find link_search 抽离的最小实现
"""

from __future__ import annotations

import gzip
import logging
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

from src.shared.errors import AppError

logger = logging.getLogger("dingda.crawler.ali1688.link")

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_URL_TEMPLATES = {
    "1688": "https://detail.1688.com/offer/{product_id}.html",
    "taobao": "https://item.taobao.com/item.htm?id={product_id}",
    "tmall": "https://detail.tmall.com/item.htm?id={product_id}",
}


def parse_product_ref(url_or_id: str) -> dict[str, str]:
    """解析链接或纯 ID → platform / product_id / canonical_url。"""
    text = url_or_id.strip()
    if "://" not in text and "." not in text:
        return _parse_pure_id(text)
    return _parse_url(text)


def extract_main_image(url: str, platform: str = "1688") -> str | None:
    """从商品页静默抽主图；失败返回 None。"""
    try:
        html = _fetch_page(url)
    except Exception:
        logger.warning("fetch product page failed url=%s", url)
        return None

    if platform == "1688":
        return _extract_1688(html)
    if platform in ("taobao", "tmall"):
        return _extract_taobao(html)
    return None


def resolve_image_from_link(url_or_id: str) -> tuple[str, str]:
    """解析链接并抽主图 → (image_url, canonical_url)。"""
    parsed = parse_product_ref(url_or_id)
    image = extract_main_image(parsed["canonical_url"], parsed["platform"])
    if not image:
        raise AppError(
            "crawler.ali1688_link_image",
            "无法自动获取商品主图，请改用 image 参数直接提供图片 URL",
            status_code=400,
        )
    logger.info("link image ok product_id=%s", parsed["product_id"])
    return image, parsed["canonical_url"]


def _parse_pure_id(product_id: str) -> dict[str, str]:
    if re.match(r"^\d{6,12}$", product_id):
        return {
            "platform": "1688",
            "product_id": product_id,
            "canonical_url": _URL_TEMPLATES["1688"].format(product_id=product_id),
        }
    if re.match(r"^[a-zA-Z0-9]{8,12}$", product_id):
        return {
            "platform": "taobao",
            "product_id": product_id,
            "canonical_url": _URL_TEMPLATES["taobao"].format(product_id=product_id),
        }
    raise AppError("crawler.ali1688_link", f"无法识别的商品 ID：{product_id}", status_code=400)


def _parse_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "1688.com" in host:
        match = re.search(r"/offer/(\d+)", parsed.path)
        if not match:
            raise AppError("crawler.ali1688_link", f"无效的 1688 链接：{url}", status_code=400)
        pid = match.group(1)
        return {
            "platform": "1688",
            "product_id": pid,
            "canonical_url": _URL_TEMPLATES["1688"].format(product_id=pid),
        }

    if "taobao.com" in host or "tb.cn" in host:
        qs = parse_qs(parsed.query)
        if "id" not in qs:
            raise AppError("crawler.ali1688_link", f"无效的淘宝链接：{url}", status_code=400)
        pid = qs["id"][0]
        return {
            "platform": "taobao",
            "product_id": pid,
            "canonical_url": _URL_TEMPLATES["taobao"].format(product_id=pid),
        }

    if "tmall.com" in host:
        qs = parse_qs(parsed.query)
        if "id" not in qs:
            raise AppError("crawler.ali1688_link", f"无效的天猫链接：{url}", status_code=400)
        pid = qs["id"][0]
        return {
            "platform": "tmall",
            "product_id": pid,
            "canonical_url": _URL_TEMPLATES["tmall"].format(product_id=pid),
        }

    raise AppError("crawler.ali1688_link", f"不支持的电商平台：{parsed.netloc}", status_code=400)


def _fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
        data = response.read()
        encoding = response.headers.get("Content-Encoding", "")
        if "gzip" in encoding:
            data = gzip.decompress(data)
        charset = "utf-8"
        content_type = response.headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        return data.decode(charset, errors="ignore")


def _normalize_image_url(img_url: str) -> str:
    if not img_url:
        return ""
    img_url = img_url.strip()
    if img_url.startswith("//"):
        img_url = "https:" + img_url
    if "alicdn.com" in img_url:
        img_url = re.sub(r"_\d+x\d+\.[a-zA-Z]+$", "", img_url)
        img_url = re.sub(r"_\.webp$", "", img_url)
        img_url = re.sub(r"\?.*$", "", img_url)
    return img_url


def _is_video_url(url: str) -> bool:
    lower = url.lower()
    return any(x in lower for x in (".mp4", ".mov", ".avi", ".webm", "video", "cloud.video"))


def _is_valid_product_image(img_url: str) -> bool:
    if not img_url:
        return False
    lower = img_url.lower()
    for keyword in (
        "icon",
        "logo",
        "sprite",
        "avatar",
        "badge",
        "btn",
        "button",
        "loading",
        "placeholder",
        "background",
        "banner",
        "ad_",
        "advert",
        "cms/upload",
        "/tfs/",
    ):
        if keyword in lower:
            return False

    for pattern in (r"tps-(\d+)-(\d+)", r"[_-](\d+)x(\d+)", r"-(\d+)-(\d+)\.[a-z]+$"):
        match = re.search(pattern, lower)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
            if width < 400 or height < 400:
                return False
            if height > 0:
                ratio = width / height
                if ratio > 3 or ratio < 0.33:
                    return False
    return True


def _first_valid(html: str, pattern: str) -> str | None:
    for match in re.finditer(pattern, html, re.IGNORECASE):
        normalized = _normalize_image_url(match.group(0))
        if not _is_video_url(normalized) and _is_valid_product_image(normalized):
            return normalized
    return None


def _extract_1688(html: str) -> str | None:
    for pattern in (
        r"(https?:)?//cbu01\.alicdn\.com/img/ibank/[^\"\s\')\]]+\.(jpg|jpeg|png|webp)",
        r"(https?:)?//cbu01\.alicdn\.com/[^\"\s\')\]]+\.(jpg|jpeg|png|webp)",
        r"(https?:)?//img\.alicdn\.com/imgextra/[^\"\s\')\]]+\.(jpg|jpeg|png|webp)",
    ):
        found = _first_valid(html, pattern)
        if found:
            return found

    for pattern in (
        r'"offerDetail"\s*:\s*\{[^}]*"images"\s*:\s*\[([^\]]+)\]',
        r'"images"\s*:\s*\["([^"]+)"',
    ):
        match = re.search(pattern, html)
        if not match:
            continue
        content = match.group(1)
        found = _first_valid(
            content,
            r"(https?:)?//[^\"\s,\]]+\.(jpg|jpeg|png|webp)",
        )
        if found:
            return found
    return None


def _extract_taobao(html: str) -> str | None:
    for pattern in (
        r'"pic"\s*:\s*"([^"]+)"',
        r'"picUrl"\s*:\s*"([^"]+)"',
        r'"mainPic"\s*:\s*"([^"]+)"',
        r'"images"\s*:\s*\["([^"]+)"',
    ):
        match = re.search(pattern, html)
        if not match:
            continue
        img_url = match.group(1)
        if img_url and not _is_video_url(img_url):
            normalized = _normalize_image_url(img_url)
            if _is_valid_product_image(normalized):
                return normalized

    for pattern in (
        r"(https?:)?//img\.alicdn\.com/[^\"\s\')\]]+\.(jpg|jpeg|png|webp)",
        r"(https?:)?//gw\.alicdn\.com/[^\"\s\')\]]+\.(jpg|jpeg|png|webp)",
    ):
        found = _first_valid(html, pattern)
        if found:
            return found
    return None
