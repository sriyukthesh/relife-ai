"""Listing suggestions for the marketplace (pure Python).

The price is a starting point, decided by code:
  1. median of at least two comparable active listings, if they exist
  2. otherwise a typical hobby-shop price for the category, discounted for untested parts.
Base prices are rough placeholders in paise (1/100 rupee), not market data.
"""
from __future__ import annotations

from statistics import median
from typing import Any

from .. import catalog

BASE_PRICE_PAISE: dict[str, int] = {
    "resistor": 200, "potentiometer": 2500, "capacitor": 800, "led": 300,
    "transistor": 600, "diode": 200, "ic": 3000, "battery": 4000, "button": 500,
    "buzzer": 3000, "ldr": 1000, "microcontroller": 35000, "other": 2000,
}
UNTESTED_FACTOR = 0.8
STEP = 50  # round to the nearest 50 paise
MIN_PRICE = 50


def _round(paise: float) -> int:
    return max(MIN_PRICE, int(round(paise / STEP)) * STEP)


def suggest_price(category: str, condition: str, peer_prices: list[int]) -> dict[str, Any]:
    peers = sorted(p for p in peer_prices if p > 0)
    if len(peers) >= 2:
        mid = _round(median(peers))
        return {
            "price_cents": mid, "low_cents": _round(peers[0]), "high_cents": _round(peers[-1]),
            "basis": f"Median of {len(peers)} similar listings on the marketplace.",
        }
    base = BASE_PRICE_PAISE.get(category, BASE_PRICE_PAISE["other"])
    factor = 1.0 if condition == catalog.TESTED_OK else UNTESTED_FACTOR
    price = _round(base * factor)
    return {
        "price_cents": price, "low_cents": _round(price * 0.6), "high_cents": _round(price * 1.5),
        "basis": "Rough hobby-shop estimate; no similar listings to compare yet."
        + ("" if condition == catalog.TESTED_OK else " Reduced because the part is untested."),
    }


def comparable(a_category: str, a_specs: dict[str, Any], b_category: str, b_specs: dict[str, Any]) -> bool:
    """Same category and identical specs (after normalisation)."""
    return a_category == b_category and catalog.normalize_specs(a_category, a_specs) == catalog.normalize_specs(
        b_category, b_specs
    )


def suggest_title(label: str, specs: dict[str, Any]) -> str:
    """Keep the user's confirmed label; it already carries the key details."""
    return (label or "Electronic component").strip()[:120]
