"""Marketplace rules (pure Python).

Principles: suspect or incomplete parts can never be listed, and anything bought
enters the buyer's inventory as source="marketplace", condition="unverified",
even if the seller claimed it was tested: the buyer has not tested it.
"""
from __future__ import annotations

from typing import Any

from .. import catalog
from .project_engine import spec_matches

MAX_PRICE_CENTS = 10_000_000


def listing_problem(
    *, category: str, specs: dict[str, Any], condition: str,
    owned_qty: int, list_qty: int, price_cents: int,
) -> str | None:
    """Return why this item cannot be listed, or None if it can."""
    if condition == catalog.SUSPECT:
        return "Parts marked as suspected damaged cannot be listed."
    missing = catalog.missing_required_specs(category, specs)
    if missing:
        return "Add the missing details before listing: " + ", ".join(missing) + "."
    if list_qty < 1:
        return "Quantity must be at least 1."
    if list_qty > owned_qty:
        return f"You only have {owned_qty} of this part."
    if not (1 <= price_cents <= MAX_PRICE_CENTS):
        return "Price is out of range."
    return None


def buyer_condition(listing_condition: str) -> str:
    """Bought parts always start unverified for the buyer."""
    return catalog.UNVERIFIED


def offers_for_part(
    part: dict[str, Any], listings: list[dict[str, Any]], buyer_id: int
) -> list[dict[str, Any]]:
    """Active listings by other sellers that satisfy a missing part's category + constraints."""
    out = []
    for l in listings:
        if l["status"] != "active" or l["quantity"] <= 0 or l["seller_id"] == buyer_id:
            continue
        if l["condition"] == catalog.SUSPECT or l["category"] != part["category"]:
            continue
        if catalog.missing_required_specs(l["category"], l["specs"]):
            continue
        if spec_matches(l["specs"], part.get("constraints", {})):
            out.append(l)
    return sorted(out, key=lambda l: (l["price_cents"], l["id"]))
