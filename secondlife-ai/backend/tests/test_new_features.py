import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import InventoryItem, User
from app.services import component_testing as ct
from app.services import salvage_guard, substitution as sub
from app.services.multilingual_safety import is_unsafe, safety_message
from app.routers import salvage, workbench
from app.security import get_current_user


def test_series_substitute_and_quantity():
    options = sub.suggest_resistor(440, [{"ohm": 220, "qty": 2}])
    assert options[0]["kind"] == "series" and options[0]["result_ohm"] == 440
    assert sub.suggest_resistor(440, [{"ohm": 220, "qty": 1}]) == []


def test_parallel_substitute():
    options = sub.suggest_resistor(110, [{"ohm": 220, "qty": 2}])
    assert options[0]["kind"] == "parallel"


def test_e24_rounds_up_without_exceeding_target_current():
    assert sub.next_e24_up(300.01) >= 300.01
    result = sub.led_resistor(5, 2.0, 10)
    assert result["chosen_ohm"] >= 300
    assert result["actual_current_ma"] <= 10


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_e24_rejects_non_positive_or_non_finite(value):
    with pytest.raises(ValueError):
        sub.next_e24_up(value)


def test_led_rejects_supply_below_forward_voltage():
    with pytest.raises(ValueError):
        sub.led_resistor(1.5, 2.0)


def test_salvage_guard_blocks_hazardous_devices_and_warns_on_chargers():
    assert salvage_guard.assess("old microwave oven")["blocked"]
    charger = salvage_guard.assess("phone charger")
    assert not charger["blocked"] and charger["warnings"]


def test_component_test_pass_fail_and_invalid_boolean():
    assert ct.evaluate("resistor", {"resistance_ohm": 220}, {"measured_ohm": 225})["verdict"] == "pass"
    assert ct.evaluate("resistor", {"resistance_ohm": 220}, {"measured_ohm": 330})["verdict"] == "fail"
    assert ct.evaluate("button", {}, {"continuity_when_pressed": "false", "open_when_released": True})["verdict"] == "fail"


def test_bad_input_fails_safely():
    assert ct.evaluate("resistor", {"resistance_ohm": 220}, {})["verdict"] == "fail"
    assert ct.evaluate("capacitor", {"capacitance_uf": 0}, {"measured_uf": 1})["verdict"] == "fail"


def test_multilingual_guard():
    assert is_unsafe("இதில் புகை வருகிறது")
    assert is_unsafe("इसमें से धुआं निकल रहा है")
    assert not is_unsafe("how do I wire an LED")
    assert "நிறுத்துங்கள்" in safety_message("புகை")


def _client(*routers):
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: object()
    return TestClient(app)


def test_teardown_hazard_is_blocked_before_ai(monkeypatch):
    def unexpected_ai_call(*args, **kwargs):
        raise AssertionError("AI must not run for blocked devices")

    monkeypatch.setattr(salvage, "chat_json", unexpected_ai_call)
    response = _client(salvage.router).post(
        "/teardown",
        files={"file": ("device.png", b"image bytes", "image/png")},
        data={"device_name": "old microwave"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["blocked"] and result["components"] == []
    assert result["saved_to_inventory"] is False


def test_teardown_safe_device_returns_proposal_without_saving(monkeypatch):
    async def fake_chat_json(messages, **kwargs):
        assert kwargs["schema_name"] == "salvage_assessment"
        return {
            "device_guess": "toy",
            "components": [{
                "category": "resistor", "label": "220 ohm resistor", "marking": "221",
                "location_hint": "near the LED", "confidence": 0.8, "worth_harvesting": True,
                "extraction_tip": "unsafe model instructions are replaced", "damage_flags": [],
            }],
            "overall_warnings": [],
        }

    image = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(image, format="PNG")
    monkeypatch.setattr(salvage, "chat_json", fake_chat_json)
    response = _client(salvage.router).post(
        "/teardown",
        files={"file": ("device.png", image.getvalue(), "image/png")},
        data={"device_name": "low-voltage toy"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["components"][0]["worth_harvesting"] is True
    assert "unsafe model instructions" not in result["components"][0]["extraction_tip"]
    assert result["saved_to_inventory"] is False


def test_workbench_public_calculator_and_procedure_require_no_database():
    client = _client(workbench.router)
    procedure = client.get("/testing/procedure/resistor")
    assert procedure.status_code == 200
    assert "measured_ohm" in procedure.json()["inputs"]
    result = client.get("/substitutions/led-resistor?supply_v=5&led_vf=2&current_ma=10")
    assert result.status_code == 200
    assert result.json()["chosen_ohm"] >= 300


def test_confirmed_component_test_moves_only_one_unit():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(email="maker@example.com", name="Maker", password_hash="unused")
        db.add(user)
        db.flush()
        db.add(InventoryItem(
            user_id=user.id,
            category="resistor",
            label="220 ohm",
            specs={"resistance_ohm": 220},
            quantity=2,
            condition="unverified",
            source="manual",
        ))
        db.commit()
        user_id = user.id

    app = FastAPI()
    app.include_router(workbench.router)

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id, email="maker@example.com", name="Maker", password_hash="unused",
    )
    response = TestClient(app).post(
        "/testing/1/complete",
        json={"measurements": {"measured_ohm": 220}, "confirmed_by_user": True},
    )
    assert response.status_code == 200
    assert response.json()["new_condition"] == "tested_ok"
    with factory() as db:
        rows = db.scalars(select(InventoryItem).order_by(InventoryItem.id)).all()
        assert [(row.quantity, row.condition) for row in rows] == [(1, "unverified"), (1, "tested_ok")]
    engine.dispose()


def test_teardown_sanitization_disables_batteries_and_damaged_parts():
    clean = salvage._clean_response({
        "components": [
            {"category": "battery", "label": "Cell", "worth_harvesting": True, "confidence": 0.9},
            {"category": "resistor", "label": "Burnt resistor", "worth_harvesting": True,
             "confidence": 0.8, "damage_flags": ["burnt"]},
        ],
    })
    assert all(not component["worth_harvesting"] for component in clean)
