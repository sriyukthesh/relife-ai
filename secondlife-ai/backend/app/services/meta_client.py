
"""
Async client for Meta's OpenAI-compatible Chat Completions API.

Supports:
- Muse Spark 1.3
- Text generation
- JSON structured output with prompt fallback
- Image inputs using base64 data URLs
- Retry/backoff for transient errors
- Detailed, safe API error logging

Configuration:
    MODEL_API_KEY
    META_BASE_URL=https://api.meta.ai/v1
    MUSE_MODEL=muse-spark-1.3
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

from app.config import get_settings


log = logging.getLogger("secondlife.meta")

RETRY_STATUS = {
    408,
    409,
    429,
    500,
    502,
    503,
    504,
}

DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_TIMEOUT = 60.0
DEFAULT_TEXT_TOKENS = 8000
DEFAULT_JSON_TOKENS = 4000


class MetaAPIError(RuntimeError):
    """Raised when the Meta Model API request fails."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
    ):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def chat_url() -> str:
    """
    Construct the Chat Completions endpoint.

    Supported base URLs:
        https://api.meta.ai
        https://api.meta.ai/v1
        https://api.meta.ai/v1/chat/completions
    """

    base = str(
        get_settings().meta_base_url
    ).strip().rstrip("/")

    if not base:
        base = "https://api.meta.ai/v1"

    if base.endswith("/chat/completions"):
        return base

    if not base.endswith("/v1"):
        base += "/v1"

    return base + "/chat/completions"


def get_model_name() -> str:
    """Return the configured Muse Spark model."""

    model = str(
        get_settings().muse_model or DEFAULT_MODEL
    ).strip()

    if not model:
        model = DEFAULT_MODEL

    return model


def get_api_key() -> str:
    """Read the API key from backend settings."""

    key = str(
        get_settings().meta_api_key or ""
    ).strip()

    if not key:
        raise MetaAPIError(
            "MODEL_API_KEY is not configured."
        )

    return key


# ---------------------------------------------------------
# Image handling
# ---------------------------------------------------------

def image_data_url(
    data: bytes,
    mime: str = "image/jpeg",
) -> str:
    """
    Convert image bytes to a base64 data URL.

    Example:
        data:image/jpeg;base64,...
    """

    if not data:
        raise ValueError("Image data cannot be empty.")

    encoded = base64.b64encode(data).decode("ascii")

    return f"data:{mime};base64,{encoded}"


# ---------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------

def extract_json(text: str) -> Any:
    """
    Extract JSON from a model response.

    Supports:
    - Plain JSON
    - JSON surrounded by markdown fences
    - JSON surrounded by explanatory text
    """

    if not isinstance(text, str):
        raise ValueError("Expected a string response.")

    text = text.strip()

    if not text:
        raise ValueError("Empty JSON response.")

    # Remove markdown code fences.
    text = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Try parsing the entire response first.
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Find a JSON object inside surrounding text.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        return json.loads(
            text[start:end + 1]
        )

    # Find a JSON array if no object exists.
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end > start:
        return json.loads(
            text[start:end + 1]
        )

    raise ValueError(
        "No valid JSON object or array found."
    )


# ---------------------------------------------------------
# JSON schema fallback
# ---------------------------------------------------------

def _with_schema_hint(
    messages: list[dict],
    schema: dict,
) -> list[dict]:
    """
    Add JSON schema instructions to the system prompt.

    Used when the API rejects response_format.
    """

    schema_text = json.dumps(
        schema,
        ensure_ascii=False,
    )

    hint = (
        "You must respond with exactly one valid JSON object "
        "that follows this JSON schema.\n"
        "Do not include markdown.\n"
        "Do not include explanations.\n"
        "Do not include text outside the JSON object.\n\n"
        f"JSON schema:\n{schema_text}"
    )

    msgs = copy.deepcopy(messages)

    if (
        msgs
        and msgs[0].get("role") == "system"
        and isinstance(msgs[0].get("content"), str)
    ):
        msgs[0]["content"] += "\n\n" + hint

    else:
        msgs.insert(
            0,
            {
                "role": "system",
                "content": hint,
            },
        )

    return msgs


# ---------------------------------------------------------
# Response parsing
# ---------------------------------------------------------

