"""Embedding — OpenAI 兼容 `/v1/embeddings`。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.models import ProviderSettings
from llm.models import EmbeddingRequest, EmbeddingResponse, LlmError
from llm.providers.openai import normalize_base_url


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
