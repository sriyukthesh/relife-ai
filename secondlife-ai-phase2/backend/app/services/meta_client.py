"""Thin async client for Meta's OpenAI-compatible chat completions (Muse Spark).

Verified (from the handoff): POST {base}/chat/completions, Bearer auth,
model "muse-spark-1.3", max_completion_tokens, images as data URLs.
Unverified: whether response_format json_schema is honoured. If the API
rejects it with HTTP 400 we retry once with the schema embedded in the prompt.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import logging
import re
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("secondlife.meta")

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class MetaAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def chat_url() -> str:
    base = str(settings.meta_base_url).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if not base.endswith("/v1"):
        base += "/v1"
    return base + "/chat/completions"


def image_data_url(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and stray prose."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            return json.loads(t[start : end + 1])
        raise


def _with_schema_hint(messages: list[dict], schema: dict) -> list[dict]:
    hint = (
        "Reply with ONLY one JSON object that matches this JSON schema. "
        "No markdown, no commentary.\n" + json.dumps(schema)
    )
    msgs = copy.deepcopy(messages)
    if msgs and msgs[0].get("role") == "system" and isinstance(msgs[0].get("content"), str):
        msgs[0]["content"] += "\n\n" + hint
    else:
        msgs.insert(0, {"role": "system", "content": hint})
    return msgs


def _parse_response(resp: httpx.Response) -> Any:
    try:
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"].get("content")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise MetaAPIError(f"unexpected response shape: {exc!r}") from exc
    if isinstance(content, list):  # content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if not content:
        raise MetaAPIError("empty model reply")
    if choice.get("finish_reason") == "length":
        raise MetaAPIError("model reply was truncated; raise max_completion_tokens")
    try:
        return extract_json(content)
    except json.JSONDecodeError as exc:
        raise MetaAPIError("model reply was not valid JSON") from exc


async def chat_json(
    messages: list[dict],
    *,
    schema_name: str,
    schema: dict,
    max_completion_tokens: int = 1500,
    temperature: float = 0.1,
    timeout: float = 60.0,
    retries: int = 3,
) -> Any:
    """Call Muse Spark and return the parsed JSON object."""
    if not settings.meta_api_key:
        raise MetaAPIError("MODEL_API_KEY is not set")

    payload: dict[str, Any] = {
        "model": settings.muse_model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
    }
    headers = {
        "Authorization": f"Bearer {settings.meta_api_key}",
        "Content-Type": "application/json",
    }

    last: MetaAPIError = MetaAPIError("no attempt made")
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(retries):
            try:
                resp = await client.post(chat_url(), json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = MetaAPIError(f"network error: {exc!r}")
            else:
                if resp.status_code == 200:
                    return _parse_response(resp)
                if resp.status_code == 400 and "response_format" in payload:
                    log.warning("json_schema rejected (%s); retrying prompt-only", resp.text[:200])
                    payload.pop("response_format")
                    payload["messages"] = _with_schema_hint(messages, schema)
                    last = MetaAPIError(f"HTTP 400: {resp.text[:200]}", 400)
                    continue
                last = MetaAPIError(f"HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code)
                if resp.status_code not in RETRY_STATUS:
                    raise last
            await asyncio.sleep(min(2**attempt, 8))
    raise last
