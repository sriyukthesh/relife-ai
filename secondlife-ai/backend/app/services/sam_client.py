"""SAM 3.1 adapter.

STATUS: the real SAM 3.1 call is NOT implemented because its request/response
format was not verified (reported: Responses API, streamed, concept-text prompt,
custom line-based output). Paste the official docs section and this gets
completed. Until then segment() returns no segments and the inspector analyses
the whole image instead.

Enable later with SAM_ENABLED=true once _segment_with_sam is implemented.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image


@dataclass
class Segment:
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels of the analysed image
    score: float
    mask_png: bytes | None = None


class SamUnavailable(RuntimeError):
    pass


async def _segment_with_sam(img: Image.Image) -> list[Segment]:
    # TODO(docs needed): send img + concept text such as "electronic component",
    # parse the streamed output into boxes/masks/scores.
    raise SamUnavailable("SAM 3.1 call not implemented yet")


async def segment(img: Image.Image) -> tuple[list[Segment], str, list[str]]:
    """Return (segments, mode, notes). mode is 'sam' or 'whole_image'."""
    if os.getenv("SAM_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return [], "whole_image", ["Segmentation is off; the whole photo was analysed at once."]
    segments = await _segment_with_sam(img)
    return segments, "sam", []
