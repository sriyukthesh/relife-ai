"""Deterministic project feasibility engine.

No database in here: pure Python over plain data, so every decision is
explainable and unit-testable. Muse Spark only *explains* these results (Phase 3).

A project requirement looks like:
  {"label": "...", "category": "resistor", "qty": 2,
   "specs": {"resistance_ohm": {"min": 470, "max": 2200}}}
Spec rules: scalar = equals, list = one of, {"min":..,"max":..} = numeric range.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import catalog


@dataclass(frozen=True)
class StockItem:
    id: int
    label: str
    category: str
    specs: dict[str, Any]
    quantity: int
    condition: str = catalog.UNVERIFIED


@dataclass
class Allocation:
    item_id: int
    label: str
    quantity: int
    condition: str


@dataclass
class RequirementResult:
    index: int
    label: str
    category: str
    needed: int
    allocated: list[Allocation]
    missing: int
    status: str  # ok | partial | missing
    constraints: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class MissingPart:
    label: str
    category: str
    quantity: int
    constraints: dict[str, Any]


@dataclass
class ProjectMatch:
    project_id: int
    slug: str
    title: str
    difficulty: int
    estimated_minutes: int
    description: str
    can_build: bool
    coverage: float
    requirements: list[RequirementResult]
    missing_parts: list[MissingPart]
    warnings: list[str]


def _norm(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return str(value).strip().lower()


def spec_matches(specs: dict[str, Any], constraints: dict[str, Any]) -> bool:
    """True only if every constrained spec is present and satisfies its rule."""
    for key, rule in (constraints or {}).items():
        value = (specs or {}).get(key)
        if catalog.is_blank(value):
            return False
        if isinstance(rule, dict):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            if "min" in rule and value < rule["min"]:
                return False
            if "max" in rule and value > rule["max"]:
                return False
        elif isinstance(rule, list):
            if _norm(value) not in {_norm(r) for r in rule}:
                return False
        elif _norm(value) != _norm(rule):
            return False
    return True


def split_usable(items: list[StockItem]) -> tuple[list[StockItem], list[dict[str, Any]]]:
    """Separate parts the engine may trust from those it must not use (with reasons)."""
    usable: list[StockItem] = []
    excluded: list[dict[str, Any]] = []
    for item in items:
        missing = catalog.missing_required_specs(item.category, item.specs)
        if item.quantity <= 0:
            reason = "Quantity is zero."
        elif item.condition == catalog.SUSPECT:
            reason = "Marked as suspected damaged. Test it before using it."
        elif missing:
            reason = "Missing required details: " + ", ".join(missing) + "."
        else:
            usable.append(item)
            continue
        excluded.append({"id": item.id, "label": item.label, "reason": reason})
    return usable, excluded


def evaluate_project(project: dict[str, Any], stock: list[StockItem]) -> ProjectMatch:
    reqs: list[dict[str, Any]] = project["requirements"]
    remaining = {s.id: s.quantity for s in stock}

    candidates = [
        [s for s in stock if s.category == r["category"] and spec_matches(s.specs, r.get("specs", {}))]
        for r in reqs
    ]
    # Fill the most constrained requirements first so broad ones don't steal their parts.
    order = sorted(range(len(reqs)), key=lambda i: (len(candidates[i]), i))

    results: dict[int, RequirementResult] = {}
    for i in order:
        req = reqs[i]
        needed = int(req.get("qty", 1))
        left = needed
        allocated: list[Allocation] = []
        warnings: list[str] = []
        # Prefer parts the user has actually tested.
        for item in sorted(candidates[i], key=lambda s: (s.condition != catalog.TESTED_OK, s.id)):
            if left <= 0:
                break
            take = min(left, remaining[item.id])
            if take <= 0:
                continue
            remaining[item.id] -= take
            left -= take
            allocated.append(Allocation(item.id, item.label, take, item.condition))
            if item.condition != catalog.TESTED_OK:
                warnings.append(f"Test '{item.label}' before using it.")
        got = needed - left
        status = "ok" if left == 0 else ("partial" if got > 0 else "missing")
        results[i] = RequirementResult(
            index=i, label=req["label"], category=req["category"], needed=needed,
            allocated=allocated, missing=left, status=status,
            constraints=req.get("specs", {}), warnings=warnings,
        )

    ordered = [results[i] for i in range(len(reqs))]
    total_needed = sum(r.needed for r in ordered) or 1
    total_got = sum(r.needed - r.missing for r in ordered)
    missing_parts = [
        MissingPart(r.label, r.category, r.missing, r.constraints) for r in ordered if r.missing > 0
    ]
    warnings: list[str] = []
    if project.get("safety_note"):
        warnings.append(project["safety_note"])

    return ProjectMatch(
        project_id=project["id"], slug=project["slug"], title=project["title"],
        difficulty=project["difficulty"], estimated_minutes=project["estimated_minutes"],
        description=project["description"],
        can_build=all(r.missing == 0 for r in ordered),
        coverage=round(total_got / total_needed, 3),
        requirements=ordered, missing_parts=missing_parts, warnings=warnings,
    )


def recommend(
    projects: list[dict[str, Any]], items: list[StockItem]
) -> tuple[list[ProjectMatch], list[dict[str, Any]]]:
    """Rank projects: buildable first, then by how close the user is, then easiest."""
    usable, excluded = split_usable(items)
    matches = [evaluate_project(p, usable) for p in projects]
    matches.sort(key=lambda m: (not m.can_build, -m.coverage, m.difficulty, m.title))
    return matches, excluded
