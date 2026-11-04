import asyncio
from types import SimpleNamespace

import httpx

from app.services import meta_client


def test_default_model_matches_current_meta_model_id():
    assert meta_client.DEFAULT_MODEL == "muse-spark-1.3"


def test_chat_url_accepts_base_and_full_endpoint(monkeypatch):
    settings = SimpleNamespace(meta_base_url="https://api.meta.ai")
    monkeypatch.setattr(meta_client, "get_settings", lambda: settings)
    assert meta_client.chat_url() == "https://api.meta.ai/v1/chat/completions"

    settings.meta_base_url = "https://api.meta.ai/v1/chat/completions"
    assert meta_client.chat_url() == "https://api.meta.ai/v1/chat/completions"


def test_chat_text_uses_configured_model_and_bounded_defaults(monkeypatch):
    settings = SimpleNamespace(muse_model="")
    monkeypatch.setattr(meta_client, "get_settings", lambda: settings)
    captured = {}

    async def fake_post(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Hello."}, "finish_reason": "stop"}
                ]
            },
        )

    monkeypatch.setattr(meta_client, "_post", fake_post)
    messages = [{"role": "user", "content": "Hi"}]

    assert asyncio.run(meta_client.chat_text(messages)) == "Hello."
    assert captured["payload"]["model"] == "muse-spark-1.3"
    assert captured["payload"]["messages"] == messages
    assert captured["kwargs"]["timeout"] == 60.0
    assert captured["kwargs"]["retries"] == 2
