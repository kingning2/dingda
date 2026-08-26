"""Embedding — OpenAI 兼容 ``/v1/embeddings``。

用 urllib 发请求，供知识库建索引与检索生成向量。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent.llm.models import EmbeddingRequest, EmbeddingResponse, LlmError
from config.models import ProviderSettings


def normalize_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not base:
        return "https://api.openai.com/v1"
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/v1") or base.endswith("/v2") or base.endswith("/v3"):
        return base
    return f"{base}/v1"


def embed(settings: ProviderSettings, request: EmbeddingRequest) -> EmbeddingResponse:
    base = normalize_base_url(settings.base_url)
    url = f"{base}/embeddings"
    payload = {"model": request.model or settings.model, "input": request.texts}
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise LlmError(f"embeddings http {error.code}") from error
    except URLError as error:
        raise LlmError(f"embeddings transport: {error}") from error

    rows = data.get("data") or []
    vectors = [row.get("embedding") or [] for row in rows]
    return EmbeddingResponse(vectors=vectors)
