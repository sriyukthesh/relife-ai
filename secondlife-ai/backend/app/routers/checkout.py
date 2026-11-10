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
from ..config import get_settings
from ..models import Listing, Order, PayPalCheckout, Payment, User
from ..schemas import CartLineIn, CartPreviewIn, CartPreviewOut, PayPalOrderIn, PaymentOut, PricedLineOut
from ..security import get_current_user
from ..services import checkout as co
from ..services import marketplace_rules as rules
from ..services import paypal
from ..services.paypal import PayPalError
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


@router.post("/pay", status_code=status.HTTP_410_GONE)
def pay():
    raise HTTPException(
        status.HTTP_410_GONE,
        "Simulated payments are disabled. Use the PayPal sandbox checkout.",
    )


@router.get("/paypal/config")
def paypal_config(user: User = Depends(get_current_user)):
    settings = get_settings()
    return {
        "client_id": settings.paypal_client_id,
        "currency": settings.paypal_currency,
        "seller_email": settings.paypal_seller_email,
        "enabled": bool(settings.paypal_client_id and settings.paypal_client_secret),
        "environment": "sandbox",
    }


@router.post("/paypal/orders")
def create_paypal_order(body: PayPalOrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings = get_settings()
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "PayPal sandbox credentials are not configured")

    checkout = db.scalar(select(PayPalCheckout).where(
        PayPalCheckout.user_id == user.id,
        PayPalCheckout.idempotency_key == body.idempotency_key,
    ))
    if checkout and checkout.paypal_order_id:
        return {
            "paypal_order_id": checkout.paypal_order_id,
            "total": f"{checkout.total_cents // 100}.{checkout.total_cents % 100:02d}",
            "currency": checkout.currency,
        }

    if checkout is None:
        priced, _ = _price(db, body.lines, user)
        problems = [f"{line['label']}: {line['issue']}" for line in priced if line["issue"]]
        if problems:
            raise HTTPException(status.HTTP_409_CONFLICT, "Your cart changed: " + " ".join(problems))
        totals = co.totals(priced)
        if not totals["ok"] or totals["total_cents"] <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The cart must contain available items")
        snapshot = [{
            "listing_id": line["listing_id"],
            "label": line["label"],
            "category": line["category"],
            "quantity": line["quantity"],
            "unit_cents": line["unit_cents"],
            "line_cents": line["line_cents"],
        } for line in priced]
        checkout = PayPalCheckout(
            user_id=user.id,
            idempotency_key=body.idempotency_key,
            status="CREATING",
            currency=settings.paypal_currency,
            subtotal_cents=totals["subtotal_cents"],
            delivery_cents=totals["delivery_cents"],
            total_cents=totals["total_cents"],
            address=body.address.model_dump(),
            lines=snapshot,
        )
        db.add(checkout)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            checkout = db.scalar(select(PayPalCheckout).where(
                PayPalCheckout.user_id == user.id,
                PayPalCheckout.idempotency_key == body.idempotency_key,
            ))
            if checkout is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "Could not start PayPal checkout. Please try again.")
            if checkout.paypal_order_id:
                return {
                    "paypal_order_id": checkout.paypal_order_id,
                    "total": f"{checkout.total_cents // 100}.{checkout.total_cents % 100:02d}",
                    "currency": checkout.currency,
                }

    try:
        result = paypal.create_order(
            user_id=user.id,
            idempotency_key=checkout.idempotency_key,
            lines=checkout.lines,
            subtotal_cents=checkout.subtotal_cents,
            delivery_cents=checkout.delivery_cents,
            total_cents=checkout.total_cents,
            currency=checkout.currency,
            reference_id=f"SL-{checkout.id}",
        )
    except PayPalError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    order_id = result.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal returned an invalid order response")

    checkout.paypal_order_id = order_id
    checkout.status = "CREATED"
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(select(PayPalCheckout).where(
            PayPalCheckout.user_id == user.id,
            PayPalCheckout.idempotency_key == body.idempotency_key,
        ))
        if existing and existing.paypal_order_id:
            return {
                "paypal_order_id": existing.paypal_order_id,
                "total": f"{existing.total_cents // 100}.{existing.total_cents % 100:02d}",
                "currency": existing.currency,
            }
        raise HTTPException(status.HTTP_409_CONFLICT, "Could not save PayPal checkout. Please retry.") from exc
    return {
        "paypal_order_id": order_id,
        "total": f"{checkout.total_cents // 100}.{checkout.total_cents % 100:02d}",
        "currency": checkout.currency,
    }


