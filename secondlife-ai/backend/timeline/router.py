from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import catalog
from app.database import get_db
from app.models import InventoryItem, User
from app.security import get_current_user

from . import engine, library
from .store import load, save

try:
    from agent import llm as _llm
except ImportError:
    _llm = None

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


class DemoIn(BaseModel):
    budget_usd: float = Field(25, ge=1, le=500)
    deadline_days: int = Field(10, ge=3, le=30)
    project_keys: Optional[list[str]] = Field(None, max_length=3)


class EventIn(BaseModel):
    type: Literal["delivery_delay", "component_failed", "deadline_change", "budget_change"]
    purchase_id: Optional[str] = Field(None, max_length=16)
    days: Optional[int] = Field(None, ge=1, le=30)
    inventory_index: Optional[int] = Field(None, ge=0, le=500)
    quantity: Optional[int] = Field(None, ge=1, le=50)
    deadline_days: Optional[int] = Field(None, ge=1, le=60)
    budget_usd: Optional[float] = Field(None, ge=1, le=500)


def _caps():
    return {
        "external_checkout": False,
        "agent_llm": bool(_llm and _llm.enabled()),
        "projects": [{"key": p["key"], "name": p["name"]} for p in library.PROJECTS],
    }


def _inventory_for_user(db: Session, user: User) -> list[dict]:
    rows = db.scalars(
        select(InventoryItem).where(InventoryItem.user_id == user.id).order_by(InventoryItem.id)
    ).all()
    return [
        {"name": item.label, "quantity": item.quantity, "failed": 0}
        for item in rows
        if item.condition != catalog.SUSPECT
        and not catalog.missing_required_specs(item.category, item.specs)
    ]


def _require(db: Session, user: User):
    timeline = load(db, user.id)
    if not timeline:
        raise HTTPException(404, "No plan yet. Build one first.")
    return timeline


def _view(timeline):
    return {"exists": True, **engine.view(timeline), "capabilities": _caps()}


@router.get("/state")
def state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = load(db, user.id)
    return _view(timeline) if timeline else {"exists": False, "capabilities": _caps()}


@router.post("/demo")
def build(body: DemoIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    valid = {project["key"] for project in library.PROJECTS}
    if body.project_keys and not set(body.project_keys) <= valid:
        raise HTTPException(400, "Unknown project")
    try:
        timeline = engine.create_plan(
            int(round(body.budget_usd * 100)),
            body.deadline_days,
            held=_inventory_for_user(db, user),
            project_keys=body.project_keys,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save(db, user.id, timeline)
    return _view(timeline)


@router.post("/event")
def event(body: EventIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = _require(db, user)
    try:
        engine.heal(timeline, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save(db, user.id, timeline)
    return _view(timeline)


@router.post("/optimize")
def optimize(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    timeline = _require(db, user)
    before = engine.evaluate(timeline)
    timeline["order"] = engine.optimize_order(timeline)
    after = engine.evaluate(timeline)
    names = {project["key"]: project["name"] for project in timeline["projects"]}
    engine.log(
        timeline,
        "optimize",
        "Resource optimizer tried every project order on the shared maker, soldering and bench lanes. Best order: "
        + " > ".join(names[key] for key in timeline["order"] if key in names) + ".",
        before,
        after,
    )
    save(db, user.id, timeline)
    return _view(timeline)


@router.post("/purchases/{purchase_id}/ordered")
def mark_purchase_ordered(
    purchase_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record a user-confirmed external purchase; supplier checkout is not handled by ReLife."""
    timeline = _require(db, user)
    purchase = next(
        (item for item in timeline["purchases"] if item["id"] == purchase_id and item["status"] == "planned"),
        None,
    )
    if purchase is None:
        raise HTTPException(404, "Planned purchase not found")
    before = engine.evaluate(timeline)
    purchase["status"] = "ordered"
    purchase["ordered_on"] = max(date.today(), date.fromisoformat(timeline["settings"]["start_date"])).isoformat()
    timeline["order"] = engine.optimize_order(timeline)
    after = engine.evaluate(timeline)
    engine.log(
        timeline,
        "external_purchase",
        f"User confirmed ordering {purchase['part']} from its supplier. Delivery estimate is simulated.",
        before,
        after,
    )
    save(db, user.id, timeline)
    return _view(timeline)


def mount_timeline_ui(app: FastAPI):
    ui = Path(__file__).resolve().parent.parent / "sl_ui" / "timeline"
    if ui.is_dir():
        app.mount("/timeline-ui", StaticFiles(directory=str(ui), html=True), name="timeline-ui")
