"""Component catalog: categories, required specs, units and normalisation.

Pure Python (no DB / AI) so the rules are easy to test and to explain to judges.
Numeric specs are always stored in base units:
  resistance_ohm (ohms), capacitance_uf (microfarads), voltage_v (volts).
"""
from __future__ import annotations

from typing import Any

# Item conditions
UNVERIFIED = "unverified"          # identified, never tested
TESTED_OK = "tested_ok"            # user tested it with a meter / in a circuit
SUSPECT = "suspect_damaged"        # visible damage or failed test: never used in projects
CONDITIONS = (UNVERIFIED, TESTED_OK, SUSPECT)

# Where an inventory item came from
SOURCES = ("scan", "manual", "marketplace")

# Specs a component MUST have before the engine will trust it.
CATEGORIES: dict[str, dict[str, Any]] = {
    "resistor":        {"label": "Resistor",        "required": ["resistance_ohm"]},
    "potentiometer":   {"label": "Potentiometer",   "required": ["resistance_ohm"]},
    "capacitor":       {"label": "Capacitor",       "required": ["capacitance_uf", "voltage_v"]},
    "led":             {"label": "LED",             "required": ["color"]},
    "transistor":      {"label": "Transistor",      "required": ["polarity"]},
    "diode":           {"label": "Diode",           "required": ["part_number"]},
    "ic":              {"label": "Integrated circuit", "required": ["part_number"]},
    "battery":         {"label": "Battery / supply", "required": ["voltage_v"]},
    "button":          {"label": "Push button",     "required": []},
    "buzzer":          {"label": "Buzzer",          "required": ["buzzer_type"]},
    "ldr":             {"label": "Light sensor (LDR)", "required": []},
    "microcontroller": {"label": "Microcontroller board", "required": ["part_number"]},
    "other":           {"label": "Other",           "required": []},
}

# Metadata the frontend uses to build the confirm/correct form.
SPEC_FIELDS: dict[str, dict[str, Any]] = {
    "resistance_ohm":  {"label": "Resistance", "unit": "Ω", "type": "number"},
    "capacitance_uf":  {"label": "Capacitance", "unit": "µF", "type": "number"},
    "voltage_v":       {"label": "Voltage", "unit": "V", "type": "number"},
    "color":           {"label": "Colour", "unit": None, "type": "text"},
    "polarity":        {"label": "Polarity", "unit": None, "type": "choice", "choices": ["npn", "pnp"]},
    "buzzer_type":     {"label": "Buzzer type", "unit": None, "type": "choice", "choices": ["active", "passive"]},
    "part_number":     {"label": "Part number", "unit": None, "type": "text"},
}

_LOWER_FIELDS = {"color", "polarity", "buzzer_type"}
_UPPER_FIELDS = {"part_number"}


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def normalize_specs(category: str, specs: dict[str, Any]) -> dict[str, Any]:
    """Strip blanks and canonicalise text specs so matching is reliable."""
    out: dict[str, Any] = {}
    for key, value in (specs or {}).items():
        if is_blank(value):
            continue
        if isinstance(value, str):
            value = value.strip()
            if key in _LOWER_FIELDS:
                value = value.lower()
            elif key in _UPPER_FIELDS:
                value = value.upper()
        out[key] = value
    return out


def missing_required_specs(category: str, specs: dict[str, Any]) -> list[str]:
    required = CATEGORIES.get(category, {}).get("required", [])
    return [k for k in required if is_blank((specs or {}).get(k))]
