"""Small DB helpers shared by the builds, copilot and marketplace routers."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import InventoryItem, Project
from .project_engine import StockItem


def load_stock(db: Session, user_id: int) -> list[StockItem]:
    rows = db.scalars(select(InventoryItem).where(InventoryItem.user_id == user_id)).all()
    return [StockItem(r.id, r.label, r.category, r.specs, r.quantity, r.condition) for r in rows]


def project_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id, "slug": p.slug, "title": p.title, "difficulty": p.difficulty,
        "estimated_minutes": p.estimated_minutes, "description": p.description,
        "safety_note": p.safety_note, "requirements": p.requirements, "steps": p.steps,
    }


def add_stock(
    db: Session, user_id: int, *, category: str, label: str, specs: dict[str, Any],
    quantity: int, condition: str, source: str,
) -> InventoryItem:
    """Add parts to a user's inventory, merging with an identical row (same category/specs/condition)."""
    rows = db.scalars(
        select(InventoryItem).where(
            InventoryItem.user_id == user_id,
            InventoryItem.category == category,
            InventoryItem.condition == condition,
        )
    ).all()
    for row in rows:
        if row.specs == specs:
            row.quantity += quantity
            return row
    item = InventoryItem(
        user_id=user_id, category=category, label=label, specs=specs,
        quantity=quantity, condition=condition, source=source,
    )
    db.add(item)
    return item
