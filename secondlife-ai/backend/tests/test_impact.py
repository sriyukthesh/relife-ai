from datetime import datetime, timedelta, timezone

from app.services import impact

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)  # a Thursday


def ev(days_ago, cat, qty):
    return (NOW - timedelta(days=days_ago), cat, qty)


def test_lower_bound_avoids_double_counting():
    reused = [ev(1, "resistor", 4), ev(2, "led", 2)]
    resold = [ev(1, "resistor", 10)]
    rows = {r["category"]: r for r in impact.category_breakdown(reused, resold)}
    assert rows["resistor"]["grams_low"] == round(10 * impact.grams_for("resistor"), 1)   # max(4, 10)
    assert rows["resistor"]["grams_high"] == round(14 * impact.grams_for("resistor"), 1)  # 4 + 10
    t = impact.totals(reused, resold)
    assert t["parts_reused"] == 6 and t["parts_resold"] == 10
    assert t["diverted_g_low"] <= t["diverted_g_high"]


def test_unknown_category_uses_default_mass():
    t = impact.totals([ev(0, "flux capacitor", 3)], [])
    assert t["diverted_g_low"] == 3 * impact.DEFAULT_GRAMS


def test_weekly_series_has_requested_length_and_buckets_events():
    s = impact.weekly_series([ev(0, "led", 3), ev(8, "led", 2)], [ev(0, "resistor", 5), ev(400, "led", 9)], weeks=12, now=NOW)
    assert len(s) == 12
    assert s[-1]["reused"] == 3 and s[-1]["resold"] == 5   # current week
    assert sum(x["reused"] for x in s) == 5                # the 8-day-old event lands in the previous week
    assert sum(x["resold"] for x in s) == 5                # the 400-day-old event is outside the window
    assert s[0]["week_start"] < s[-1]["week_start"]


def test_negative_quantities_ignored():
    assert impact.totals([ev(0, "led", -5)], [])["parts_reused"] == 0
