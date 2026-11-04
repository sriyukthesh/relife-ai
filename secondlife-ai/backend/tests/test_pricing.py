from app.services import pricing


def test_peer_median_used_when_two_or_more():
    p = pricing.suggest_price("resistor", "unverified", [200, 400, 300])
    assert p["price_cents"] == 300 and "3 similar" in p["basis"]
    assert p["low_cents"] <= p["price_cents"] <= p["high_cents"]


def test_fallback_discounts_untested():
    tested = pricing.suggest_price("ic", "tested_ok", [])
    untested = pricing.suggest_price("ic", "unverified", [])
    assert untested["price_cents"] < tested["price_cents"]
    assert "untested" in untested["basis"]


def test_price_never_below_minimum_and_rounded():
    p = pricing.suggest_price("resistor", "unverified", [])
    assert p["price_cents"] >= pricing.MIN_PRICE and p["price_cents"] % pricing.STEP == 0


def test_comparable_requires_same_category_and_specs():
    assert pricing.comparable("led", {"color": "Red"}, "led", {"color": "red"})
    assert not pricing.comparable("led", {"color": "red"}, "led", {"color": "green"})
    assert not pricing.comparable("led", {"color": "red"}, "resistor", {"color": "red"})
