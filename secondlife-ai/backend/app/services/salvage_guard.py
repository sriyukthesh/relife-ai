"""Deterministic hazard check that runs before any teardown model call."""
import re

BLOCK = {
    r"microwave": "Microwave ovens hold lethal high-voltage capacitors that can stay charged.",
    r"\bcrt\b|picture tube|flyback": "CRT and flyback circuits hold lethal charge.",
    r"air.?condition|\bac unit\b|compressor": "Air conditioners contain pressurised refrigerant and mains-voltage parts.",
    r"\bups\b|inverter|lead.?acid": "UPS/inverter units contain high-energy batteries and mains circuits.",
    r"neon sign|transformer sign": "Neon sign transformers output lethal voltage.",
}
WARN = {
    r"camera flash|disposable camera|flash unit": "Flash capacitors can hold high voltage. Do not open or harvest them.",
    r"adapter|charger|smps|power supply|psu|mains": "Mains-side parts can stay charged. Do not open these devices.",
    r"li-?ion|lithium|lipo|power ?bank|phone battery|laptop battery|vape": "Lithium cells can ignite if punctured or shorted. Do not remove or desolder them.",
    r"swollen|bulging|leak|burnt|burned|smoke": "Damaged or burnt parts are unsafe. Do not harvest them.",
}
ALWAYS = [
    "Unplug external power. Do not open battery packs or touch mains-side parts.",
    "Wear eye protection when cutting or desoldering.",
    "Work in a ventilated area; solder fumes are harmful.",
    "Never harvest parts that are swollen, leaking, burnt or corroded.",
    "Test every harvested part before using it. It is unverified until you measure it.",
]


def assess(text: str) -> dict:
    t = (text or "").lower()
    blocked = [msg for pat, msg in BLOCK.items() if re.search(pat, t)]
    warnings = [msg for pat, msg in WARN.items() if re.search(pat, t)]
    return {
        "blocked": bool(blocked),
        "reasons": blocked,
        "warnings": warnings,
        "safety_steps": ALWAYS,
    }
