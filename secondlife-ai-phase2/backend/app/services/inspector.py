"""Part inspection: photo -> (optional segmentation) -> model -> PROPOSALS.

Nothing here touches the database. Proposals only become inventory after the
user confirms them via POST /inventory with confirmed_by_user=true.
The AI never certifies that a part works; suggested_condition is only ever
"unverified" or "suspect_damaged".
"""
from __future__ import annotations

import asyncio
import io
import uuid
from typing import Any

from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from app.catalog import is_blank, missing_required_specs, normalize_specs
from app.services import sam_client
from app.services.meta_client import MetaAPIError, chat_json, image_data_url

CATEGORIES = [
    "resistor", "potentiometer", "capacitor", "led", "transistor", "diode", "ic",
    "battery", "button", "buzzer", "ldr", "microcontroller", "other",
]
DAMAGE_FLAGS = [
    "cracked_or_broken", "burnt_or_scorched", "corroded", "bent_or_missing_leads",
    "swollen_or_leaking", "discolored", "other",
]
DISCLAIMER = (
    "These are AI proposals from a photo, not an electrical test. Confirm or correct "
    "every item, and test parts before relying on them."
)
MAX_IMAGE_SIDE = 1600
MAX_SEGMENTS = 12
MIN_SEGMENT_SCORE = 0.30
MIN_SEGMENT_AREA = 0.002  # fraction of the image
UNKNOWN_WORDS = {"", "unknown", "n/a", "na", "none", "null", "?", "unreadable"}


# ---------- response models ----------
class ComponentProposal(BaseModel):
    proposal_id: str
    category: str
    label: str
    specs: dict[str, Any]
    quantity: int = 1
    suggested_condition: str  # "unverified" | "suspect_damaged" only
    ai_confidence: float
    needs_review: bool
    missing_required_specs: list[str] = Field(default_factory=list)
    visible_markings: str = ""
    damage_flags: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    evidence: str = ""
    box: list[int] | None = None  # pixels in the analysed image
    box_source: str = "none"  # "sam" | "model_estimate" | "none"
    crop_index: int = 0


class InspectResponse(BaseModel):
    proposals: list[ComponentProposal]
    segmentation_mode: str
    image_width: int
    image_height: int
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


# ---------- JSON schema for strict structured output ----------
def _nullable(t: str) -> dict:
    return {"type": [t, "null"]}


