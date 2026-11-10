"""Channel3 search for project parts that are still missing from a user's inventory."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InventoryItem, Project, User
from ..security import get_current_user
from ..services.channel3 import Channel3Error, plan_purchase
from ..services.project_engine import StockItem, evaluate_project, split_usable
from ..services.stock import project_dict

router = APIRouter(prefix="/parts", tags=["parts"])


class Channel3PlanIn(BaseModel):
    budget_usd: float = Field(default=25.0, gt=0, le=10000)


@router.post("/channel3/{project_slug}")
def channel3_plan(
    project_slug: str,
    body: Channel3PlanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.scalar(select(Project).where(Project.slug == project_slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    rows = db.scalars(select(InventoryItem).where(InventoryItem.user_id == user.id)).all()
    stock = [StockItem(row.id, row.label, row.category, row.specs, row.quantity, row.condition) for row in rows]
    usable, _ = split_usable(stock)
    match = evaluate_project(project_dict(project), usable)

    try:
        plan = plan_purchase([asdict(part) for part in match.missing_parts], body.budget_usd)
    except Channel3Error as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    plan["covered_by_salvage"] = [
        {
            "part": requirement.label,
            "qty": sum(allocation.quantity for allocation in requirement.allocated),
        }
        for requirement in match.requirements
        if requirement.allocated
    ]
    return plan
