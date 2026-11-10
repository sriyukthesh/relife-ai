"""Part sourcing for the timeline engine.

Uses the app's Channel3 service when available, otherwise a tiny built-in sample table.
Channel3 does not return shipping times, so every ETA below is SIMULATED (deterministic, 3 to 8 days,
derived from the product id). The UI and README must say so.
"""
import math
import re
import zlib

try:
    from app.services.channel3 import Channel3Error, search_part as _search_part
except ImportError:
    _search_part = None

    class Channel3Error(Exception):
        pass

STOP = {"the", "a", "an", "of", "for", "and", "with", "pcs", "pc", "piece", "pieces", "pack", "x"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def toks(s: str) -> set:
    return {t for t in norm(s).split() if t not in STOP}


def overlap(part: str, title: str) -> float:
    a, b = toks(part), toks(title)
    return len(a & b) / max(1, len(a))


def same_part(a: str, b: str) -> bool:
    ta, tb = toks(a), toks(b)
    return bool(ta) and bool(tb) and (norm(a) == norm(b) or ta <= tb or tb <= ta)


def pack_size(title: str) -> int:
    m = re.search(r"pack of (\d+)", title.lower())
    return max(1, int(m.group(1))) if m else 1


def sim_eta_days(product_id: str, title: str) -> int:
    return 3 + zlib.crc32((product_id or title).encode()) % 6


_SAMPLE = [
    (["7805", "regulator"], [("s-7805", "L7805CV 5V 1.5A Voltage Regulator TO-220 (pack of 5)", 599),
                             ("s-7805b", "LM7805 5V Positive Voltage Regulator TO-220 (pack of 10)", 899)]),
    (["capacitor", "1000uf"], [("s-cap", "1000uF 16V Electrolytic Capacitor (pack of 10)", 699),
                               ("s-capb", "1000uF 25V Radial Electrolytic Capacitor (pack of 5)", 499)]),
    (["diode", "1n4007"], [("s-d", "1N4007 1A 1000V Rectifier Diode (pack of 50)", 599)]),
    (["bridge", "w10m"], [("s-br", "W10M 1A Bridge Rectifier (pack of 10)", 749)]),
    (["resistor"], [("s-r", "1/4W 10k Ohm Metal Film Resistor Assortment (pack of 100)", 599)]),
    (["usb"], [("s-usb", "Micro USB Female Breakout Connector (pack of 10)", 799)]),
    (["transformer"], [("s-tx", "9V 1A Mini Step-Down Transformer", 1299)]),
    (["led"], [("s-led", "5mm LED Assortment Kit (pack of 200)", 699)]),
]


def _sample(query: str) -> list:
    q = query.lower()
    for keys, rows in _SAMPLE:
        if any(k in q for k in keys):
            return [{"product_id": pid, "title": t, "price_cents": c, "merchant": "Sample data (not a live listing)",
                     "url": "", "image": "", "source": "cached_demo"} for pid, t, c in rows]
    return []


_CACHE: dict = {}


def candidates(part_name: str) -> list:
    """Relevant, in-stock options with pack size and simulated ETA, cheapest first."""
    key = norm(part_name)
    if key in _CACHE:
        return _CACHE[key]
    raw = []
    if _search_part is not None:
        try:
            response = _search_part(part_name)
            raw = [
                {
                    "product_id": product.get("product_id"),
                    "title": product["title"],
                    "price_cents": int(round(float(product["price"]) * 100)),
                    "merchant": product.get("merchant") or "",
                    "url": product.get("url") or "",
                    "source": response.get("source", "channel3"),
                }
                for product in response.get("results", [])
                if product.get("title") and product.get("price") is not None
            ]
        except Channel3Error:
            raw = []
    def relevant(rows):
        return [
            {**candidate, "pack_size": pack_size(candidate["title"]),
             "eta_days": sim_eta_days(candidate.get("product_id", ""), candidate["title"])}
            for candidate in rows
            if overlap(part_name, candidate["title"]) >= 0.4
        ]

    out = relevant(raw)
    if not out:
        out = relevant(_sample(part_name))
    out.sort(key=lambda c: c["price_cents"])
    _CACHE[key] = out
    return out


def total_cost(c: dict, units: int) -> int:
    return math.ceil(units / c["pack_size"]) * c["price_cents"]


def clear_cache():
    _CACHE.clear()