@router.post("/paypal/orders/{paypal_order_id}/capture", response_model=PaymentOut)
def capture_paypal_order(
    paypal_order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    checkout = db.scalar(select(PayPalCheckout).where(
        PayPalCheckout.user_id == user.id,
        PayPalCheckout.paypal_order_id == paypal_order_id,
    ).with_for_update())
    if checkout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown PayPal order")

    payment = db.scalar(select(Payment).where(
        Payment.user_id == user.id,
        Payment.idempotency_key == checkout.idempotency_key,
    ))
    if payment:
        return _out(payment)
    if checkout.status not in {"CREATED", "CAPTURING"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "This PayPal order cannot be captured")

    lines_in = [CartLineIn(listing_id=line["listing_id"], quantity=line["quantity"]) for line in checkout.lines]
    priced, listings = _price(db, lines_in, user, lock=True)
    problems = [f"{line['label']}: {line['issue']}" for line in priced if line["issue"]]
    totals = co.totals(priced)
    if problems or (
        totals["subtotal_cents"] != checkout.subtotal_cents
        or totals["delivery_cents"] != checkout.delivery_cents
        or totals["total_cents"] != checkout.total_cents
    ):
        db.rollback()
        message = " ".join(problems) if problems else "The cart price changed."
        raise HTTPException(status.HTTP_409_CONFLICT, f"{message} Review your cart and start checkout again.")

    checkout.status = "CAPTURING"
    db.flush()
    try:
        result = paypal.capture_order(
            paypal_order_id=paypal_order_id,
            user_id=user.id,
            idempotency_key=checkout.idempotency_key,
        )
    except PayPalError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    try:
        capture = result["purchase_units"][0]["payments"]["captures"][0]
        capture_amount = capture["amount"]
        capture_id = capture["id"]
    except (KeyError, IndexError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "PayPal returned an invalid capture response") from exc

    amount = f"{checkout.total_cents // 100}.{checkout.total_cents % 100:02d}"
    if (
        result.get("id") != paypal_order_id
        or result.get("status") != "COMPLETED"
        or not isinstance(capture, dict)
        or not isinstance(capture_amount, dict)
        or capture.get("status") != "COMPLETED"
        or capture_amount.get("value") != amount
        or capture_amount.get("currency_code") != checkout.currency
        or not isinstance(capture_id, str)
        or not capture_id
    ):
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "PayPal payment was not completed for the expected amount")

    now = datetime.now(timezone.utc)
    order_lines = []
    for line in priced:
        listing = listings[line["listing_id"]]
        listing.quantity -= line["quantity"]
        if listing.quantity == 0:
            listing.status = "sold"
        order = Order(
            buyer_id=user.id,
            listing_id=listing.id,
            quantity=line["quantity"],
            total_cents=line["line_cents"],
            status="completed",
        )
        db.add(order)
        db.flush()
        add_stock(
            db,
            user.id,
            category=listing.category,
            label=listing.label,
            specs=dict(listing.specs),
            quantity=line["quantity"],
            condition=rules.buyer_condition(listing.condition),
            source="marketplace",
        )
        order_lines.append({
            "order_id": order.id,
            "listing_id": listing.id,
            "label": line["label"],
            "quantity": line["quantity"],
            "unit_cents": line["unit_cents"],
            "line_cents": line["line_cents"],
            "seller_name": line["seller_name"],
        })

    payment = Payment(
        user_id=user.id,
        reference=co.new_reference(now),
        idempotency_key=checkout.idempotency_key,
        method="paypal",
        status="paid",
        subtotal_cents=checkout.subtotal_cents,
        delivery_cents=checkout.delivery_cents,
        total_cents=checkout.total_cents,
        address=checkout.address,
        lines=order_lines,
    )
    db.add(payment)
    checkout.status = "CAPTURED"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Payment).where(
            Payment.user_id == user.id,
            Payment.idempotency_key == checkout.idempotency_key,
        ))
        if existing:
            return _out(existing)
        raise HTTPException(status.HTTP_409_CONFLICT, "Could not finalize the payment. Retry capture safely.")
    db.refresh(payment)
    return _out(payment)


@router.get("/payments", response_model=list[PaymentOut])
def my_payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc()).limit(30)).all()
    return [_out(p) for p in rows]
