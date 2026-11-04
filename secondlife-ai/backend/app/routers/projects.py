from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InventoryItem, Project, User
from ..schemas import ProjectDetailOut, ProjectMatchOut, ProjectOut, RecommendationsOut
from ..security import get_current_user
from ..services.project_engine import StockItem, recommend

router = APIRouter(tags=["projects"])


def project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id, "slug": p.slug, "title": p.title, "difficulty": p.difficulty,
        "estimated_minutes": p.estimated_minutes, "description": p.description,
        "safety_note": p.safety_note, "requirements": p.requirements, "steps": p.steps,
    }


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.difficulty, Project.title)).all()


@router.get("/projects/{slug}", response_model=ProjectDetailOut)
def get_project(slug: str, db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("/recommendations", response_model=RecommendationsOut)
def build_with_what_i_have(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """'Build with What I Have': rank projects against the user's confirmed inventory."""
    rows = db.scalars(select(InventoryItem).where(InventoryItem.user_id == user.id)).all()
    stock = [
        StockItem(r.id, r.label, r.category, r.specs, r.quantity, r.condition) for r in rows
    ]
    projects = [project_to_dict(p) for p in db.scalars(select(Project)).all()]
    matches, excluded = recommend(projects, stock)
    return RecommendationsOut(
        matches=[ProjectMatchOut.model_validate(asdict(m)) for m in matches],
        excluded_items=excluded,
    )
