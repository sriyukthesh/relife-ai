"""Deterministic component substitution helpers."""
from itertools import combinations_with_replacement
from math import floor, isfinite, log10

E24 = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6,
    3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
]


def next_e24_up(ohms: float) -> float:
    """Return the smallest standard E24 value greater than or equal to ohms."""
    if not isfinite(ohms) or ohms <= 0:
        raise ValueError("resistance must be a positive finite value")
    decade = 10 ** floor(log10(ohms))
    for multiplier in (decade, decade * 10):
        for base in E24:
            candidate = base * multiplier
            if candidate >= ohms:
                return round(candidate, 6)
    raise ValueError("resistance is outside the supported numeric range")


def suggest_resistor(
    target_ohm: float,
    owned: list[dict],
    tolerance: float = 0.10,
    limit: int = 5,
) -> list[dict]:
    """Find single, series, and parallel combinations from confirmed user stock."""
    if not isfinite(target_ohm) or target_ohm <= 0:
        raise ValueError("target resistance must be a positive finite value")
    if not isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise ValueError("tolerance must be between 0 and 1")
    if limit < 1:
        raise ValueError("limit must be positive")

    stock: dict[float, int] = {}
    for item in owned:
        try:
            value = float(item["ohm"])
            quantity = int(item["qty"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if isfinite(value) and value > 0 and quantity > 0:
            stock[value] = stock.get(value, 0) + quantity
    values = sorted(stock)
    options: list[dict] = []

    def add(kind: str, parts: list[float], total: float, text: str) -> None:
        error = (total - target_ohm) / target_ohm
        if abs(error) <= tolerance:
            options.append({
                "kind": kind,
                "parts": parts,
                "result_ohm": round(total, 2),
                "error_pct": round(error * 100, 2),
                "how": text,
            })

    for value in values:
        add("single", [value], value, f"Use one {value:g} ohm resistor")
    for first, second in combinations_with_replacement(values, 2):
        if first == second and stock[first] < 2:
            continue
        add("series", [first, second], first + second,
            f"Put {first:g} ohm and {second:g} ohm in series")
        add("parallel", [first, second], first * second / (first + second),
            f"Put {first:g} ohm and {second:g} ohm in parallel")
    order = {"single": 0, "series": 1, "parallel": 1}
    options.sort(key=lambda option: (abs(option["error_pct"]), order[option["kind"]]))
    return options[:limit]


def led_resistor(supply_v: float, led_vf: float, current_ma: float = 10.0) -> dict:
    """Calculate an LED resistor and round up so calculated current is not exceeded."""
    if not all(isfinite(value) for value in (supply_v, led_vf, current_ma)):
        raise ValueError("voltages and current must be finite values")
    if supply_v <= led_vf:
        raise ValueError("Supply voltage must exceed LED forward voltage")
    if not 1 <= current_ma <= 30:
        raise ValueError("LED current should be between 1 and 30 mA")
    exact = (supply_v - led_vf) / (current_ma / 1000)
    chosen = next_e24_up(exact)
    actual_ma = (supply_v - led_vf) / chosen * 1000
    power_mw = ((supply_v - led_vf) ** 2 / chosen) * 1000
    watts_rating = "1/4 W is fine" if power_mw < 125 else "use a 1/2 W or larger resistor"
    return {
        "exact_ohm": round(exact, 1),
        "chosen_ohm": chosen,
        "actual_current_ma": round(actual_ma, 2),
        "resistor_power_mw": round(power_mw, 1),
        "note": watts_rating,
    }


def can_substitute_voltage(required_v: float, owned_v: float) -> bool:
    """A higher capacitor voltage rating alone does not establish full compatibility."""
    return isfinite(required_v) and isfinite(owned_v) and owned_v >= required_v
