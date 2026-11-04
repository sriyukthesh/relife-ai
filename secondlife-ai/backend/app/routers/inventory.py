from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import catalog
from ..database import get_db
from ..models import InventoryItem, User
from ..schemas import InventoryItemIn, InventoryItemOut, InventoryItemPatch
from ..security import get_current_user

router = APIRouter(prefix="/inventory", tags=["inventory"])


def to_out(item: InventoryItem) -> InventoryItemOut:
    missing = catalog.missing_required_specs(item.category, item.specs)
    return InventoryItemOut(
        id=item.id, category=item.category, label=item.label, specs=item.specs,
        quantity=item.quantity, condition=item.condition, source=item.source,
        ai_confidence=item.ai_confidence, ai_notes=item.ai_notes,
        confirmed_at=item.confirmed_at, missing_specs=missing,
        usable=not missing and item.condition != catalog.SUSPECT,
    )


def _owned(db: Session, user: User, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@router.get("", response_model=list[InventoryItemOut])
def list_inventory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(InventoryItem).where(InventoryItem.user_id == user.id).order_by(InventoryItem.category, InventoryItem.id)
    ).all()
    return [to_out(r) for r in rows]


@router.post("", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
def add_item(body: InventoryItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not body.confirmed_by_user:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Components must be confirmed by the user before entering inventory.",
        )
    specs = catalog.normalize_specs(body.category, body.specs)

    # Merge duplicates (same category, specs and condition) instead of creating new rows.
    same = db.scalars(
        select(InventoryItem).where(
            InventoryItem.user_id == user.id,
            InventoryItem.category == body.category,
            InventoryItem.condition == body.condition,
        )
    ).all()
    for row in same:
        if row.specs == specs:
            row.quantity += body.quantity
            db.commit()
            return to_out(row)

    item = InventoryItem(
        user_id=user.id, category=body.category, label=body.label.strip(), specs=specs,
        quantity=body.quantity, condition=body.condition, source=body.source,
        ai_confidence=body.ai_confidence, ai_notes=body.ai_notes,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    return to_out(item)


@router.patch("/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: int, body: InventoryItemPatch, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    item = _owned(db, user, item_id)
    if body.label is not None:
        item.label = body.label.strip()
    if body.specs is not None:
        item.specs = catalog.normalize_specs(item.category, body.specs)
    if body.quantity is not None:
        item.quantity = body.quantity
    if body.condition is not None:
        item.condition = body.condition
    db.commit()
    return to_out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_owned(db, user, item_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
