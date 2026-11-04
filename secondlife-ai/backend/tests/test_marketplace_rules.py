from app.services import marketplace_rules as r


def _l(**kw):
    base = {"id": 1, "seller_id": 2, "category": "potentiometer", "specs": {"resistance_ohm": 10000},
            "quantity": 2, "price_cents": 100, "condition": "unverified", "status": "active"}
    base.update(kw)
    return base


def test_cannot_list_suspect_or_incomplete():
    kw = dict(owned_qty=3, list_qty=1, price_cents=100)
    assert r.listing_problem(category="resistor", specs={"resistance_ohm": 220}, condition="suspect_damaged", **kw)
    assert r.listing_problem(category="resistor", specs={}, condition="unverified", **kw)
    assert r.listing_problem(category="resistor", specs={"resistance_ohm": 220}, condition="unverified", **kw) is None


def test_cannot_list_more_than_owned_or_bad_price():
    base = dict(category="led", specs={"color": "red"}, condition="unverified")
    assert r.listing_problem(owned_qty=2, list_qty=3, price_cents=100, **base)
    assert r.listing_problem(owned_qty=2, list_qty=1, price_cents=0, **base)


def test_buyer_always_gets_unverified():
    assert r.buyer_condition("tested_ok") == "unverified"


def test_offers_reuse_spec_matching_and_skip_own_and_inactive():
    part = {"category": "potentiometer", "constraints": {"resistance_ohm": {"min": 1000, "max": 10000}}}
    listings = [
        _l(id=1, price_cents=300),
        _l(id=2, price_cents=100, specs={"resistance_ohm": 500}),    # out of range
        _l(id=3, price_cents=50, seller_id=9),                       # own listing (buyer is 9)
        _l(id=4, price_cents=70, status="sold"),
        _l(id=5, price_cents=200, condition="suspect_damaged"),
        _l(id=6, price_cents=90),
    ]
    assert [l["id"] for l in r.offers_for_part(part, listings, buyer_id=9)] == [6, 1]
