"""POST /copilot/ask: Muse Spark answers questions about the user's CURRENT build step."""
import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BuildSession, Project, User
from ..schemas import CopilotAnswerOut, CopilotAskIn, CopilotChatOut
from ..security import get_current_user
from ..services import copilot as cp
from ..services.inspector import full_to_jpeg, load_image
from ..services.meta_client import MetaAPIError, chat_text, image_data_url
from ..services.project_engine import recommend
from ..services.stock import load_stock, project_dict

log = logging.getLogger("secondlife.copilot")
router = APIRouter(prefix="/copilot", tags=["copilot"])
_limiter = cp.RateLimiter(max_calls=20, window_s=60)


@router.post("/ask", response_model=CopilotAnswerOut)
async def ask(body: CopilotAskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    build = db.get(BuildSession, body.build_id)
    if build is None or build.user_id != user.id or build.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active build not found")
    if not _limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many questions; wait a moment.")

    project = project_dict(db.get(Project, build.project_id))
    step_index = cp.step_view(project, build.current_step)["index"]

    # Deterministic safety guard runs BEFORE any model call.
    if cp.needs_safety_override(body.question):
        return CopilotAnswerOut(
            answer=cp.safety_override_reply(body.question),
            step_index=step_index,
            source="safety_guard",
        )

    stock = load_stock(db, user.id)
    messages = cp.build_messages(project, step_index, stock, body.question, body.history)
    try:
        text = cp.clean_for_speech(await chat_text(messages))
        # clean_for_speech never returns empty; guard anyway for safety.
        if not text:
            text = "I'm having trouble answering right now. Please try again."
        return CopilotAnswerOut(answer=text, step_index=step_index, source="ai")
    except MetaAPIError as exc:
        log.error("Copilot Muse call failed: %s", exc)
        return CopilotAnswerOut(
            answer=cp.fallback_answer(project, step_index), step_index=step_index, source="fallback"
        )


ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


@router.post("/chat", response_model=CopilotChatOut)
async def chat(
    message: str = Form("", max_length=cp.MAX_QUESTION_CHARS),
    history: str = Form("[]"),
    use_build: bool = Form(True),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Global copilot: text and/or one photo, with or without a build in progress.
    Sends proposals and advice only; it never changes inventory."""
    if not message.strip() and image is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Say or type something, or attach a photo.")
    if not _limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many questions; wait a moment.")

    # Which build (if any) gives context?
    build = None
    if use_build:
        build = db.scalar(
            select(BuildSession)
            .where(BuildSession.user_id == user.id, BuildSession.status == "active")
            .order_by(BuildSession.id.desc())
        )
    project = project_dict(db.get(Project, build.project_id)) if build else None
    step_index = cp.step_view(project, build.current_step)["index"] if project else None
    meta = {
        "mode": "build" if project else "general",
        "project_title": project["title"] if project else None,
        "step_index": step_index,
        "total_steps": len(project["steps"]) if project else None,
    }

    # Deterministic safety guard runs BEFORE any model call.
    if cp.needs_safety_override(message):
        return CopilotChatOut(
            answer=cp.safety_override_reply(message),
            source="safety_guard",
            **meta,
        )

    data_url = None
    if image is not None:
        if image.content_type not in ALLOWED_IMAGES:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Attach a JPEG, PNG or WebP photo.")
        raw = await image.read(MAX_IMAGE_BYTES + 1)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is empty or larger than 6 MB.")
        try:
            jpeg = await asyncio.to_thread(lambda: full_to_jpeg(load_image(raw)))
        except OSError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not read that photo.")
        data_url = image_data_url(jpeg)

    stock = load_stock(db, user.id)
    matches, _ = recommend([project_dict(p) for p in db.scalars(select(Project)).all()], stock)
    messages = cp.build_chat_messages(
        project=project, step_index=step_index or 0, stock=stock, options=cp.options_summary(matches),
        question=message, history=cp.parse_history(history), image_data_url=data_url,
    )
    try:
        text = cp.clean_for_speech(await chat_text(messages, max_completion_tokens=4000))
        # clean_for_speech never returns empty; guard anyway for safety.
        if not text:
            text = "I'm having trouble answering right now. Please try again."
        return CopilotChatOut(answer=text, source="ai", **meta)
    except MetaAPIError as exc:
        log.error("Copilot chat Muse call failed: %s", exc)
        fallback = (
            cp.fallback_answer(project, step_index or 0)
            if project
            else "I'm having trouble answering right now. Please try again."
        )
        return CopilotChatOut(answer=fallback, source="fallback", **meta)
