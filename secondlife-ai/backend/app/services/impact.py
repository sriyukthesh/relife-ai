"""Impact maths for the dashboard (pure Python: no DB).

Everything here is an ESTIMATE built from counted events:
  reused  = parts required by builds the user marked as finished
  resold  = parts sold through the marketplace
A part that is sold and then used in a build can appear in both counts, so the
headline "diverted" figure uses the conservative lower bound (per category, the larger
of the two counts); the upper bound (sum) is reported separately.

Masses are approximate typical values for hobby parts, NOT measurements. Replace
them with weighed values if you want to quote exact figures.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

GRAMS_PER_PART: dict[str, float] = {
    "resistor": 0.25,
    "potentiometer": 3.0,
    "capacitor": 1.5,
    "led": 0.3,
    "transistor": 0.5,
    "diode": 0.3,
    "ic": 1.0,
    "battery": 30.0,
    "button": 1.5,
    "buzzer": 2.5,
    "ldr": 0.4,
    "microcontroller": 8.0,
    "other": 2.0,
}
DEFAULT_GRAMS = 2.0

# (when, category, quantity)
Event = tuple[datetime, str, int]


def grams_for(category: str) -> float:
    return GRAMS_PER_PART.get(category, DEFAULT_GRAMS)


def _count_by_category(events: Iterable[Event]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for _, cat, qty in events:
        out[cat] += max(0, int(qty))
    return dict(out)


def category_breakdown(reused: Iterable[Event], resold: Iterable[Event]) -> list[dict]:
    """Per-category parts and diverted grams (lower and upper bound), biggest first."""
    r, s = _count_by_category(reused), _count_by_category(resold)
    rows = []
    for cat in sorted(set(r) | set(s)):
        low_parts = max(r.get(cat, 0), s.get(cat, 0))
        high_parts = r.get(cat, 0) + s.get(cat, 0)
        g = grams_for(cat)
        rows.append({
            "category": cat,
            "reused": r.get(cat, 0),
            "resold": s.get(cat, 0),
            "grams_low": round(low_parts * g, 1),
            "grams_high": round(high_parts * g, 1),
        })
    rows.sort(key=lambda x: (-x["grams_low"], x["category"]))
    return rows


def totals(reused: Iterable[Event], resold: Iterable[Event]) -> dict:
    reused, resold = list(reused), list(resold)
    rows = category_breakdown(reused, resold)
    return {
        "parts_reused": sum(x["reused"] for x in rows),
        "parts_resold": sum(x["resold"] for x in rows),
        "diverted_g_low": round(sum(x["grams_low"] for x in rows), 1),
        "diverted_g_high": round(sum(x["grams_high"] for x in rows), 1),
    }


def week_start(d: datetime | date) -> date:
    day = d.date() if isinstance(d, datetime) else d
    return day - timedelta(days=day.weekday())


def weekly_series(
    reused: Iterable[Event], resold: Iterable[Event], *, weeks: int = 12, now: datetime | None = None
) -> list[dict]:
    """Oldest -> newest weekly buckets (Monday start) ending with the current week."""
    now = now or datetime.now(timezone.utc)
    this_week = week_start(now)
    starts = [this_week - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    idx = {s: i for i, s in enumerate(starts)}
    series = [{"week_start": s.isoformat(), "reused": 0, "resold": 0} for s in starts]
    for key, events in (("reused", reused), ("resold", resold)):
        for when, _cat, qty in events:
            i = idx.get(week_start(when))
            if i is not None:
                series[i][key] += max(0, int(qty))
    return series
