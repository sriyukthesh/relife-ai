from timeline import sourcing


def test_channel3_results_are_adapted_to_timeline_price_units(monkeypatch):
    sourcing.clear_cache()
    monkeypatch.setattr(
        sourcing,
        "_search_part",
        lambda _query: {
            "source": "channel3",
            "results": [{
                "product_id": "p1",
                "title": "10k Ohm resistor 1/4 W",
                "price": 2.5,
                "merchant": "shop.example",
                "url": "https://shop.example/p1",
            }],
        },
    )

    candidates = sourcing.candidates("10k resistor")

    assert candidates[0]["price_cents"] == 250
    assert candidates[0]["source"] == "channel3"
    assert candidates[0]["url"] == "https://shop.example/p1"
    sourcing.clear_cache()


def test_unmatched_channel3_results_fall_back_to_labeled_demo_data(monkeypatch):
    sourcing.clear_cache()
    monkeypatch.setattr(
        sourcing,
        "_search_part",
        lambda _query: {
            "source": "channel3",
            "results": [{"title": "Arduino development board", "price": 4.0}],
        },
    )

    candidates = sourcing.candidates("1000uF 16V electrolytic capacitor")

    assert candidates
    assert all(candidate["source"] == "cached_demo" for candidate in candidates)
    sourcing.clear_cache()
