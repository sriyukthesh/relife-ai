import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.database import Base


class TimelineRow(Base):
    """Per-user timeline state stored alongside the app's existing data."""
    __tablename__ = "sl_timelines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    payload_json: Mapped[str] = mapped_column(Text)


def _key(user_id: int) -> str:
    return f"user:{user_id}"


def load(db: Session, user_id: int):
    row = db.get(TimelineRow, _key(user_id))
    return json.loads(row.payload_json) if row else None


def save(db: Session, user_id: int, timeline: dict):
    row = db.get(TimelineRow, _key(user_id))
    payload = json.dumps(timeline)
    if row:
        row.payload_json = payload
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(TimelineRow(id=_key(user_id), payload_json=payload))
    db.commit()