def _content(
    resp: httpx.Response,
) -> str:
    """
    Extract text from the API response.

    Logs response metadata to help diagnose:
    - Empty responses
    - Truncated completions
    - Unexpected response formats
    """

    try:
        body = resp.json()

        choices = body["choices"]

        if not choices:
            raise ValueError(
                "Response contains no choices."
            )

        choice = choices[0]

        message = choice["message"]

        content = message.get("content")

        finish_reason = choice.get(
            "finish_reason"
        )

    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError,
    ) as exc:

        log.error(
            "Unexpected Muse response shape: %s",
            resp.text[:1000],
        )

        raise MetaAPIError(
            f"Unexpected response shape: {exc!r}"
        ) from exc

    log.info(
        "Muse response received: model=%s "
        "finish_reason=%s usage=%s",
        body.get("model"),
        finish_reason,
        body.get("usage"),
    )

    # Handle content represented as a list of parts.
    if isinstance(content, list):

        text_parts = []

        for part in content:

            if not isinstance(part, dict):
                continue

            if part.get("type") == "text":
                text_parts.append(
                    part.get("text", "")
                )

            elif "text" in part:
                text_parts.append(
                    str(part["text"])
                )

        content = "".join(text_parts)

    # Detect empty output.
    if (
        content is None
        or not isinstance(content, str)
        or not content.strip()
    ):

        log.error(
            "Muse returned empty content. "
            "finish_reason=%s response=%s",
            finish_reason,
            resp.text[:1000],
        )

        # Reasoning models (Muse Spark 1.3) spend tokens on reasoning before
        # producing the final answer. When we hit the token cap with empty
        # content, signal the caller to retry with a higher limit.
        if finish_reason == "length":
            raise MetaAPIError(
                "Muse response was truncated with empty content; "
                "retry with higher max_completion_tokens.",
                status=413,
            )
        raise MetaAPIError("Muse returned an empty response.")

    # Detect truncation: return the partial content instead of failing,
    # so the user still gets a useful answer.
    if finish_reason == "length":

        log.warning(
            "Muse response was truncated (finish_reason=length). "
            "Returning partial content; consider raising max_completion_tokens."
        )

    if finish_reason == "content_filter":

        raise MetaAPIError(
            "Muse response was blocked by a content filter."
        )

    return content.strip()


# ---------------------------------------------------------
# Core HTTP request
# ---------------------------------------------------------

