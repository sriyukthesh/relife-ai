"""Accuracy evaluation of the photo-identification pipeline (pure Python, no network).

Ground-truth CSV columns (blank spec = not graded for that photo):
  filename,category,label,resistance_ohm,capacitance_uf,voltage_v,color,polarity,buzzer_type,part_number,tags
Several rows with the same filename = several components in one photo.
`tags` is free text such as "hard" or "blurry"; the report breaks results down by tag.

Headline honesty metrics:
  category_accuracy            ground-truth parts whose category the AI got right
  fully_correct_rate           category AND every graded spec right
  confident_wrong_rate         share of proposals that were wrong yet NOT flagged for review
                               (the dangerous case; the user could confirm without a second look)
  auto_accept_precision        among proposals NOT flagged for review, how many were fully correct
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import catalog

SPEC_KEYS = ["resistance_ohm", "capacitance_uf", "voltage_v", "color", "polarity", "buzzer_type", "part_number"]
NUMERIC = {"resistance_ohm", "capacitance_uf", "voltage_v"}
REL_TOL = 0.01


@dataclass
class GroundTruth:
    filename: str
    category: str
    label: str
    specs: dict[str, Any]
    tags: list[str] = field(default_factory=list)


def load_ground_truth(path: Path) -> dict[str, list[GroundTruth]]:
    out: dict[str, list[GroundTruth]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            fn = (row.get("filename") or "").strip()
            cat = (row.get("category") or "").strip().lower()
            if not fn or not cat:
                continue
            specs: dict[str, Any] = {}
            for k in SPEC_KEYS:
                v = (row.get(k) or "").strip()
                if not v:
                    continue
                specs[k] = float(v) if k in NUMERIC else v
            specs = catalog.normalize_specs(cat, specs)
            tags = [t.strip().lower() for t in (row.get("tags") or "").split(";") if t.strip()]
            out[fn].append(GroundTruth(fn, cat, (row.get("label") or "").strip(), specs, tags))
    return dict(out)


def _eq(key: str, truth: Any, pred: Any) -> bool:
    if pred is None:
        return False
    if key in NUMERIC:
        try:
            t, p = float(truth), float(pred)
        except (TypeError, ValueError):
            return False
        return abs(t - p) <= REL_TOL * max(abs(t), 1e-9)
    return str(truth).strip().lower() == str(pred).strip().lower()


def specs_correct(truth: dict[str, Any], pred: dict[str, Any]) -> bool:
    """Every ground-truth spec must be present and equal in the prediction."""
    return all(_eq(k, v, (pred or {}).get(k)) for k, v in truth.items())


def _spec_hits(truth: dict[str, Any], pred: dict[str, Any]) -> int:
    return sum(_eq(k, v, (pred or {}).get(k)) for k, v in truth.items())


@dataclass
class ItemScore:
    filename: str
    category: str
    tags: list[str]
    found: bool            # a proposal with the right category exists
    fully_correct: bool    # right category and all graded specs right
    flagged: bool | None   # needs_review of the matched proposal (None if not found)
    confidence: float | None


@dataclass
class PhotoScore:
    filename: str
    items: list[ItemScore]
    extra_proposals: int
    proposals: int
    confident_wrong: int   # proposals that were wrong (or unmatched) and not flagged for review
    unflagged: int
    unflagged_correct: int


def score_photo(filename: str, truths: list[GroundTruth], proposals: list[dict[str, Any]]) -> PhotoScore:
    """Greedy match each ground-truth part to the best same-category proposal."""
    free = list(range(len(proposals)))
    matched: dict[int, tuple[GroundTruth, bool]] = {}  # proposal index -> (truth, fully_correct)
    items: list[ItemScore] = []

    # Match specs-rich truths first so simple ones don't steal their proposals.
    for gt in sorted(truths, key=lambda g: -len(g.specs)):
        best, best_key = None, (-1, -1.0)
        for i in free:
            p = proposals[i]
            if p.get("category") != gt.category:
                continue
            key = (_spec_hits(gt.specs, p.get("specs") or {}), float(p.get("ai_confidence") or 0))
            if key > best_key:
                best, best_key = i, key
        if best is None:
            items.append(ItemScore(filename, gt.category, gt.tags, False, False, None, None))
            continue
        free.remove(best)
        p = proposals[best]
        ok = specs_correct(gt.specs, p.get("specs") or {})
        matched[best] = (gt, ok)
        items.append(ItemScore(filename, gt.category, gt.tags, True, ok,
                               bool(p.get("needs_review")), float(p.get("ai_confidence") or 0)))

    confident_wrong = unflagged = unflagged_correct = 0
    for i, p in enumerate(proposals):
        flagged = bool(p.get("needs_review"))
        correct = i in matched and matched[i][1]
        if not flagged:
            unflagged += 1
            unflagged_correct += int(correct)
            if not correct:
                confident_wrong += 1
    return PhotoScore(filename, items, len(free), len(proposals), confident_wrong, unflagged, unflagged_correct)


def _rate(n: float, d: float) -> float | None:
    return round(n / d, 3) if d else None


def summarize(scores: list[PhotoScore]) -> dict[str, Any]:
    items = [it for s in scores for it in s.items]
    total = len(items)
    found = sum(i.found for i in items)
    correct = sum(i.fully_correct for i in items)
    flagged_found = [i for i in items if i.found and i.flagged]
    proposals = sum(s.proposals for s in scores)

    by_tag: dict[str, dict[str, Any]] = {}
    for tag in sorted({t for i in items for t in i.tags}):
        sub = [i for i in items if tag in i.tags]
        by_tag[tag] = {
            "items": len(sub),
            "category_accuracy": _rate(sum(i.found for i in sub), len(sub)),
            "fully_correct_rate": _rate(sum(i.fully_correct for i in sub), len(sub)),
        }
    by_category: dict[str, dict[str, Any]] = {}
    for cat in sorted({i.category for i in items}):
        sub = [i for i in items if i.category == cat]
        by_category[cat] = {
            "items": len(sub),
            "category_accuracy": _rate(sum(i.found for i in sub), len(sub)),
            "fully_correct_rate": _rate(sum(i.fully_correct for i in sub), len(sub)),
        }
    return {
        "photos": len(scores),
        "ground_truth_items": total,
        "proposals": proposals,
        "category_accuracy": _rate(found, total),
        "fully_correct_rate": _rate(correct, total),
        "spec_accuracy_given_category": _rate(correct, found),
        "flagged_for_review_rate": _rate(sum(s.proposals - s.unflagged for s in scores), proposals),
        "confident_wrong_rate": _rate(sum(s.confident_wrong for s in scores), proposals),
        "auto_accept_precision": _rate(sum(s.unflagged_correct for s in scores), sum(s.unflagged for s in scores)),
        "missed_items": total - found,
        "extra_proposals": sum(s.extra_proposals for s in scores),
        "flagged_but_found": len(flagged_found),
        "by_tag": by_tag,
        "by_category": by_category,
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render_report(summary: dict[str, Any], *, model: str, mode_counts: dict[str, int], failed: list[str]) -> str:
    s = summary
    lines = [
        "# Identification accuracy report", "",
        f"- Model: `{model}`", f"- Photos scored: {s['photos']} (failed/skipped: {len(failed)})",
        f"- Ground-truth parts: {s['ground_truth_items']}; AI proposals: {s['proposals']}",
        f"- Segmentation modes: {mode_counts}", "",
        "| Metric | Value |", "|---|---|",
        f"| Category accuracy | {_pct(s['category_accuracy'])} |",
        f"| Fully correct (category + graded specs) | {_pct(s['fully_correct_rate'])} |",
        f"| Spec accuracy given right category | {_pct(s['spec_accuracy_given_category'])} |",
        f"| Proposals flagged for review | {_pct(s['flagged_for_review_rate'])} |",
        f"| Confident-wrong rate (wrong and NOT flagged) | {_pct(s['confident_wrong_rate'])} |",
        f"| Precision of un-flagged proposals | {_pct(s['auto_accept_precision'])} |",
        f"| Missed parts | {s['missed_items']} |", f"| Extra (unmatched) proposals | {s['extra_proposals']} |", "",
        "## By tag", "", "| Tag | Parts | Category acc. | Fully correct |", "|---|---|---|---|",
    ]
    for t, v in s["by_tag"].items():
        lines.append(f"| {t} | {v['items']} | {_pct(v['category_accuracy'])} | {_pct(v['fully_correct_rate'])} |")
    lines += ["", "## By category", "", "| Category | Parts | Category acc. | Fully correct |", "|---|---|---|---|"]
    for c, v in s["by_category"].items():
        lines.append(f"| {c} | {v['items']} | {_pct(v['category_accuracy'])} | {_pct(v['fully_correct_rate'])} |")
    if failed:
        lines += ["", "## Photos that failed", ""] + [f"- {f}" for f in failed]
    lines += ["", "Every proposal is confirmed by the user before it is saved; this report measures the AI step only."]
    return "\n".join(lines) + "\n"
