from datetime import datetime, timezone

from app.services import checkout as co


def L(**o):
    base = {"id": 1, "seller_id": 2, "category": "led", "label": "Red LED", "specs": {"color": "red"},
            "quantity": 5, "price_cents": 300, "condition": "unverified", "status": "active"}
    base.update(o)
    return base


def test_merge_duplicate_lines():
    assert co.merge_lines([(1, 2), (1, 3), (2, 1)]) == {1: 5, 2: 1}


def test_normal_line_priced_by_code():
    p = co.price_line(L(), 3, buyer_id=9)
    assert p["issue"] is None and p["quantity"] == 3 and p["line_cents"] == 900


def test_over_request_is_flagged_and_capped():
    p = co.price_line(L(quantity=2), 5, buyer_id=9)
    assert p["issue"] == "Only 2 left." and p["quantity"] == 2


def test_own_sold_and_missing_listings_cannot_be_bought():
    assert co.price_line(L(seller_id=9), 1, buyer_id=9)["issue"] == "This is your own listing."
    assert co.price_line(L(status="sold"), 1, buyer_id=9)["issue"] == "No longer available."
    assert co.price_line(L(quantity=0), 1, buyer_id=9)["issue"] == "No longer available."
    assert co.price_line({"id": 7, "status": "missing"}, 1, buyer_id=9)["issue"] == "No longer available."


def test_delivery_fee_threshold():
    assert co.delivery_fee(0) == 0
    assert co.delivery_fee(co.FREE_DELIVERY_FROM_CENTS - 1) == co.DELIVERY_FEE_CENTS
    assert co.delivery_fee(co.FREE_DELIVERY_FROM_CENTS) == 0


def test_totals_ok_only_when_every_line_is_clean():
    good = co.price_line(L(), 2, 9)
    t = co.totals([good])
    assert t["ok"] and t["subtotal_cents"] == 600 and t["total_cents"] == 600 + co.DELIVERY_FEE_CENTS
    bad = co.price_line(L(id=2, quantity=1), 4, 9)
    t2 = co.totals([good, bad])
    assert not t2["ok"] and t2["subtotal_cents"] == 600   # a flagged line is not charged
    assert not co.totals([])["ok"]


def test_reference_format_and_uniqueness():
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    a, b = co.new_reference(now), co.new_reference(now)
    assert a.startswith("SL-20261030-") and len(a) == len("SL-20261030-") + 8 and a != b
