"""Cart pricing and checkout rules for the marketplace (pure Python: no DB).

Code, not the client, decides every price, quantity and fee. The delivery fee and the free-delivery
threshold below are made-up demo values, not real rates. No payment details are ever handled.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Iterable

DELIVERY_FEE_CENTS = 4000            # ₹40 demo delivery fee
FREE_DELIVERY_FROM_CENTS = 30000     # free from ₹300
MAX_LINES = 30

METHOD_LABELS = {"upi": "UPI", "card": "Credit / debit card", "netbanking": "Net banking"}


def merge_lines(lines: Iterable[tuple[int, int]]) -> dict[int, int]:
    """Combine duplicate listing ids so one listing is priced and locked once."""
    out: dict[int, int] = {}
    for listing_id, qty in lines:
        out[listing_id] = out.get(listing_id, 0) + max(0, int(qty))
    return out


def price_line(listing: dict[str, Any] | None, requested: int, buyer_id: int, seller_name: str = "Seller") -> dict[str, Any]:
    """Price one cart line against the CURRENT listing. `issue` is set when it cannot be bought as asked."""
    if listing is None or listing.get("status") != "active" or listing.get("quantity", 0) <= 0:
        return {
            "listing_id": (listing or {}).get("id", 0), "label": (listing or {}).get("label", "Unavailable item"),
            "category": (listing or {}).get("category", "other"), "specs": (listing or {}).get("specs", {}),
            "condition": (listing or {}).get("condition", "unverified"), "seller_name": seller_name,
            "unit_cents": (listing or {}).get("price_cents", 0), "quantity": 0, "quantity_available": 0,
            "line_cents": 0, "issue": "No longer available.",
        }
    available = int(listing["quantity"])
    qty = min(requested, available)
    issue = None
    if listing["seller_id"] == buyer_id:
        issue, qty = "This is your own listing.", 0
    elif requested > available:
        issue = f"Only {available} left."
    unit = int(listing["price_cents"])
    return {
        "listing_id": listing["id"], "label": listing["label"], "category": listing["category"],
        "specs": listing["specs"], "condition": listing["condition"], "seller_name": seller_name,
        "unit_cents": unit, "quantity": qty, "quantity_available": available,
        "line_cents": unit * qty, "issue": issue,
    }


def delivery_fee(subtotal_cents: int) -> int:
    if subtotal_cents <= 0 or subtotal_cents >= FREE_DELIVERY_FROM_CENTS:
        return 0
    return DELIVERY_FEE_CENTS


def totals(priced: list[dict[str, Any]]) -> dict[str, Any]:
    subtotal = sum(l["line_cents"] for l in priced if not l["issue"])
    fee = delivery_fee(subtotal)
    return {
        "subtotal_cents": subtotal, "delivery_cents": fee, "total_cents": subtotal + fee,
        "free_delivery_from_cents": FREE_DELIVERY_FROM_CENTS,
        "ok": bool(priced) and all(not l["issue"] for l in priced),
    }


def new_reference(now: datetime) -> str:
    return f"SL-{now:%Y%m%d}-{secrets.token_hex(4).upper()}"