async def _post(
    payload: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
    fallback_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    """
    Send a request to Meta's Chat Completions API.

    Features:
    - Bearer authentication
    - Transient-error retries
    - Exponential backoff
    - One fallback request for HTTP 400
    - Detailed API error logging
    """

    key = get_api_key()

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = chat_url()

    max_attempts = max(
        1,
        retries,
    )

    attempt = 0

    fallback_used = False

    last_error = MetaAPIError(
        "No request attempt completed."
    )
    log.info(
        "Sending Muse request: model=%s endpoint=%s",
        payload.get("model"),
        url,
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
    ) as client:

        while attempt < max_attempts:

            try:

                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

            except httpx.TimeoutException as exc:

                last_error = MetaAPIError(
                    f"Muse API timeout: {exc!r}"
                )

                log.warning(
                    "Muse request timed out: %s",
                    exc,
                )

            except httpx.TransportError as exc:

                last_error = MetaAPIError(
                    f"Muse API network error: {exc!r}"
                )

                log.warning(
                    "Muse network error: %s",
                    exc,
                )

            else:

                if response.status_code == 200:

                    return response

                status = response.status_code

                response_text = response.text[:1500]

                last_error = MetaAPIError(
                    f"HTTP {status}: {response_text}",
                    status,
                )

                log.error(
                    "Muse API returned HTTP %s: %s",
                    status,
                    response_text,
                )

                # If structured output is rejected,
                # retry once using a prompt-only schema.
                if (
                    status == 400
                    and fallback_payload is not None
                    and not fallback_used
                ):

                    log.warning(
                        "Structured output rejected. "
                        "Retrying with prompt-only JSON."
                    )

                    payload = fallback_payload

                    fallback_payload = None

                    fallback_used = True

                    # Do not consume a normal retry.
                    continue

                # Non-transient errors should not be retried.
                if status not in RETRY_STATUS:

                    raise last_error

            attempt += 1

            if attempt >= max_attempts:
                break

            delay = min(
                2 ** attempt,
                8,
            )

            log.info(
                "Retrying Muse request in %s seconds. "
                "Attempt %s/%s",
                delay,
                attempt + 1,
                max_attempts,
            )

            await asyncio.sleep(delay)

    raise last_error


# ---------------------------------------------------------
# Text generation
# ---------------------------------------------------------

async def chat_text(
    messages: list[dict],
    *,
    max_completion_tokens: int = DEFAULT_TEXT_TOKENS,
    temperature: float | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> str:
    """
    Generate a plain-text Muse Spark response.

    Used by:
        ReLife AI Copilot
        Project recommendations
        General AI assistance

    If the API rejects the request with HTTP 400, retries once using a
    minimal payload (no temperature / bounded tokens) so a single
    unsupported parameter does not break the whole copilot.
    """

    if not messages:
        raise ValueError(
            "Messages cannot be empty."
        )

    payload = {
        "model": get_model_name(),
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
    }

    # Omit temperature to use the model's default
    # unless the caller explicitly supplies a value.
    if temperature is not None:

        payload["temperature"] = temperature

    # Fallback payload: minimal, most-likely-to-be-accepted request.
    fallback_payload = {
        "model": get_model_name(),
        "messages": messages,
    }

    try:
        response = await _post(
            payload,
            timeout=timeout,
            retries=retries,
            fallback_payload=fallback_payload,
        )
        return _content(response)
    except MetaAPIError as exc:
        if exc.status == 413 and max_completion_tokens < 32000:
            log.warning(
                "Muse text needs more tokens; retrying with %d",
                max_completion_tokens * 2,
            )
            return await chat_text(
                messages,
                max_completion_tokens=max_completion_tokens * 2,
                temperature=temperature,
                timeout=timeout,
                retries=retries,
            )
        raise


async def _chat_text_with_token_retry(
    messages: list[dict],
    *,
    max_completion_tokens: int,
    temperature: float | None,
    timeout: float,
    retries: int,
) -> str:
    """chat_text that doubles max_completion_tokens when the model needs more room (reasoning models)."""
    try:
        return await chat_text(
            messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            timeout=timeout,
            retries=retries,
        )
    except MetaAPIError as exc:
        if exc.status == 413 and max_completion_tokens < 32000:
            log.warning("Muse text needs more tokens; retrying with %d", max_completion_tokens * 2)
            return await chat_text(
                messages,
                max_completion_tokens=max_completion_tokens * 2,
                temperature=temperature,
                timeout=timeout,
                retries=retries,
            )
        raise


# ---------------------------------------------------------
# Structured JSON generation
# ---------------------------------------------------------

async def chat_json(
    messages: list[dict],
    *,
    schema_name: str,
    schema: dict,
    max_completion_tokens: int = DEFAULT_JSON_TOKENS,
    temperature: float | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> Any:
    """
    Generate a structured JSON response.

    Uses JSON schema response_format first.

    If the API rejects the structured output
    configuration with HTTP 400, retries once
    using schema instructions in the prompt.
    """

    if not messages:
        raise ValueError(
            "Messages cannot be empty."
        )

    base = {
        "model": get_model_name(),
        "max_completion_tokens": max_completion_tokens,
    }

    if temperature is not None:

        base["temperature"] = temperature

    strict_payload = {
        **base,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
        },
    }

    prompt_only_payload = {
        **base,
        "messages": _with_schema_hint(
            messages,
            schema,
        ),
    }

    try:
        response = await _post(
            strict_payload,
            timeout=timeout,
            retries=retries,
            fallback_payload=prompt_only_payload,
        )
        text = _content(response)

        result = extract_json(text)

    except MetaAPIError as exc:
        if exc.status == 413 and max_completion_tokens < 32000:
            log.warning(
                "Muse JSON needs more tokens; retrying with %d",
                max_completion_tokens * 2,
            )
            return await chat_json(
                messages,
                schema_name=schema_name,
                schema=schema,
                max_completion_tokens=max_completion_tokens * 2,
                temperature=temperature,
                timeout=timeout,
                retries=retries,
            )
        raise
    except (json.JSONDecodeError, ValueError) as exc:

        log.error(
            "Muse returned invalid JSON: %s",
            text[:1000],
        )

        raise MetaAPIError(
            "Muse response was not valid JSON."
        ) from exc

    return result
