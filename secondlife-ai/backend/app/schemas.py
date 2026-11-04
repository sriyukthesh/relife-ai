from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from . import catalog

Condition = Literal["unverified", "tested_ok", "suspect_damaged"]
Source = Literal["scan", "manual", "marketplace"]


# ---- auth ----
class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- inventory ----
class InventoryItemIn(BaseModel):
    category: str
    label: str = Field(min_length=1, max_length=120)
    specs: dict[str, Any] = Field(default_factory=dict)
    quantity: int = Field(1, ge=1, le=10000)
    condition: Condition = "unverified"
    source: Source = "manual"
    ai_confidence: float | None = Field(None, ge=0, le=1)
    ai_notes: str | None = Field(None, max_length=1000)
    # Server-enforced rule: nothing enters inventory unless the user confirmed it.
    confirmed_by_user: bool = False

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in catalog.CATEGORIES:
            raise ValueError(f"Unknown category '{v}'")
        return v


class InventoryItemPatch(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=120)
    specs: dict[str, Any] | None = None
    quantity: int | None = Field(None, ge=1, le=10000)
    condition: Condition | None = None


class InventoryItemOut(BaseModel):
    id: int
    category: str
    label: str
    specs: dict[str, Any]
    quantity: int
    condition: str
    source: str
    ai_confidence: float | None
    ai_notes: str | None
    confirmed_at: datetime
    missing_specs: list[str]
    usable: bool


# ---- projects / recommendations ----
class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    difficulty: int
    estimated_minutes: int
    description: str
    safety_note: str | None


class ProjectDetailOut(ProjectOut):
    requirements: list[dict[str, Any]]
    steps: list[dict[str, Any]]


class AllocationOut(BaseModel):
    item_id: int
    label: str
    quantity: int
    condition: str


class RequirementResultOut(BaseModel):
    index: int
    label: str
    category: str
    needed: int
    allocated: list[AllocationOut]
    missing: int
    status: str
    constraints: dict[str, Any]
    warnings: list[str]


class MissingPartOut(BaseModel):
    label: str
    category: str
    quantity: int
    constraints: dict[str, Any]


class ProjectMatchOut(BaseModel):
    project_id: int
    slug: str
    title: str
    difficulty: int
    estimated_minutes: int
    description: str
    can_build: bool
    coverage: float
    requirements: list[RequirementResultOut]
    missing_parts: list[MissingPartOut]
    warnings: list[str]


class ExcludedItemOut(BaseModel):
    id: int
    label: str
    reason: str


class RecommendationsOut(BaseModel):
    matches: list[ProjectMatchOut]
    excluded_items: list[ExcludedItemOut]


# ---- build sessions + copilot (Phase 3) ----
class BuildStartIn(BaseModel):
    project_slug: str
    # Allow starting even though parts are missing (the UI asks the user first).
    allow_incomplete: bool = False


class StepOut(BaseModel):
    index: int
    title: str
    instruction: str


class BuildOut(BaseModel):
    id: int
    project_slug: str
    title: str
    status: str
    current_step: int
    total_steps: int
    step: StepOut
    is_last: bool
    safety_note: str | None
    warnings: list[str]
    missing_parts: list[MissingPartOut]


class CopilotAskIn(BaseModel):
    build_id: int
    question: str = Field(min_length=1, max_length=500)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


class CopilotAnswerOut(BaseModel):
    answer: str
    step_index: int
    source: Literal["ai", "safety_guard", "fallback"]


# ---- marketplace (Phase 5) ----
class ListingIn(BaseModel):
    item_id: int
    quantity: int = Field(1, ge=1, le=10000)
    price_cents: int = Field(ge=1, le=10_000_000)
    title: str | None = Field(None, max_length=120)  # optional friendlier name for the listing


class ListingOut(BaseModel):
    id: int
    seller_id: int
    seller_name: str
    category: str
    label: str
    specs: dict[str, Any]
    quantity: int
    price_cents: int
    condition: str  # seller's claim; buyers still receive it as "unverified"
    status: str
    mine: bool
    created_at: datetime


class BuyIn(BaseModel):
    quantity: int = Field(1, ge=1, le=10000)


class OrderOut(BaseModel):
    id: int
    listing_id: int
    label: str
    quantity: int
    total_cents: int
    status: str
    created_at: datetime
    note: str


class PartOffersOut(BaseModel):
    label: str
    category: str
    quantity: int
    constraints: dict[str, Any]
    offers: list[ListingOut]


class ProjectOffersOut(BaseModel):
    project_slug: str
    parts: list[PartOffersOut]


class ListingSuggestionOut(BaseModel):
    item_id: int
    label: str
    category: str
    specs: dict[str, Any]
    condition: str
    quantity_owned: int
    can_list: bool
    problem: str | None
    suggested_title: str
    suggested_quantity: int
    suggested_price_cents: int
    price_low_cents: int
    price_high_cents: int
    price_basis: str


# ---- dashboard impact ----
class CopilotChatOut(BaseModel):
    answer: str
    source: Literal["ai", "safety_guard", "fallback"]
    mode: Literal["build", "general"]
    project_title: str | None = None
    step_index: int | None = None
    total_steps: int | None = None


# ---- cart and checkout ----
PayMethod = Literal["upi", "card", "netbanking"]


class CartLineIn(BaseModel):
    listing_id: int
    quantity: int = Field(1, ge=1, le=10000)


class CartPreviewIn(BaseModel):
    lines: list[CartLineIn] = Field(default_factory=list, max_length=30)


class PricedLineOut(BaseModel):
    listing_id: int
    label: str
    category: str
    specs: dict[str, Any]
    condition: str
    seller_name: str
    unit_cents: int
    quantity: int            # what will be bought (capped at what is available)
    quantity_available: int
    line_cents: int
    issue: str | None = None


class CartPreviewOut(BaseModel):
    lines: list[PricedLineOut]
    subtotal_cents: int
    delivery_cents: int
    total_cents: int
    free_delivery_from_cents: int
    ok: bool                  # false when any line has an issue or the cart is empty


class AddressIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^\d{10}$")
    line1: str = Field(min_length=5, max_length=120)
    city: str = Field(min_length=2, max_length=60)
    pincode: str = Field(pattern=r"^\d{6}$")


class CheckoutIn(BaseModel):
    lines: list[CartLineIn] = Field(min_length=1, max_length=30)
    address: AddressIn
    method: PayMethod
    idempotency_key: str = Field(min_length=8, max_length=64)  # a retry never pays twice
    simulate_decline: bool = False  # demo switch to see a failed payment


class PaymentLineOut(BaseModel):
    order_id: int
    listing_id: int
    label: str
    quantity: int
    unit_cents: int
    line_cents: int
    seller_name: str


class PaymentOut(BaseModel):
    id: int
    reference: str
    method: str
    method_label: str
    status: str
    subtotal_cents: int
    delivery_cents: int
    total_cents: int
    address: dict[str, Any]
    lines: list[PaymentLineOut]
    created_at: datetime
    note: str
