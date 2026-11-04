"""GET /stats/impact: dashboard numbers. Everything is counted from real rows, then
converted to estimates by services/impact.py (assumed masses, clearly disclosed)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import catalog
from ..database import get_db
from ..models import BuildSession, InventoryItem, Listing, Order, Project, User
from ..security import get_current_user
from ..services import impact

router = APIRouter(prefix="/stats", tags=["stats"])

DEMO_EMAIL_PATTERN = "%@secondlife.ai"  # accounts created by app.seed / app.seed_community


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _label(cat: str) -> str:
    return catalog.CATEGORIES.get(cat, {}).get("label", cat)


@router.get("/impact")
def impact_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)

    # --- reused: parts required by finished builds ---
    done = db.execute(
        select(BuildSession, Project)
        .join(Project, Project.id == BuildSession.project_id)
        .where(BuildSession.status == "completed")
    ).all()
    reused_all: list[impact.Event] = []
    reused_mine: list[impact.Event] = []
    builds_mine = 0
    for b, p in done:
        when = _aware(b.updated_at)
        evs = [(when, r.get("category", "other"), int(r.get("qty", 1))) for r in (p.requirements or [])]
        reused_all += evs
        if b.user_id == user.id:
            reused_mine += evs
            builds_mine += 1

    # --- resold: parts sold through the marketplace ---
    orders = db.execute(
        select(Order, Listing).join(Listing, Listing.id == Order.listing_id).where(Order.status == "completed")
    ).all()
    resold_all: list[impact.Event] = []
    resold_mine: list[impact.Event] = []
    bought_mine = 0
    for o, l in orders:
        ev = (_aware(o.created_at), l.category, o.quantity)
        resold_all.append(ev)
        if l.seller_id == user.id:
            resold_mine.append(ev)
        if o.buyer_id == user.id:
            bought_mine += o.quantity

    # --- stock and community counters ---
    inv_qty = db.scalar(select(func.coalesce(func.sum(InventoryItem.quantity), 0))) or 0
    my_inv_qty = db.scalar(
        select(func.coalesce(func.sum(InventoryItem.quantity), 0)).where(InventoryItem.user_id == user.id)
    ) or 0
    act_count, act_qty = db.execute(
        select(func.count(Listing.id), func.coalesce(func.sum(Listing.quantity), 0)).where(Listing.status == "active")
    ).one()
    my_act_count = db.scalar(
        select(func.count(Listing.id)).where(Listing.status == "active", Listing.seller_id == user.id)
    ) or 0
    makers = db.scalar(select(func.count(User.id))) or 0
    volume_paise = db.scalar(select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.status == "completed")) or 0
    demo_accounts = db.scalar(select(func.count(User.id)).where(User.email.like(DEMO_EMAIL_PATTERN))) or 0

    # --- recent activity (other makers are anonymous) ---
    feed: list[tuple[datetime, str, str, bool]] = []
    for o, l in orders:
        mine = o.buyer_id == user.id
        feed.append((_aware(o.created_at), "purchase", f"{'You' if mine else 'A maker'} bought {o.quantity} × {l.label}", mine))
    for b, p in done:
        mine = b.user_id == user.id
        feed.append((_aware(b.updated_at), "build", f"{'You' if mine else 'A maker'} finished “{p.title}”", mine))
    for l in db.scalars(select(Listing).where(Listing.status == "active").order_by(Listing.created_at.desc()).limit(10)):
        mine = l.seller_id == user.id
        feed.append((_aware(l.created_at), "listing", f"{'You' if mine else 'A maker'} listed {l.quantity} × {l.label}", mine))
    feed.sort(key=lambda x: x[0], reverse=True)

    t_all = impact.totals(reused_all, resold_all)
    t_me = impact.totals(reused_mine, resold_mine)
    cats = impact.category_breakdown(reused_all, resold_all)

    return {
        "generated_at": now.isoformat(),
        "platform": {
            **t_all,
            "builds_completed": len(done),
            "makers": makers,
            "parts_in_circulation": int(inv_qty) + int(act_qty),
            "active_listings": int(act_count),
            "marketplace_volume_paise": int(volume_paise),
        },
        "me": {
            **t_me,
            "builds_completed": builds_mine,
            "parts_in_stock": int(my_inv_qty),
            "parts_bought": bought_mine,
            "active_listings": int(my_act_count),
        },
        "weekly": impact.weekly_series(reused_all, resold_all, weeks=12, now=now),
        "by_category": [{**c, "label": _label(c["category"])} for c in cats[:6]],
        "activity": [
            {"when": w.isoformat(), "kind": k, "text": t, "mine": m} for (w, k, t, m) in feed[:8]
        ],
        "demo_data": demo_accounts > 0,
        "methodology": {
            "grams_per_part": [
                {"category": c, "label": _label(c), "grams": g} for c, g in impact.GRAMS_PER_PART.items()
            ],
            "notes": [
                "Reused = parts required by builds that makers marked as finished.",
                "Resold = parts sold through the marketplace.",
                "A part that is sold and then used in a build can appear in both counts, so the headline "
                "uses the lower bound (the larger count per category). The upper bound adds both.",
                "Masses are rough typical values for hobby parts, not measurements. They estimate component "
                "weight kept out of the bin, not a full life-cycle saving.",
                "Marketplace volume reflects completed orders.",
            ],
        },
    }
