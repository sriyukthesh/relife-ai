"""Server-side Channel3 search and budget-aware missing-parts planning."""
from __future__ import annotations

import logging
import math
import re
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

API_URL = "https://api.trychannel3.com/v1/search"
SEARCH_HINT = "electronic component"
MEM_TTL = 600
_MEM: dict[str, tuple[float, list[dict[str, Any]]]] = {}


class Channel3Error(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _web_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def _parse(products: Any) -> list[dict[str, Any]]:
    results = []
    for product in products if isinstance(products, list) else []:
        if not isinstance(product, dict):
            continue
        offers = []
        for offer in product.get("offers") or []:
            if not isinstance(offer, dict) or offer.get("availability") != "InStock":
                continue
            price = offer.get("price")
            if not isinstance(price, dict) or price.get("currency", "USD") != "USD":
                continue
            raw_amount = price.get("price")
            if isinstance(raw_amount, bool):
                continue
            try:
                amount = float(raw_amount)
            except (TypeError, ValueError):
                continue
            url = _web_url(offer.get("url"))
            if not math.isfinite(amount) or amount < 0 or amount > 1_000_000 or not url:
                continue
            amount = float(Decimal(str(amount)).quantize(Decimal("0.01")))
            offers.append((amount, offer, url))
        if not offers:
            continue

        amount, offer, url = min(offers, key=lambda row: row[0])
        images = product.get("images") or []
        image = None
        if isinstance(images, list) and images and isinstance(images[0], dict):
            image = _web_url(images[0].get("cleaned_url")) or _web_url(images[0].get("url"))
        results.append({
            "product_id": product.get("id") if isinstance(product.get("id"), (str, int)) else None,
            "title": str(product.get("title") or "")[:120],
            "price": amount,
            "currency": "USD",
            "merchant": offer.get("domain") if isinstance(offer.get("domain"), str) else None,
            "url": url,
            "condition": offer.get("condition") if isinstance(offer.get("condition"), str) else None,
            "image": image,
        })
    return sorted(results, key=lambda item: item["price"])


def search_part(query: str) -> dict[str, Any]:
    """Search Channel3, reusing only recent successful results for the same query."""
    key = _norm(query)
    hit = _MEM.get(key)
    if hit and time.time() - hit[0] < MEM_TTL:
        return {"source": "cache", "results": hit[1][:5]}

    api_key = get_settings().channel3_api_key
    if not api_key:
        raise Channel3Error("Channel3 is not configured. Add CHANNEL3_API_KEY to the backend environment.", 503)
    try:
        response = httpx.post(
            API_URL,
            json={"query": f"{query} {SEARCH_HINT}"},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        log.warning("Channel3 search request failed: %s", exc)
        raise Channel3Error("Channel3 search is temporarily unavailable.") from exc
    except ValueError as exc:
        raise Channel3Error("Channel3 returned an invalid response.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        raise Channel3Error("Channel3 returned an invalid product list.")
    results = _parse(payload.get("products"))
    if results:
        _MEM[key] = (time.time(), results)
    return {"source": "channel3", "results": results[:5]}


def _query_for_part(part: dict[str, Any]) -> str:
    details = []
    for key, rule in (part.get("constraints") or {}).items():
        if isinstance(rule, dict):
            value = " to ".join(str(rule[k]) for k in ("min", "max") if k in rule)
        elif isinstance(rule, list):
            value = " or ".join(map(str, rule))
        else:
            value = str(rule)
        if value:
            details.append(f"{key} {value}")
    return " ".join([str(part["label"]), *details])


def plan_purchase(missing: list[dict[str, Any]], budget_usd: float) -> dict[str, Any]:
    """Pick the lowest-priced in-stock USD offer per missing part without exceeding budget."""
    remaining = Decimal(str(budget_usd))
    spent = Decimal("0")
    cart = []
    unavailable = []
    over_budget = []

    for part in missing:
        name = str(part["label"])
        quantity = max(1, int(part.get("quantity", 1)))
        found = search_part(_query_for_part(part))
        if not found["results"]:
            unavailable.append({"part": name, "qty": quantity})
            continue

        choice = found["results"][0]
        line_total = (Decimal(str(choice["price"])) * quantity).quantize(Decimal("0.01"))
        if spent + line_total > remaining:
            over_budget.append({"part": name, "qty": quantity, "cost": float(line_total)})
            continue

        spent += line_total
        cart.append({
            **choice,
            "part": name,
            "qty": quantity,
            "line_total": float(line_total),
            "data_source": found["source"],
        })

    return {
        "budget_usd": float(remaining),
        "cart": cart,
        "total_usd": float(spent),
        "covered_by_salvage": [],
        "unavailable": unavailable,
        "skipped_over_budget": over_budget,
    }
