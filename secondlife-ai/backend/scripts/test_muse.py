"""Minimal Muse Spark check. Run from backend/:  python scripts/test_muse.py [photo.jpg]

Step 1: plain JSON-schema call (tells you if strict json_schema works).
Step 2 (optional): send one photo through the real inspector prompt.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.meta_client import chat_json  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
    "required": ["ok", "word"],
    "additionalProperties": False,
}


async def main() -> None:
    out = await chat_json(
        [{"role": "user", "content": 'Reply with ok=true and word="ping".'}],
        schema_name="ping",
        schema=SCHEMA,
        max_completion_tokens=100,
    )
    print("Step 1 OK:", out)
    if len(sys.argv) > 1:
        from app.services.inspector import inspect_image

        res = await inspect_image(Path(sys.argv[1]).read_bytes())
        print(res.model_dump_json(indent=2))


asyncio.run(main())
