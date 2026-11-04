"""Photo-based teardown proposals; results never enter inventory automatically."""
import asyncio
import logging
from math import isfinite
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image

from app.security import get_current_user
from app.services import salvage_guard
from app.services.inspector import full_to_jpeg, load_image
from app.services.meta_client import MetaAPIError, chat_json, image_data_url

log = logging.getLogger("secondlife.salvage")
router = APIRouter(prefix="/teardown", tags=["teardown"])

CATEGORIES = [
    "resistor", "potentiometer", "capacitor", "led", "transistor", "diode",
    "ic", "battery", "button", "buzzer", "ldr", "microcontroller", "other",
]
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024

SYSTEM = (
    "You are an electronics salvage assistant. Identify visible component proposals from a photo "
    "of a low-voltage hobby device. Never claim a part works. Do not recommend touching or opening "
    "mains-side circuitry, high-voltage capacitors, CRTs, or pressurised equipment. Skip anything "
    "swollen, burnt, leaking, or corroded. If uncertain, lower confidence and say so. "
    "Every result is only a proposal; the user must inspect and confirm it. "
    f"Allowed categories: {', '.join(CATEGORIES)}."
)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "device_guess": {"type": "string"},
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "label": {"type": "string"},
                    "marking": {"type": ["string", "null"]},
                    "location_hint": {"type": "string"},
                    "confidence": {"type": "number"},
                    "worth_harvesting": {"type": "boolean"},
                    "extraction_tip": {"type": "string"},
                    "damage_flags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "category", "label", "marking", "location_hint", "confidence",
                    "worth_harvesting", "extraction_tip", "damage_flags",
                ],
                "additionalProperties": False,
            },
        },
        "overall_warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["device_guess", "components", "overall_warnings"],
    "additionalProperties": False,
}


def _clean_response(raw: Any, allow_harvesting: bool = True) -> list[dict]:
    if not isinstance(raw, dict) or not isinstance(raw.get("components"), list):
        raise HTTPException(502, "The AI returned an invalid teardown assessment.")
    components = []
    for candidate in raw["components"][:30]:
        if not isinstance(candidate, dict):
            continue
        category = candidate.get("category")
        flags = candidate.get("damage_flags")
        flags = [str(flag)[:80] for flag in flags[:10]] if isinstance(flags, list) else []
        try:
            confidence_value = candidate.get("confidence", 0)
            confidence = 0.0 if isinstance(confidence_value, bool) else float(confidence_value)
            confidence = min(max(confidence, 0.0), 1.0) if isfinite(confidence) else 0.0
        except (TypeError, ValueError, OverflowError):
            confidence = 0.0
        battery = category == "battery"
        components.append({
            "category": category if category in CATEGORIES else "other",
            "label": str(candidate.get("label") or "")[:80],
            "marking": str(candidate["marking"])[:80] if candidate.get("marking") is not None else None,
            "location_hint": str(candidate.get("location_hint") or "")[:120],
            "confidence": confidence,
            "worth_harvesting": (
                allow_harvesting and candidate.get("worth_harvesting") is True and not flags and not battery
            ),
            "extraction_tip": (
                "Do not remove or desolder batteries. Avoid mains-side, hot, swollen, or damaged parts."
                if battery
                else "Only proceed with unplugged, low-voltage equipment; do not touch mains-side or damaged parts."
            ),
            "damage_flags": flags,
            "suggested_condition": "suspect_damaged" if flags else "unverified",
        })
    return components


@router.post("")
async def teardown(
    file: UploadFile = File(...),
    device_name: str = Form("", max_length=160),
    _user=Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image.")
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image larger than 10 MB.")

    guard = salvage_guard.assess(device_name)
    if guard["blocked"]:
        return {
            "blocked": True,
            "reasons": guard["reasons"],
            "components": [],
            "warnings": guard["warnings"],
            "safety_steps": guard["safety_steps"],
            "saved_to_inventory": False,
        }

    try:
        jpeg = await asyncio.to_thread(lambda: full_to_jpeg(load_image(data)))
    except (OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, "Could not read that image.")

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": f"User-described device: {device_name.strip() or 'unknown'}."},
            {"type": "image_url", "image_url": {"url": image_data_url(jpeg)}},
        ]},
    ]
    try:
        raw = await chat_json(messages, schema_name="salvage_assessment", schema=RESPONSE_SCHEMA)
    except MetaAPIError as exc:
        log.error("Teardown Muse call failed: %s", exc)
        raise HTTPException(503, "The inspection service is temporarily unavailable. You can still add parts manually.")

    return {
        "blocked": False,
        "device_guess": str(raw.get("device_guess") or "")[:80] if isinstance(raw, dict) else "",
        "components": _clean_response(raw, allow_harvesting=not guard["warnings"]),
        "warnings": guard["warnings"] + [
            str(w)[:200] for w in (raw.get("overall_warnings") or [])[:5]
            if isinstance(raw, dict) and isinstance(raw.get("overall_warnings"), list)
        ],
        "safety_steps": guard["safety_steps"],
        "saved_to_inventory": False,
        "next": "Review every proposal and confirm parts separately before adding inventory.",
    }
