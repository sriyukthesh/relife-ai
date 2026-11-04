"""Marketplace: shows the circular-reuse loop end to end.

- Listing a part moves it out of the seller's inventory (escrow); cancelling returns it.
- Suspect or incomplete parts cannot be listed (rules in services/marketplace_rules.py).
- Checkout is one transaction with row locks; bought parts arrive as source="marketplace",
  condition="unverified" so the user still has to test them.
"""
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import catalog
from ..database import get_db
from ..models import InventoryItem, Listing, Order, Project, User
from ..schemas import (
    BuyIn, ListingIn, ListingOut, ListingSuggestionOut, OrderOut, PartOffersOut, ProjectOffersOut,
)
from ..security import get_current_user
from ..services import marketplace_rules as rules
from ..services import pricing
from ..services.project_engine import evaluate_project, split_usable
from ..services.stock import add_stock, load_stock, project_dict

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

SIMULATION_NOTE = "Checkout complete."


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))}


def _out(l: Listing, names: dict[int, str], viewer_id: int) -> ListingOut:
    return ListingOut(
        id=l.id, seller_id=l.seller_id, seller_name=names.get(l.seller_id, "Seller"),
        category=l.category, label=l.label, specs=l.specs, quantity=l.quantity,
        price_cents=l.price_cents, condition=l.condition, status=l.status,
        mine=l.seller_id == viewer_id, created_at=l.created_at,
    )


def _as_dict(l: Listing) -> dict[str, Any]:
    return {
        "id": l.id, "seller_id": l.seller_id, "category": l.category, "specs": l.specs,
        "quantity": l.quantity, "price_cents": l.price_cents, "condition": l.condition, "status": l.status,
    }


@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    category: str | None = Query(None), mine: bool = Query(False),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    q = select(Listing).where(Listing.status == "active")
    if category:
        q = q.where(Listing.category == category)
    q = q.where(Listing.seller_id == user.id) if mine else q.where(Listing.seller_id != user.id)
    rows = db.scalars(q.order_by(Listing.created_at.desc())).all()
    names = _names(db, {r.seller_id for r in rows})
    return [_out(r, names, user.id) for r in rows]


@router.get("/suggest/{item_id}", response_model=ListingSuggestionOut)
def suggest_listing(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Prefill the 'list it' form for a part: eligibility, title, quantity and a starting price.
    Eligibility and price come from deterministic rules, not from the AI."""
    item = db.get(InventoryItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    problem = rules.listing_problem(
        category=item.category, specs=item.specs, condition=item.condition,
        owned_qty=item.quantity, list_qty=1, price_cents=1,
    )
    peers = db.scalars(
        select(Listing).where(Listing.status == "active", Listing.seller_id != user.id, Listing.category == item.category)
    ).all()
    prices = [p.price_cents for p in peers if pricing.comparable(item.category, item.specs, p.category, p.specs)]
    sug = pricing.suggest_price(item.category, item.condition, prices)
    return ListingSuggestionOut(
        item_id=item.id, label=item.label, category=item.category, specs=item.specs,
        condition=item.condition, quantity_owned=item.quantity,
        can_list=problem is None, problem=problem,
        suggested_title=pricing.suggest_title(item.label, item.specs),
        suggested_quantity=item.quantity,
        suggested_price_cents=sug["price_cents"], price_low_cents=sug["low_cents"],
        price_high_cents=sug["high_cents"], price_basis=sug["basis"],
    )


@router.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(select(InventoryItem).where(InventoryItem.id == body.item_id).with_for_update())
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    problem = rules.listing_problem(
        category=item.category, specs=item.specs, condition=item.condition,
        owned_qty=item.quantity, list_qty=body.quantity, price_cents=body.price_cents,
    )
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    listing = Listing(
        seller_id=user.id, source_item_id=None, category=item.category,
        label=((body.title or "").strip() or item.label)[:120],
        specs=dict(item.specs), quantity=body.quantity, price_cents=body.price_cents,
        condition=item.condition, status="active",
    )
    db.add(listing)
    item.quantity -= body.quantity  # escrow
    if item.quantity == 0:
        db.delete(item)
    db.commit()
    return _out(listing, {user.id: user.name}, user.id)


@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if l is None or l.seller_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if l.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Listing is no longer active")
    add_stock(db, user.id, category=l.category, label=l.label, specs=l.specs,
              quantity=l.quantity, condition=l.condition, source="manual")
    l.status = "cancelled"
    l.quantity = 0
    db.commit()


@router.post("/listings/{listing_id}/buy", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def buy(listing_id: int, body: BuyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Legacy one-click purchase kept for the API and tests. The app now uses the cart and
    POST /checkout/pay (address, payment method, receipt), which never pays by accident."""
    l = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if l is None or l.status != "active" or l.quantity <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "This listing is no longer available")
    if l.seller_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot buy your own listing")
    if body.quantity > l.quantity:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only {l.quantity} left")

    l.quantity -= body.quantity
    if l.quantity == 0:
        l.status = "sold"
    order = Order(buyer_id=user.id, listing_id=l.id, quantity=body.quantity,
                  total_cents=l.price_cents * body.quantity, status="completed")
    db.add(order)
    add_stock(db, user.id, category=l.category, label=l.label, specs=dict(l.specs),
              quantity=body.quantity, condition=rules.buyer_condition(l.condition), source="marketplace")
    db.commit()  # listing, order and inventory change together or not at all
    return OrderOut(
        id=order.id, listing_id=l.id, label=l.label, quantity=order.quantity,
        total_cents=order.total_cents, status=order.status, created_at=order.created_at,
        note="The parts are marked unverified: test them before use.",
    )


@router.get("/orders", response_model=list[OrderOut])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(Order, Listing).join(Listing, Listing.id == Order.listing_id)
        .where(Order.buyer_id == user.id).order_by(Order.id.desc())
    ).all()
    return [
        OrderOut(id=o.id, listing_id=o.listing_id, label=l.label, quantity=o.quantity,
                 total_cents=o.total_cents, status=o.status, created_at=o.created_at, note=SIMULATION_NOTE)
        for o, l in rows
    ]


@router.get("/for-project/{slug}", response_model=ProjectOffersOut)
def offers_for_project(slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """For each part the user is missing for a project, list matching marketplace listings."""
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    usable, _ = split_usable(load_stock(db, user.id))
    match = evaluate_project(project_dict(project), usable)
    active = db.scalars(select(Listing).where(Listing.status == "active", Listing.seller_id != user.id)).all()
    by_id = {l.id: l for l in active}
    names = _names(db, {l.seller_id for l in active})
    dicts = [_as_dict(l) for l in active]
    parts = []
    for mp in match.missing_parts:
        found = rules.offers_for_part(asdict(mp), dicts, user.id)
        parts.append(PartOffersOut(
            label=mp.label, category=mp.category, quantity=mp.quantity, constraints=mp.constraints,
            offers=[_out(by_id[d["id"]], names, user.id) for d in found],
        ))
    return ProjectOffersOut(project_slug=slug, parts=parts)
