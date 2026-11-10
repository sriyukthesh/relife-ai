"""PayPal Orders v2 client. This integration is deliberately restricted to sandbox."""
from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from ..config import get_settings

PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com"


class PayPalError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


_token: dict[str, Any] = {"value": None, "expires_at": 0.0}


def _request_id(action: str, user_id: int, idempotency_key: str) -> str:
    value = f"{action}:{user_id}:{idempotency_key}".encode()
    return hashlib.sha256(value).hexdigest()[:32]


def _access_token() -> str:
    settings = get_settings()
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise PayPalError("PayPal sandbox credentials are not configured", 503)
    try:
        response = httpx.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
            headers={"Accept": "application/json"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise PayPalError("Could not reach PayPal sandbox") from exc
    if response.status_code != 200:
        raise PayPalError("PayPal sandbox authentication failed")
    try:
        body = response.json()
        token = body["access_token"]
        expires_in = int(body.get("expires_in", 300))
    except (ValueError, KeyError, TypeError) as exc:
        raise PayPalError("PayPal returned an invalid authentication response") from exc
    if not isinstance(token, str) or not token or expires_in <= 0:
        raise PayPalError("PayPal returned an invalid authentication response")
    _token["value"] = token
    _token["expires_at"] = time.time() + expires_in
    return token


def _api_request(method: str, path: str, *, payload: dict[str, Any] | None = None, request_id: str) -> dict[str, Any]:
    try:
        response = httpx.request(
            method,
            f"{PAYPAL_BASE_URL}{path}",
            json=payload,
            headers={
                "Authorization": f"Bearer {_access_token()}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": request_id,
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise PayPalError("Could not reach PayPal sandbox") from exc
    if response.status_code >= 400:
        raise PayPalError("PayPal sandbox rejected the payment request")
    try:
        body = response.json()
    except ValueError as exc:
        raise PayPalError("PayPal returned an invalid response") from exc
    if not isinstance(body, dict):
        raise PayPalError("PayPal returned an invalid response")
    return body


def _amount(cents: int, currency: str) -> dict[str, str]:
    return {"currency_code": currency, "value": f"{cents // 100}.{cents % 100:02d}"}


def create_order(
    *,
    user_id: int,
    idempotency_key: str,
    lines: list[dict[str, Any]],
    subtotal_cents: int,
    delivery_cents: int,
    total_cents: int,
    currency: str,
    reference_id: str,
) -> dict[str, Any]:
    amount = {
        **_amount(total_cents, currency),
        "breakdown": {
            "item_total": _amount(subtotal_cents, currency),
            "shipping": _amount(delivery_cents, currency),
        },
    }
    return _api_request(
        "POST",
        "/v2/checkout/orders",
        payload={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference_id,
                "description": "ReLife AI marketplace purchase",
                "amount": amount,
                "items": [{
                    "name": line["label"][:127],
                    "unit_amount": _amount(line["unit_cents"], currency),
                    "quantity": str(line["quantity"]),
                    "category": "PHYSICAL_GOODS",
                } for line in lines],
            }],
        },
        request_id=_request_id("create", user_id, idempotency_key),
    )


def capture_order(*, paypal_order_id: str, user_id: int, idempotency_key: str) -> dict[str, Any]:
    return _api_request(
        "POST",
        f"/v2/checkout/orders/{paypal_order_id}/capture",
        payload={},
        request_id=_request_id("capture", user_id, idempotency_key),
    )
