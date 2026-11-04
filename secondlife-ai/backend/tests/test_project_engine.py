import json
from pathlib import Path

from app import catalog
from app.services.project_engine import StockItem, recommend, spec_matches

PROJECTS = json.loads((Path(__file__).parent.parent / "app" / "data" / "projects.json").read_text())
for i, p in enumerate(PROJECTS, start=1):
    p["id"] = i


def by_slug(matches, slug):
    return next(m for m in matches if m.slug == slug)


def item(i, category, label, specs, qty=1, cond=catalog.UNVERIFIED):
    return StockItem(i, label, category, specs, qty, cond)


def test_spec_matching_rules():
    assert spec_matches({"resistance_ohm": 470}, {"resistance_ohm": {"min": 470, "max": 2200}})
    assert not spec_matches({"resistance_ohm": 220}, {"resistance_ohm": {"min": 470}})
    assert spec_matches({"color": "Red"}, {"color": "red"})
    assert spec_matches({"part_number": "NE555"}, {"part_number": ["ne555", "lm555"]})
    assert not spec_matches({}, {"resistance_ohm": {"min": 1}})  # unknown spec never matches


def test_buildable_project():
    stock = [
        item(1, "battery", "9V", {"voltage_v": 9}, cond=catalog.TESTED_OK),
        item(2, "led", "Red LED", {"color": "red"}),
        item(3, "resistor", "1k", {"resistance_ohm": 1000}),
        item(4, "button", "Button", {}),
    ]
    matches, _ = recommend(PROJECTS, stock)
    m = by_slug(matches, "led-with-button")
    assert m.can_build and m.coverage == 1.0
    buildable = [x.slug for x in matches if x.can_build]
    assert "led-with-button" in buildable
    assert matches[0].can_build and matches[: len(buildable)] == [x for x in matches if x.can_build]  # buildable ranks first
    assert any("Test" in w for r in m.requirements for w in r.warnings)  # unverified parts flagged


def test_missing_part_reported():
    stock = [
        item(1, "battery", "9V", {"voltage_v": 9}),
        item(2, "led", "Red LED", {"color": "red"}),
        item(3, "resistor", "470", {"resistance_ohm": 470}),
    ]
    matches, _ = recommend(PROJECTS, stock)
    m = by_slug(matches, "led-dimmer")
    assert not m.can_build
    assert [p.category for p in m.missing_parts] == ["potentiometer"]


def test_damaged_and_incomplete_parts_excluded():
    stock = [
        item(1, "led", "Burnt LED", {"color": "red"}, cond=catalog.SUSPECT),
        item(2, "resistor", "Unreadable resistor", {}),
    ]
    _, excluded = recommend(PROJECTS, stock)
    reasons = {e["id"]: e["reason"] for e in excluded}
    assert "damaged" in reasons[1]
    assert "resistance_ohm" in reasons[2]


def test_capacitor_voltage_rating_is_enforced():
    base = [
        item(1, "battery", "9V", {"voltage_v": 9}),
        item(2, "transistor", "npn", {"polarity": "npn"}, qty=2),
        item(3, "resistor", "47k", {"resistance_ohm": 47000}, qty=2),
        item(4, "resistor", "470", {"resistance_ohm": 470}, qty=2),
        item(5, "led", "LED", {"color": "red"}, qty=2),
    ]
    weak = base + [item(6, "capacitor", "47uF 6.3V", {"capacitance_uf": 47, "voltage_v": 6.3}, qty=2)]
    good = base + [item(6, "capacitor", "47uF 25V", {"capacitance_uf": 47, "voltage_v": 25}, qty=2)]
    assert not by_slug(recommend(PROJECTS, weak)[0], "led-flasher").can_build
    assert by_slug(recommend(PROJECTS, good)[0], "led-flasher").can_build


def test_shared_resistors_are_not_double_counted():
    # Night light needs two resistors in different ranges; one resistor must not fill both.
    stock = [
        item(1, "battery", "9V", {"voltage_v": 9}),
        item(2, "ldr", "LDR", {}),
        item(3, "transistor", "npn", {"polarity": "npn"}),
        item(4, "led", "LED", {"color": "red"}),
        item(5, "resistor", "10k", {"resistance_ohm": 10000}),
    ]
    m = by_slug(recommend(PROJECTS, stock)[0], "night-light")
    assert not m.can_build
    assert sum(p.quantity for p in m.missing_parts) == 1
