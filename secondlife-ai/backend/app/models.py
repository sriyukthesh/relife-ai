from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """One unified account type: every user can own inventory, sell and buy."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InventoryItem(Base):
    """Only USER-CONFIRMED components live here. AI proposals never do."""
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(120))
    specs: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    condition: Mapped[str] = mapped_column(String(24), default="unverified")
    source: Mapped[str] = mapped_column(String(24), default="manual")
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1 easy .. 3 hard
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    description: Mapped[str] = mapped_column(Text)
    safety_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)


class BuildSession(Base):
    """The user's current build; gives the copilot its project + step context (Phase 3)."""
    __tablename__ = "build_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Listing(Base):
    """Marketplace listing (Phase 5)."""
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(120))
    specs: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price_cents: Mapped[int] = mapped_column(Integer)
    condition: Mapped[str] = mapped_column(String(24), default="unverified")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | sold | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    """One checkout: a receipt that groups the orders created together.
    New table (created by create_all); nothing existing is altered. No card data is ever stored."""
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_payment_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(12), default="paid")
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    delivery_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer)
    address: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    lines: Mapped[list[Any]] = mapped_column(JSON_TYPE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
