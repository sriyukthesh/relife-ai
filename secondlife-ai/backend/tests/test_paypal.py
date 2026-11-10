from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import InventoryItem, Listing, Order, Payment, User
from app.routers import checkout, marketplace
from app.security import get_current_user
from app.services import paypal


class FakeResponse:
    status_code = 201

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def test_create_order_uses_server_amount_and_request_id(monkeypatch):
    monkeypatch.setattr(paypal, "_access_token", lambda: "sandbox-token")
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return FakeResponse({"id": "ORDER-123"})

    monkeypatch.setattr(paypal.httpx, "request", fake_request)
    result = paypal.create_order(
        user_id=4,
        idempotency_key="stable-checkout-key",
        lines=[{"label": "LED", "unit_cents": 300, "quantity": 2}],
        subtotal_cents=600,
        delivery_cents=4000,
        total_cents=4600,
        currency="USD",
        reference_id="SL-20",
    )

    assert result["id"] == "ORDER-123"
    assert captured["method"] == "POST"
    assert captured["url"] == f"{paypal.PAYPAL_BASE_URL}/v2/checkout/orders"
    assert captured["headers"]["Authorization"] == "Bearer sandbox-token"
    assert len(captured["headers"]["PayPal-Request-Id"]) <= 38
    amount = captured["json"]["purchase_units"][0]["amount"]
    assert amount == {
        "currency_code": "USD",
        "value": "46.00",
        "breakdown": {
            "item_total": {"currency_code": "USD", "value": "6.00"},
            "shipping": {"currency_code": "USD", "value": "40.00"},
        },
    }


def test_capture_uses_same_deterministic_request_id_on_retry(monkeypatch):
    monkeypatch.setattr(paypal, "_access_token", lambda: "sandbox-token")
    request_ids = []

    def fake_request(method, url, **kwargs):
        request_ids.append(kwargs["headers"]["PayPal-Request-Id"])
        return FakeResponse({"status": "COMPLETED"})

    monkeypatch.setattr(paypal.httpx, "request", fake_request)
    args = {"paypal_order_id": "ORDER-123", "user_id": 4, "idempotency_key": "stable-checkout-key"}

    paypal.capture_order(**args)
    paypal.capture_order(**args)

    assert request_ids[0] == request_ids[1]


def test_legacy_simulated_purchase_routes_are_disabled():
    app = FastAPI()
    app.include_router(checkout.router)
    app.include_router(marketplace.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: object()
    client = TestClient(app)

    assert client.post("/checkout/pay").status_code == 410
    assert client.post("/marketplace/listings/1/buy", json={"quantity": 1}).status_code == 410


def test_paypal_capture_creates_one_receipt_and_updates_inventory(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        seller = User(email="seller@example.com", name="Seller", password_hash="unused")
        buyer = User(email="buyer@example.com", name="Buyer", password_hash="unused")
        db.add_all([seller, buyer])
        db.flush()
        listing = Listing(
            seller_id=seller.id,
            category="resistor",
            label="220 ohm resistor",
            specs={"resistance_ohm": 220},
            quantity=1,
            price_cents=300,
            condition="tested_ok",
            status="active",
        )
        db.add(listing)
        db.commit()
        buyer_id = buyer.id
        listing_id = listing.id

    app = FastAPI()
    app.include_router(checkout.router)

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=buyer_id, email="buyer@example.com", name="Buyer", password_hash="unused",
    )
    monkeypatch.setattr(
        checkout,
        "get_settings",
        lambda: SimpleNamespace(
            paypal_client_id="sandbox-client",
            paypal_client_secret="sandbox-secret",
            paypal_currency="USD",
        ),
    )
    created_orders = []
    captured_orders = []
    monkeypatch.setattr(checkout.paypal, "create_order", lambda **kwargs: created_orders.append(kwargs) or {"id": "ORDER-123"})

    def capture_order(**kwargs):
        captured_orders.append(kwargs)
        return {
            "id": "ORDER-123",
            "status": "COMPLETED",
            "purchase_units": [{
                "payments": {
                    "captures": [{
                        "id": "CAPTURE-123",
                        "status": "COMPLETED",
                        "amount": {"value": "43.00", "currency_code": "USD"},
                    }],
                },
            }],
        }

    monkeypatch.setattr(checkout.paypal, "capture_order", capture_order)
    client = TestClient(app)
    body = {
        "lines": [{"listing_id": listing_id, "quantity": 1}],
        "address": {
            "full_name": "Buyer",
            "phone": "1234567890",
            "line1": "123 Main Street",
            "city": "Delhi",
            "pincode": "110001",
        },
        "idempotency_key": "stable-checkout-key",
    }

    first_order = client.post("/checkout/paypal/orders", json=body)
    repeated_order = client.post("/checkout/paypal/orders", json=body)
    assert first_order.status_code == 200
    assert repeated_order.json() == first_order.json()
    assert len(created_orders) == 1

    capture_url = f"/checkout/paypal/orders/{first_order.json()['paypal_order_id']}/capture"
    first_capture = client.post(capture_url)
    repeated_capture = client.post(capture_url)
    assert first_capture.status_code == 200
    assert first_capture.json()["method"] == "paypal"
    assert first_capture.json()["total_cents"] == 4300
    assert repeated_capture.json() == first_capture.json()
    assert len(captured_orders) == 1

    with factory() as db:
        assert len(db.scalars(select(Payment)).all()) == 1
        assert len(db.scalars(select(Order)).all()) == 1
        listing = db.get(Listing, listing_id)
        assert listing.status == "sold" and listing.quantity == 0
        inventory = db.scalars(select(InventoryItem).where(InventoryItem.user_id == buyer_id)).all()
        assert [(item.quantity, item.condition, item.source) for item in inventory] == [(1, "unverified", "marketplace")]
    engine.dispose()
