import asyncio
import sys
import io
from PIL import Image, ImageDraw

sys.path.insert(0, r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\secondlife-ai\backend")

from app.services.meta_client import chat_json, image_data_url, MetaAPIError

img = Image.new("RGB", (400, 300), "black")
draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 150, 100], fill="red", outline="white")
draw.rectangle([200, 100, 280, 150], fill="blue", outline="white")
draw.ellipse([100, 150, 160, 210], fill="green", outline="white")
draw.rectangle([250, 200, 350, 280], fill="yellow", outline="white")

buf = io.BytesIO()
img.save(buf, format="JPEG", quality=85)
jpeg = buf.getvalue()
durl = image_data_url(jpeg)

async def main():
    print("--- Testing /inspect-like call with image ---")
    inspect_schema = {
        "type": "object",
        "properties": {
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["resistor", "capacitor", "led", "ic", "transistor", "diode", "battery", "button", "buzzer", "ldr", "microcontroller", "other"]},
                        "label": {"type": "string"},
                        "specs": {"type": "object"},
                        "quantity_estimate": {"type": "integer"},
                        "visible_markings": {"type": "string"},
                        "damage_flags": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number"},
                        "uncertainties": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "string"},
                        "approx_box": {"type": ["array", "null"], "items": {"type": "number"}},
                    },
                    "required": ["category", "label", "specs", "quantity_estimate", "visible_markings", "damage_flags", "confidence", "uncertainties", "evidence", "approx_box"],
                    "additionalProperties": False,
                },
            },
            "image_quality_note": {"type": "string"},
        },
        "required": ["components", "image_quality_note"],
        "additionalProperties": False,
    }
    try:
        result = await chat_json(
            [
                {"role": "system", "content": "You identify electronic components in photos."},
                {"role": "user", "content": [
                    {"type": "text", "text": "What electronic components do you see in this photo? Identify each one."},
                    {"type": "image_url", "image_url": {"url": durl}},
                ]},
            ],
            schema_name="component_inspection",
            schema=inspect_schema,
            max_completion_tokens=4000,
        )
        print("RESULT:", result)
    print("\n--- Testing /teardown-like call with image ---")
    teardown_schema = {
        "type": "object",
        "properties": {
            "device_guess": {"type": "string"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "label": {"type": "string"},
                        "marking": {"type": ["string", "null"]},
                        "location_hint": {"type": "string"},
                        "confidence": {"type": "number"},
                        "worth_harvesting": {"type": "boolean"},
                        "extraction_tip": {"type": "string"},
                        "damage_flags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["category", "label", "marking", "location_hint", "confidence", "worth_harvesting", "extraction_tip", "damage_flags"],
                    "additionalProperties": False,
                },
            },
            "overall_warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["device_guess", "components", "overall_warnings"],
        "additionalProperties": False,
    }
    try:
        result = await chat_json(
            [
                {"role": "system", "content": "You are an electronics salvage assistant."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Identify salvageable components from this device photo."},
                    {"type": "image_url", "image_url": {"url": durl}},
                ]},
            ],
            schema_name="salvage_assessment",
            schema=teardown_schema,
            max_completion_tokens=4000,
        )
        print("RESULT:", result)
    except MetaAPIError as e:
        print("ERROR:", e, "| status:", e.status)
    except MetaAPIError as e:
        print("ERROR:", e, "| status:", e.status)