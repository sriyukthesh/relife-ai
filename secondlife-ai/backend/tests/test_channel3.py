from types import SimpleNamespace

import pytest

from app.services import channel3


def test_parse_filters_unavailable_and_non_usd_offers_and_sorts():
    products = [
        {
            "id": "p2",
            "title": "More expensive",
            "offers": [{
                "availability": "InStock",
                "price": {"price": "4.50", "currency": "USD"},
                "url": "https://shop.example/p2",
                "domain": "shop.example",
            }],
        },
        {
            "id": "p1",
            "title": "Lowest price",
            "images": [{"cleaned_url": "https://img.example/p1.png"}],
            "offers": [
                {"availability": "OutOfStock", "price": {"price": 0.5}, "url": "https://shop.example/out"},
                {"availability": "InStock", "price": {"price": 1.25, "currency": "USD"},
                 "url": "https://shop.example/p1", "domain": "shop.example"},
                {"availability": "InStock", "price": {"price": 0.1, "currency": "EUR"},
                 "url": "https://shop.example/eur"},
            ],
        },
        {
            "id": "bad-link",
            "offers": [{
                "availability": "InStock",
                "price": {"price": 0.25, "currency": "USD"},
                "url": "javascript:alert(1)",
            }],
        },
    ]

    results = channel3._parse(products)

    assert [item["product_id"] for item in results] == ["p1", "p2"]
    assert results[0]["price"] == 1.25
    assert results[0]["image"] == "https://img.example/p1.png"


def test_plan_uses_inventory_missing_parts_and_does_not_exceed_budget(monkeypatch):
    searched = []

    def fake_search(query):
        searched.append(query)
        return {
            "source": "channel3",
            "results": [
                {"product_id": "p1", "title": "Part", "price": 3.25, "url": "https://shop.example/p1"},
            ],
        }

    monkeypatch.setattr(channel3, "search_part", fake_search)
    plan = channel3.plan_purchase([
        {"label": "10k resistor", "quantity": 2, "constraints": {"resistance_ohm": {"min": 9000, "max": 11000}}},
        {"label": "potentiometer", "quantity": 1, "constraints": {}},
    ], 6.50)

    assert len(plan["cart"]) == 1
    assert plan["cart"][0]["part"] == "10k resistor"
    assert plan["total_usd"] == 6.50
    assert plan["skipped_over_budget"] == [{"part": "potentiometer", "qty": 1, "cost": 3.25}]
    assert "9000 to 11000" in searched[0]


def test_search_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(channel3, "get_settings", lambda: SimpleNamespace(channel3_api_key=""))
    with pytest.raises(channel3.Channel3Error) as error:
        channel3.search_part("resistor")
    assert error.value.status_code == 503


def test_search_uses_api_key_and_caches_success(monkeypatch):
    channel3._MEM.clear()
    monkeypatch.setattr(channel3, "get_settings", lambda: SimpleNamespace(channel3_api_key="test-key"))
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"products": [{
                "id": "p1",
                "title": "Resistor",
                "offers": [{
                    "availability": "InStock",
                    "price": {"price": 0.25, "currency": "USD"},
                    "url": "https://shop.example/p1",
                }],
            }]}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(channel3.httpx, "post", fake_post)
    first = channel3.search_part("resistor")
    second = channel3.search_part("resistor")

    assert len(calls) == 1
    assert calls[0][1]["headers"]["x-api-key"] == "test-key"
    assert first["source"] == "channel3"
    assert second["source"] == "cache"
    channel3._MEM.clear()
