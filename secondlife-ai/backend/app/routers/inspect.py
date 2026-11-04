"""POST /inspect: upload a photo, get component PROPOSALS. Nothing is saved."""
import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.security import get_current_user
from app.services.inspector import InspectResponse, inspect_image
from app.services.meta_client import MetaAPIError

router = APIRouter(prefix="/inspect", tags=["inspect"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 10 * 1024 * 1024


@router.post("", response_model=InspectResponse)
async def inspect_photo(file: UploadFile = File(...), user=Depends(get_current_user)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image is larger than 10 MB.")
    if not data:
        raise HTTPException(400, "Empty file.")
    try:
        return await inspect_image(data)
    except MetaAPIError as exc:
        # Log details server-side; keep the client message generic.
        import logging

        logging.getLogger("secondlife.inspect").error("Muse call failed: %s", exc)
        raise HTTPException(502, "The inspection service is temporarily unavailable. You can still add parts manually.")
    except OSError:
        raise HTTPException(400, "Could not read that image.")
