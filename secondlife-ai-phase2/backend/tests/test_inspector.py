import asyncio
import io

from PIL import Image

from app.services import inspector
from app.services.meta_client import extract_json


def _raw(**over):
    base = {
        "category": "resistor", "label": "220 ohm resistor",
        "specs": {"resistance_ohm": 220, "capacitance_uf": None, "voltage_v": None, "color": None,
                  "polarity": None, "buzzer_type": None, "part_number": None},
        "quantity_estimate": 2, "visible_markings": "red red brown gold", "damage_flags": [],
        "confidence": 0.9, "uncertainties": [], "evidence": "bands legible", "approx_box": [0.1, 0.1, 0.5, 0.5],
    }
    base.update(over)
    return base


def test_extract_json_handles_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_nulls_dropped_and_never_tested_ok():
    p = inspector.build_proposal(_raw(), crop_index=0, box=None, box_source="sam")
    assert p.specs == {"resistance_ohm": 220}
    assert p.suggested_condition == "unverified"
    assert p.box_source == "none"  # no box -> source reset


def test_damage_flag_marks_suspect_and_review():
    p = inspector.build_proposal(_raw(damage_flags=["burnt_or_scorched"]), crop_index=0, box=None, box_source="sam")
    assert p.suggested_condition == "suspect_damaged" and p.needs_review


def test_unknown_category_becomes_other():
    p = inspector.build_proposal(_raw(category="flux capacitor"), crop_index=0, box=None, box_source="sam")
    assert p.category == "other" and p.needs_review


def test_confidence_clamped():
    p = inspector.build_proposal(_raw(confidence=7), crop_index=0, box=None, box_source="sam")
    assert p.ai_confidence == 1.0


def test_whole_image_flow_with_fake_model(monkeypatch):
    async def fake_chat_json(*a, **k):
        return {"components": [_raw()], "image_quality_note": ""}

    monkeypatch.setattr(inspector, "chat_json", fake_chat_json)
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, format="PNG")
    res = asyncio.run(inspector.inspect_image(buf.getvalue()))
    assert res.segmentation_mode == "whole_image"
    assert len(res.proposals) == 1
    assert res.proposals[0].box == [40, 30, 200, 150]
    assert "not an electrical test" in res.disclaimer
