import asyncio
import sys
sys.path.insert(0, r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\secondlife-ai\backend")

from app.services.meta_client import chat_text, chat_json, MetaAPIError, get_settings, image_data_url

async def main():
    s = get_settings()
    print("API key set:", bool(s.meta_api_key))
    print("Key prefix:", s.meta_api_key[:20] if s.meta_api_key else "NONE")
    print("Base URL:", s.meta_base_url)
    print("Model:", s.muse_model)

    # Step 1: plain text call with higher tokens
    print("\n--- Step 1: chat_text (plain, 4000 tokens) ---")
    try:
        out = await chat_text([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with exactly: PONG"},
        ], max_completion_tokens=4000)
        print("RESULT:", repr(out))
    except MetaAPIError as e:
        print("ERROR:", e, "| status:", e.status)

    # Step 2: structured JSON call with higher tokens
    print("\n--- Step 2: chat_json (structured, 4000 tokens) ---")
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
        "required": ["ok", "word"],
        "additionalProperties": False,
    }
    try:
        out = await chat_json([
            {"role": "user", "content": 'Reply with ok=true and word="ping".'},
        ], schema_name="ping", schema=schema, max_completion_tokens=4000)
        print("RESULT:", out)
    except MetaAPIError as e:
        print("ERROR:", e, "| status:", e.status)

    # Step 3: image + JSON (like the inspector does)
    print("\n--- Step 3: chat_json with image (inspector-like) ---")
    # Create a small test image
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg = buf.getvalue()
    durl = image_data_url(jpeg)

    inspect_schema = {
        "type": "object",
        "properties": {
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["resistor", "capacitor", "led", "other"]},
                        "label": {"type": "string"},
                        "specs": {"type": "object"},
                        "confidence": {"type": "number"},
                        "damage_flags": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "string"},
                        "approx_box": {"type": ["array", "null"], "items": {"type": "number"}},
                    },
                    "required": ["category", "label", "specs", "confidence", "damage_flags", "evidence", "approx_box"],
                    "additionalProperties": False,
                },
            },
            "image_quality_note": {"type": "string"},
        },
        "required": ["components", "image_quality_note"],
        "additionalProperties": False,
    }
    try:
        out = await chat_json([
            {"role": "system", "content": "You identify electronic components in photos."},
            {"role": "user", "content": [
                {"type": "text", "text": "What components do you see? Reply with JSON only."},
                {"type": "image_url", "image_url": {"url": durl}},
            ]},
        ], schema_name="component_inspection", schema=inspect_schema, max_completion_tokens=4000)
        print("RESULT:", out)
    except MetaAPIError as e:
        print("ERROR:", e, "| status:", e.status)

asyncio.run(main())
