"""Deterministic substitutions, guided part testing, and build-photo checks."""
import asyncio
import logging
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BuildSession, InventoryItem, Project, User
from app.security import get_current_user
from app.services import component_testing, substitution
from app.services.copilot import needs_safety_override, safety_override_reply
from app.services.inspector import full_to_jpeg, load_image
from app.services.meta_client import MetaAPIError, chat_json, image_data_url

log = logging.getLogger("secondlife.workbench")
router = APIRouter(tags=["workbench"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


@router.get("/substitutions/resistor")
def resistor_substitutes(
    target_ohm: float,
    tolerance: float = 0.10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not isfinite(target_ohm) or target_ohm <= 0:
        raise HTTPException(422, "target_ohm must be a positive finite value.")
    if not isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise HTTPException(422, "tolerance must be between 0 and 1.")
    items = db.scalars(select(InventoryItem).where(
        InventoryItem.user_id == user.id,
        InventoryItem.category == "resistor",
        InventoryItem.condition != "suspect_damaged",
        InventoryItem.quantity > 0,
    )).all()
    owned = [
        {"ohm": specs["resistance_ohm"], "qty": item.quantity}
        for item in items
        if isinstance((specs := item.specs or {}).get("resistance_ohm"), (int, float))
        and not isinstance(specs["resistance_ohm"], bool)
    ]
    try:
        options = substitution.suggest_resistor(target_ohm, owned, tolerance)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"target_ohm": target_ohm, "options": options}


@router.get("/substitutions/led-resistor")
def led_resistor(supply_v: float, led_vf: float = 2.0, current_ma: float = 10.0):
    try:
        return substitution.led_resistor(supply_v, led_vf, current_ma)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/testing/procedure/{category}")
def procedure(category: str, _user: User = Depends(get_current_user)):
    result = component_testing.PROCEDURES.get(category)
    if result is None:
        raise HTTPException(404, "No guided test for this category.")
    return result


class TestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measurements: dict[str, Any]
    confirmed_by_user: bool = False


def _move_one_unit(db: Session, item: InventoryItem, condition: str, note: str) -> InventoryItem:
    twins = db.scalars(select(InventoryItem).where(
        InventoryItem.user_id == item.user_id,
        InventoryItem.category == item.category,
        InventoryItem.condition == condition,
        InventoryItem.id != item.id,
    )).all()
    twin = next((candidate for candidate in twins if candidate.specs == item.specs), None)
    if item.quantity <= 1 and twin is None:
        item.condition = condition
        item.ai_notes = note
        return item
    item.quantity -= 1
    if twin is not None:
        twin.quantity += 1
        twin.ai_notes = note
        return twin
    moved = InventoryItem(
        user_id=item.user_id,
        category=item.category,
        label=item.label,
        specs=dict(item.specs or {}),
        quantity=1,
        condition=condition,
        source=item.source,
        ai_confidence=None,
        ai_notes=note,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(moved)
    return moved


@router.post("/testing/{item_id}/complete")
def complete_test(
    item_id: int,
    body: TestResult,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.confirmed_by_user:
        raise HTTPException(422, "confirmed_by_user must be true: you vouch for these measurements.")
    item = db.get(InventoryItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "Item not found.")
    if item.condition == "suspect_damaged":
        raise HTTPException(409, "Suspect parts cannot be promoted.")
    if item.quantity < 1:
        raise HTTPException(409, "No units left to test.")
    result = component_testing.evaluate(item.category, item.specs or {}, body.measurements)
    if result["verdict"] == "unsupported":
        return {**result, "changed": False}
    condition = "tested_ok" if result["verdict"] == "pass" else "suspect_damaged"
    moved = _move_one_unit(db, item, condition, f"User-measured {result['verdict']}: {result['reason']}")
    db.commit()
    return {**result, "changed": True, "item_id": moved.id, "new_condition": moved.condition}


CHECK_SYSTEM = (
    "Review a photo of a low-voltage hobby electronics build against the expected step. "
    "Point out only likely issues such as LED polarity, a missing resistor, loose or crossed wires, "
    "or possible shorts. Never say the circuit is safe or works. Always tell the user to verify with "
    "a multimeter before powering on. Return the requested JSON only."
)
CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "looks_consistent": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "things_to_verify": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["looks_consistent", "issues", "things_to_verify", "confidence"],
    "additionalProperties": False,
}


@router.post("/builds/{build_id}/check-photo")
async def check_photo(
    build_id: int,
    file: UploadFile = File(...),
    note: str = Form("", max_length=300),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if needs_safety_override(note):
        return {"safety_stop": True, "message": safety_override_reply(note)}
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image.")
    build = db.get(BuildSession, build_id)
    if build is None or build.user_id != user.id or build.status != "active":
        raise HTTPException(404, "Active build not found.")
    project = db.get(Project, build.project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    steps = project.steps or []
    step = steps[build.current_step] if 0 <= build.current_step < len(steps) else ""
    step_text = (
        step if isinstance(step, str)
        else step.get("text") or step.get("instruction") or str(step)
    )
    raw_image = await file.read(MAX_IMAGE_BYTES + 1)
    if not raw_image:
        raise HTTPException(400, "Empty file.")
    if len(raw_image) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image larger than 6 MB.")
    try:
        jpeg = await asyncio.to_thread(lambda: full_to_jpeg(load_image(raw_image)))
    except (OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, "Could not read that image.")

    messages = [
        {"role": "system", "content": CHECK_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": (
                f"Project: {project.title}. Current step {build.current_step + 1}: {step_text}. "
                f"User note: {note.strip()}"
            )},
            {"type": "image_url", "image_url": {"url": image_data_url(jpeg)}},
        ]},
    ]
    try:
        result = await chat_json(messages, schema_name="build_photo_check", schema=CHECK_SCHEMA)
    except MetaAPIError as exc:
        log.error("Build photo check Muse call failed: %s", exc)
        return {
            "available": False,
            "message": "AI check unavailable. Re-read the step and verify with a multimeter.",
        }
    if not isinstance(result, dict):
        raise HTTPException(502, "The AI returned an invalid build check.")
    confidence = result.get("confidence", 0)
    try:
        confidence = min(max(float(confidence), 0.0), 1.0)
        if not isfinite(confidence):
            confidence = 0.0
    except (TypeError, ValueError, OverflowError):
        confidence = 0.0
    return {
        "available": True,
        "looks_consistent": result.get("looks_consistent") is True,
        "issues": [str(issue)[:300] for issue in result.get("issues", [])[:6]],
        "things_to_verify": [str(item)[:300] for item in result.get("things_to_verify", [])[:6]]
        + ["Check polarity and continuity with a multimeter before connecting power."],
        "confidence": confidence,
        "disclaimer": "This is a hint, not a safety certification. Verify with a multimeter before connecting power.",
    }
