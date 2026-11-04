"""Cart preview and payment. No card data: the client only sends a payment
method name. One transaction: listings are locked in id order, orders are created, the parts land in
the buyer's inventory (unverified), and a receipt (Payment) is saved. A retry with the same
idempotency key returns the same receipt instead of paying twice."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Listing, Order, Payment, User
from ..schemas import CartPreviewIn, CartPreviewOut, CheckoutIn, PaymentOut, PricedLineOut
from ..security import get_current_user
from ..services import checkout as co
from ..services import marketplace_rules as rules
from ..services.stock import add_stock

router = APIRouter(prefix="/checkout", tags=["checkout"])

NOTE = (
    "Parts were added to My parts as untested, so test them before use."
)


def _names(db: Session, ids: set[int]) -> dict[int, str]:
    return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def _as_dict(l: Listing) -> dict:
    return {
        "id": l.id, "seller_id": l.seller_id, "category": l.category, "label": l.label, "specs": l.specs,
        "quantity": l.quantity, "price_cents": l.price_cents, "condition": l.condition, "status": l.status,
    }


def _price(db: Session, lines, user: User, lock: bool = False):
    merged = co.merge_lines((l.listing_id, l.quantity) for l in lines)
    ids = sorted(merged)  # lock in a fixed order so two checkouts cannot deadlock
    q = select(Listing).where(Listing.id.in_(ids)).order_by(Listing.id)
    listings = {l.id: l for l in db.scalars(q.with_for_update() if lock else q)}
    names = _names(db, {l.seller_id for l in listings.values()})
    priced = []
    for lid in ids:
        l = listings.get(lid)
        priced.append(co.price_line(_as_dict(l) if l else {"id": lid, "status": "missing"}, merged[lid], user.id,
                                    names.get(l.seller_id, "Seller") if l else "Seller"))
    return priced, listings


def _out(p: Payment) -> PaymentOut:
    return PaymentOut(
        id=p.id, reference=p.reference, method=p.method, method_label=co.METHOD_LABELS.get(p.method, p.method),
        status=p.status, subtotal_cents=p.subtotal_cents, delivery_cents=p.delivery_cents,
        total_cents=p.total_cents, address=p.address, lines=p.lines, created_at=p.created_at, note=NOTE,
    )


@router.post("/preview", response_model=CartPreviewOut)
def preview(body: CartPreviewIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    priced, _ = _price(db, body.lines, user)
    return CartPreviewOut(lines=[PricedLineOut(**l) for l in priced], **co.totals(priced))


@router.post("/pay", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def pay(body: CheckoutIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.scalar(select(Payment).where(Payment.user_id == user.id, Payment.idempotency_key == body.idempotency_key))
    if existing:
        return _out(existing)  # a retried request never pays twice

    priced, listings = _price(db, body.lines, user, lock=True)
    problems = [f"{l['label']}: {l['issue']}" for l in priced if l["issue"]]
    if problems:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Your cart changed: " + " ".join(problems) + " Review your cart and try again.")
    if body.simulate_decline:
        db.rollback()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            "Payment declined by the bank. You were not charged and your cart is unchanged.")

    t = co.totals(priced)
    now = datetime.now(timezone.utc)
    snapshot = []
    for p in priced:
        l = listings[p["listing_id"]]
        l.quantity -= p["quantity"]
        if l.quantity == 0:
            l.status = "sold"
        order = Order(buyer_id=user.id, listing_id=l.id, quantity=p["quantity"], total_cents=p["line_cents"], status="completed")
        db.add(order)
        db.flush()
        add_stock(db, user.id, category=l.category, label=l.label, specs=dict(l.specs), quantity=p["quantity"],
                  condition=rules.buyer_condition(l.condition), source="marketplace")
        snapshot.append({
            "order_id": order.id, "listing_id": l.id, "label": l.label, "quantity": p["quantity"],
            "unit_cents": p["unit_cents"], "line_cents": p["line_cents"], "seller_name": p["seller_name"],
        })
    payment = Payment(
        user_id=user.id, reference=co.new_reference(now), idempotency_key=body.idempotency_key, method=body.method,
        status="paid", subtotal_cents=t["subtotal_cents"], delivery_cents=t["delivery_cents"],
        total_cents=t["total_cents"], address=body.address.model_dump(), lines=snapshot,
    )
    db.add(payment)
    try:
        db.commit()  # listings, orders, inventory and receipt change together or not at all
    except IntegrityError:
        db.rollback()
        again = db.scalar(select(Payment).where(Payment.user_id == user.id, Payment.idempotency_key == body.idempotency_key))
        if again:
            return _out(again)
        raise HTTPException(status.HTTP_409_CONFLICT, "Could not complete the order. Please try again.")
    db.refresh(payment)
    return _out(payment)


@router.get("/payments", response_model=list[PaymentOut])
def my_payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc()).limit(30)).all()
    return [_out(p) for p in rows]