_SPEC_PROPS = {
    "resistance_ohm": _nullable("number"),
    "capacitance_uf": _nullable("number"),
    "voltage_v": _nullable("number"),
    "color": _nullable("string"),
    "polarity": _nullable("string"),
    "buzzer_type": _nullable("string"),
    "part_number": _nullable("string"),
}
_COMPONENT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "label": {"type": "string"},
        "specs": {
            "type": "object",
            "properties": _SPEC_PROPS,
            "required": list(_SPEC_PROPS),
            "additionalProperties": False,
        },
        "quantity_estimate": {"type": "integer"},
        "visible_markings": {"type": "string"},
        "damage_flags": {"type": "array", "items": {"type": "string", "enum": DAMAGE_FLAGS}},
        "confidence": {"type": "number"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "string"},
        "approx_box": {"type": ["array", "null"], "items": {"type": "number"}},
    },
    "required": [
        "category", "label", "specs", "quantity_estimate", "visible_markings",
        "damage_flags", "confidence", "uncertainties", "evidence", "approx_box",
    ],
    "additionalProperties": False,
}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "components": {"type": "array", "items": _COMPONENT_SCHEMA},
        "image_quality_note": {"type": "string"},
    },
    "required": ["components", "image_quality_note"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are the part-identification step of an electronics reuse app for students and makers.
Look at the photo and propose what electronic components are visible. A human will confirm or correct every proposal.

Rules:
- Report only what you can see. Use null for any spec you cannot read or support from visible evidence. Never invent values.
- Put the exact visible text/markings (printed numbers, colour bands, capacitor labels) in visible_markings. Put your reasoning in evidence.
- Resistance from colour bands is allowed only if all bands are clearly legible; list the bands in evidence and add an uncertainty if unsure.
- Units: resistance_ohm in ohms, capacitance_uf in microfarads, voltage_v in volts.
- polarity is "npn" or "pnp" for transistors only. buzzer_type is "active" or "passive" only if visibly supported, else null.
- Never say a part works, is good, or is tested. You can only describe what is visible. Flag visible damage in damage_flags.
- confidence is 0 to 1 and must be honest: low when markings are blurry, hidden or you are guessing the category.
- uncertainties lists what you could not determine.
- quantity_estimate is how many identical parts are visible (at least 1).
- approx_box is [x0, y0, x1, y1] as fractions of the image (0 to 1) for whole-photo mode, or null when unsure.
- If the image shows no electronic component, return an empty components list.
- category must be one of the allowed values; use "other" when unsure."""


def build_messages(jpeg: bytes, whole_photo: bool) -> list[dict]:
    task = (
        "This photo may show several components. List each distinct component or group of identical components."
        if whole_photo
        else "This is a crop expected to contain ONE component. Return one entry, or none if no component is visible."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": task},
                {"type": "image_url", "image_url": {"url": image_data_url(jpeg)}},
            ],
        },
    ]


# ---------- catalog adapters (Phase 1 signatures were not visible to me) ----------
def _normalize(category: str, specs: dict) -> dict:
    try:
        return normalize_specs(category, specs)
    except TypeError:
        return normalize_specs(specs)


def _missing_required(category: str, specs: dict) -> list[str]:
    try:
        return list(missing_required_specs(category, specs))
    except TypeError:
        return list(missing_required_specs({"category": category, "specs": specs}))


# ---------- image helpers ----------
def load_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    return img


def _to_jpeg(img: Image.Image, max_side: int) -> bytes:
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def full_to_jpeg(img: Image.Image) -> bytes:
    return _to_jpeg(img, 1280)


def crop_to_jpeg(img: Image.Image, box: tuple[int, int, int, int], pad: float = 0.08) -> bytes:
    x0, y0, x1, y1 = box
    px, py = int((x1 - x0) * pad), int((y1 - y0) * pad)
    region = (max(0, x0 - px), max(0, y0 - py), min(img.width, x1 + px), min(img.height, y1 + py))
    return _to_jpeg(img.crop(region), 768)


def _norm_box_to_px(box: Any, w: int, h: int) -> list[int] | None:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if not all(0.0 <= v <= 1.0 for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        return None
    return [round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)]


# ---------- deterministic post-processing ----------
def build_proposal(
    raw: dict, *, crop_index: int, box: list[int] | None, box_source: str
) -> ComponentProposal:
    category = raw.get("category")
    if category not in CATEGORIES:
        category = "other"

    specs_in = raw.get("specs") or {}
    specs = {
        k: v
        for k, v in specs_in.items()
        if not is_blank(v) and str(v).strip().lower() not in UNKNOWN_WORDS
    }
    specs = _normalize(category, specs)
    missing = _missing_required(category, specs)

    try:
        conf = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    flags = [f for f in (raw.get("damage_flags") or []) if f in DAMAGE_FLAGS]
    uncertainties = [str(u) for u in (raw.get("uncertainties") or []) if str(u).strip()]
    try:
        qty = int(raw.get("quantity_estimate", 1))
    except (TypeError, ValueError):
        qty = 1
    qty = max(1, min(99, qty))

    needs_review = bool(conf < 0.6 or missing or uncertainties or flags or category == "other")
    return ComponentProposal(
        proposal_id=uuid.uuid4().hex[:12],
        category=category,
        label=str(raw.get("label") or category).strip()[:80],
        specs=specs,
        quantity=qty,
        suggested_condition="suspect_damaged" if flags else "unverified",
        ai_confidence=round(conf, 2),
        needs_review=needs_review,
        missing_required_specs=missing,
        visible_markings=str(raw.get("visible_markings") or "")[:200],
        damage_flags=flags,
        uncertainties=uncertainties,
        evidence=str(raw.get("evidence") or "")[:400],
        box=box,
        box_source=box_source if box else "none",
        crop_index=crop_index,
    )


def _filter_segments(segments: list[sam_client.Segment], w: int, h: int) -> list[sam_client.Segment]:
    keep = []
    for s in segments:
        x0, y0, x1, y1 = s.box
        area = max(0, x1 - x0) * max(0, y1 - y0) / float(w * h)
        if s.score >= MIN_SEGMENT_SCORE and area >= MIN_SEGMENT_AREA:
            keep.append(s)
    keep.sort(key=lambda s: s.score, reverse=True)
    return keep[:MAX_SEGMENTS]


async def _analyse(jpeg: bytes, whole_photo: bool) -> dict:
    return await chat_json(
        build_messages(jpeg, whole_photo),
        schema_name="component_inspection",
        schema=RESPONSE_SCHEMA,
        max_completion_tokens=2000 if whole_photo else 900,
    )


async def inspect_image(data: bytes) -> InspectResponse:
    img = await asyncio.to_thread(load_image, data)
    w, h = img.size
    notes: list[str] = []

    try:
        segments, mode, seg_notes = await sam_client.segment(img)
        notes += seg_notes
    except sam_client.SamUnavailable as exc:
        segments, mode = [], "whole_image"
        notes.append(f"SAM unavailable ({exc}); the whole photo was analysed at once.")

    segments = _filter_segments(segments, w, h)
    if mode == "sam" and not segments:
        mode = "whole_image"
        notes.append("SAM found no usable segments; the whole photo was analysed at once.")

    proposals: list[ComponentProposal] = []

    if mode == "whole_image":
        jpeg = await asyncio.to_thread(full_to_jpeg, img)
        result = await _analyse(jpeg, whole_photo=True)
        if result.get("image_quality_note"):
            notes.append(result["image_quality_note"])
        for i, comp in enumerate(result.get("components") or []):
            box = _norm_box_to_px(comp.get("approx_box"), w, h)
            proposals.append(build_proposal(comp, crop_index=i, box=box, box_source="model_estimate"))
    else:
        sem = asyncio.Semaphore(3)

        async def one(seg: sam_client.Segment) -> dict:
            jpeg = await asyncio.to_thread(crop_to_jpeg, img, seg.box)
            async with sem:
                return await _analyse(jpeg, whole_photo=False)

        results = await asyncio.gather(*(one(s) for s in segments), return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]
        if failures and len(failures) == len(results):
            raise failures[0] if isinstance(failures[0], MetaAPIError) else MetaAPIError(str(failures[0]))
        for i, (seg, res) in enumerate(zip(segments, results)):
            if isinstance(res, Exception):
                notes.append(f"Segment {i + 1} could not be analysed; add it manually.")
                continue
            for comp in (res.get("components") or [])[:1]:
                proposals.append(build_proposal(comp, crop_index=i, box=list(seg.box), box_source="sam"))

    if not proposals:
        notes.append("No components were proposed. Try a closer, well-lit photo on a plain background.")

    return InspectResponse(
        proposals=proposals, segmentation_mode=mode, image_width=w, image_height=h, notes=notes
    )
