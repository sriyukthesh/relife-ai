"""Voice-guided build sessions: start, current step, next/previous, finish."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import catalog
from ..database import get_db
from ..models import BuildSession, Project, User
from ..schemas import BuildOut, BuildStartIn, MissingPartOut, StepOut
from ..security import get_current_user
from ..services.copilot import step_view
from ..services.project_engine import evaluate_project, split_usable
from ..services.stock import load_stock, project_dict

router = APIRouter(prefix="/builds", tags=["builds"])


def _owned(db: Session, user: User, build_id: int) -> BuildSession:
    b = db.get(BuildSession, build_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build not found")
    return b


def _out(db: Session, user: User, b: BuildSession) -> BuildOut:
    project = db.get(Project, b.project_id)
    pd = project_dict(project)
    usable, _ = split_usable(load_stock(db, user.id))
    match = evaluate_project(pd, usable)
    total = len(pd["steps"])
    step = step_view(pd, b.current_step)
    # Deterministic reminders: untested parts must be tested before use.
    warnings = list(dict.fromkeys(w for r in match.requirements for w in r.warnings))
    return BuildOut(
        id=b.id, project_slug=project.slug, title=project.title, status=b.status,
        current_step=step["index"], total_steps=total, step=StepOut(**step),
        is_last=step["index"] >= total - 1, safety_note=project.safety_note,
        warnings=warnings,
        missing_parts=[MissingPartOut.model_validate(asdict(m)) for m in match.missing_parts],
    )


@router.post("", response_model=BuildOut, status_code=status.HTTP_201_CREATED)
def start_build(body: BuildStartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.scalar(select(Project).where(Project.slug == body.project_slug))
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    usable, _ = split_usable(load_stock(db, user.id))
    match = evaluate_project(project_dict(project), usable)
    if not match.can_build and not body.allow_incomplete:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": "You are missing parts for this project.",
                "missing_parts": [asdict(m) for m in match.missing_parts],
            },
        )
    for old in db.scalars(
        select(BuildSession).where(BuildSession.user_id == user.id, BuildSession.status == "active")
    ):
        old.status = "abandoned"
    b = BuildSession(user_id=user.id, project_id=project.id, current_step=0, status="active")
    db.add(b)
    db.commit()
    return _out(db, user, b)


@router.get("/current", response_model=BuildOut)
def current_build(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    b = db.scalar(
        select(BuildSession)
        .where(BuildSession.user_id == user.id, BuildSession.status == "active")
        .order_by(BuildSession.id.desc())
    )
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active build")
    return _out(db, user, b)


def _move(db: Session, user: User, build_id: int, delta: int) -> BuildOut:
    b = _owned(db, user, build_id)
    if b.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This build is not active")
    total = len(db.get(Project, b.project_id).steps)
    b.current_step = max(0, min(b.current_step + delta, max(total - 1, 0)))
    db.commit()
    return _out(db, user, b)


@router.get("/{build_id}", response_model=BuildOut)
def get_build(build_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _out(db, user, _owned(db, user, build_id))


@router.post("/{build_id}/next", response_model=BuildOut)
def next_step(build_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _move(db, user, build_id, +1)


@router.post("/{build_id}/previous", response_model=BuildOut)
def previous_step(build_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _move(db, user, build_id, -1)


@router.post("/{build_id}/finish", response_model=BuildOut)
def finish_build(build_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    b = _owned(db, user, build_id)
    b.status = "completed"
    db.commit()
    return _out(db, user, b)
