"""Deterministic component checks: the user measures and confirms; code evaluates."""
from math import isfinite
from typing import Any

PROCEDURES = {
    "resistor": {
        "tool": "Multimeter on resistance (Ω)",
        "steps": ["Remove the resistor from any circuit.", "Touch the probes to both leads.", "Enter the displayed value."],
        "inputs": ["measured_ohm"],
    },
    "potentiometer": {
        "tool": "Multimeter on resistance (Ω)",
        "steps": ["Measure across the two outer pins.", "Measure outer pin to middle pin while turning the knob.", "Confirm the reading sweeps smoothly from near 0 to full value."],
        "inputs": ["measured_ohm", "wiper_sweeps_smoothly"],
    },
    "diode": {
        "tool": "Multimeter on diode mode",
        "steps": ["Red probe on anode, black on cathode: note the forward voltage.", "Swap probes: the meter should show OL (open)."],
        "inputs": ["forward_v", "reverse_open"],
    },
    "led": {
        "tool": "Multimeter on diode mode",
        "steps": ["Use diode mode with the red probe on the anode and black on the cathode.", "Record whether it lights and the forward voltage if shown."],
        "inputs": ["lights_up"],
    },
    "capacitor": {
        "tool": "Multimeter with capacitance mode",
        "steps": ["Only test a low-voltage capacitor that is known to be safely discharged.", "Do not short capacitor leads directly. If you cannot verify it is discharged, stop and ask a qualified person.", "Measure capacitance and enter µF."],
        "inputs": ["measured_uf"],
    },
    "battery": {
        "tool": "Multimeter on DC volts",
        "steps": ["Only test an undamaged low-voltage battery.", "Touch red to +, black to −. Enter the voltage; do not test swollen, hot, or leaking cells."],
        "inputs": ["measured_v"],
    },
    "button": {
        "tool": "Multimeter on continuity",
        "steps": ["Probe both terminals while released: expect open.", "Press the button: expect continuity."],
        "inputs": ["continuity_when_pressed", "open_when_released"],
    },
}


def _number(values: dict[str, Any], key: str) -> float:
    raw = values[key]
    if isinstance(raw, bool):
        raise ValueError("measurement must be numeric")
    value = float(raw)
    if not isfinite(value):
        raise ValueError("measurement must be finite")
    return value


def _boolean(values: dict[str, Any], key: str) -> bool:
    value = values[key]
    if not isinstance(value, bool):
        raise ValueError("measurement must be true or false")
    return value


def _within(measured: float, nominal: float, low: float, high: float) -> bool:
    return isfinite(measured) and isfinite(nominal) and nominal > 0 and nominal * low <= measured <= nominal * high


def evaluate(category: str, specs: dict[str, Any], measurements: dict[str, Any]) -> dict[str, str]:
    """Return a pass, fail, or unsupported result without treating invalid input as a pass."""
    try:
        if category == "resistor":
            ok = _within(_number(measurements, "measured_ohm"), _number(specs, "resistance_ohm"), 0.90, 1.10)
            return _result(ok, "within ±10% of marked value" if ok else "outside ±10% of marked value")
        if category == "potentiometer":
            ok = (
                _within(_number(measurements, "measured_ohm"), _number(specs, "resistance_ohm"), 0.80, 1.20)
                and _boolean(measurements, "wiper_sweeps_smoothly")
            )
            return _result(ok, "value and wiper sweep OK" if ok else "value off or wiper not smooth")
        if category == "diode":
            forward_v = _number(measurements, "forward_v")
            ok = 0.15 <= forward_v <= 0.9 and _boolean(measurements, "reverse_open")
            return _result(ok, "normal forward drop, blocks reverse" if ok else "forward drop abnormal or leaks in reverse")
        if category == "led":
            ok = _boolean(measurements, "lights_up")
            return _result(ok, "lights in correct polarity" if ok else "did not light")
        if category == "capacitor":
            ok = _within(_number(measurements, "measured_uf"), _number(specs, "capacitance_uf"), 0.80, 1.50)
            return _result(ok, "capacitance within -20%/+50%" if ok else "capacitance out of range")
        if category == "battery":
            ok = _within(_number(measurements, "measured_v"), _number(specs, "voltage_v"), 0.70, 1.15)
            return _result(ok, "voltage healthy" if ok else "voltage too low/high")
        if category == "button":
            ok = _boolean(measurements, "continuity_when_pressed") and _boolean(measurements, "open_when_released")
            return _result(ok, "switches correctly" if ok else "does not switch correctly")
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"verdict": "fail", "reason": "missing or invalid measurement values"}
    return {"verdict": "unsupported", "reason": "no guided test for this category yet"}


def _result(ok: bool, reason: str) -> dict[str, str]:
    return {"verdict": "pass" if ok else "fail", "reason": reason}
