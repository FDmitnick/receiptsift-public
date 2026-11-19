from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.billing import BillingSettings, PayPalClient, entitlement
from backend.billing_repository import BillingRepository
from backend.billing_router import build_billing_router


def billing_settings() -> BillingSettings:
    return BillingSettings(
        paypal_environment="sandbox",
        paypal_client_id="public-client-id",
        paypal_client_secret="server-secret",
        paypal_webhook_id="WH-test",
        paypal_plus_plan_id="P-plus",
        paypal_pro_plan_id="P-pro",
        free_monthly_documents=2,
        free_monthly_pages=10,
        free_max_pages_per_document=5,
        plus_monthly_documents=100,
        plus_monthly_pages=200,
        plus_max_pages_per_document=15,
        plus_max_files_per_batch=25,
        plus_price_usd="9.00",
        pro_monthly_documents=300,
        pro_monthly_pages=500,
        pro_max_pages_per_document=30,
        pro_max_files_per_batch=100,
        pro_price_usd="19.00",
        currency="USD",
    )


def test_entitlement_grants_pro_only_for_active_subscription():
    settings = billing_settings()

    assert entitlement(settings, None, 1, 4).as_dict() == {
        "plan": "free",
        "monthly_document_limit": 2,
        "documents_used": 1,
        "documents_remaining": 1,
        "monthly_page_limit": 10,
        "pages_used": 4,
        "pages_remaining": 6,
        "max_pages_per_document": 5,
        "max_files_per_batch": 0,
        "allowed": True,
        "overage_policy": "hard_limit",
    }
    assert entitlement(settings, "APPROVAL_PENDING", 2, 5).allowed is False
    assert entitlement(settings, "ACTIVE", 2, 5).plan_code == "pro"
    assert entitlement(settings, "ACTIVE", 2, 5, "plus").plan_code == "plus"
    assert entitlement(settings, "ACTIVE", 2, 5, "plus").documents_remaining == 98
    assert entitlement(settings, "ACTIVE", 2, 5).pages_remaining == 495
    assert entitlement(settings, "ACTIVE", 300, 500).allowed is False
    assert entitlement(settings, "ACTIVE", 299, 500).allowed is False


def test_paypal_client_authenticates_and_validates_webhook():
    calls: list[tuple[str, str, Mapping[str, str], bytes | None]] = []

    def transport(method: str, url: str, headers: Mapping[str, str], body: bytes | None):
        calls.append((method, url, headers, body))
        if url.endswith("/v1/oauth2/token"):
            return 200, {"access_token": "token", "expires_in": 3600}
        if url.endswith("/verify-webhook-signature"):
            return 200, {"verification_status": "SUCCESS"}
        return 200, {"id": "I-test", "plan_id": "P-pro", "status": "ACTIVE", "custom_id": "user-1"}

    client = PayPalClient(billing_settings(), transport=transport)
    subscription = client.get_subscription("I-test")
    verified = client.verify_webhook(
        {
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://api-m.sandbox.paypal.com/cert.pem",
            "paypal-transmission-id": "transmission-1",
            "paypal-transmission-sig": "signature",
            "paypal-transmission-time": "2026-08-21T00:00:00Z",
        },
        {"id": "event-1"},
    )

    assert subscription["status"] == "ACTIVE"
    assert verified is True
    assert sum(url.endswith("/v1/oauth2/token") for _, url, _, _ in calls) == 1
    assert all("server-secret" not in str(body) for _, _, _, body in calls)


def test_billing_repository_upserts_and_deduplicates(tmp_path: Path):
    repository = BillingRepository(tmp_path / "billing.sqlite3")

    created = repository.upsert_paypal(
        user_id="user-1",
        subscription_id="I-test",
        provider_plan_id="P-pro",
        status="ACTIVE",
        payer_email="buyer@example.com",
    )

    assert created["plan_code"] == "pro"
    assert repository.get_by_provider_id("I-test")["user_id"] == "user-1"
    assert repository.claim_webhook_event("event-1", "BILLING.SUBSCRIPTION.ACTIVATED") is True
    assert repository.claim_webhook_event("event-1", "BILLING.SUBSCRIPTION.ACTIVATED") is False
    assert repository.reserve_document("user-1", 2, "reservation-1", requested_pages=5, monthly_page_limit=10) is True
    assert repository.reserve_document("user-1", 2, "reservation-2", requested_pages=6, monthly_page_limit=10) is False
    assert repository.reserve_document("user-1", 2, "reservation-2", requested_pages=5, monthly_page_limit=10) is True
    assert repository.reserve_document("user-1", 2, "reservation-3", requested_pages=1, monthly_page_limit=10) is False
    repository.release_document_reservation("reservation-1")
    repository.release_document_reservation("reservation-2")
    assert repository.reserve_document("user-1", 2, "reservation-3", requested_pages=1, monthly_page_limit=10) is True


class FakePayPal:
    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        return {
            "id": subscription_id,
            "plan_id": "P-pro",
            "status": "ACTIVE",
            "custom_id": "user-1",
            "subscriber": {"email_address": "buyer@example.com"},
            "billing_info": {"next_billing_time": "2026-09-21T00:00:00Z"},
        }

    def verify_webhook(self, _headers: Mapping[str, str], _event: dict[str, Any]) -> bool:
        return True

    def cancel_subscription(self, _subscription_id: str) -> None:
        return None


class FakePlusPayPal(FakePayPal):
    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        subscription = super().get_subscription(subscription_id)
        subscription["plan_id"] = "P-plus"
        return subscription


def test_router_approves_subscription_and_reports_quota(tmp_path: Path):
    app = FastAPI()

    def require_user(_request: Request) -> dict[str, Any]:
        return {"id": "user-1", "email": "user@example.com"}

    def usage_for_user(_user_id: str) -> dict[str, Any]:
        return {"documents_parsed": 12, "pages_processed": 24}

    app.include_router(
        build_billing_router(
            database_path=tmp_path / "app.sqlite3",
            require_user=require_user,
            usage_for_user=usage_for_user,
            settings=billing_settings(),
            paypal=FakePayPal(),  # type: ignore[arg-type]
        )
    )

    with TestClient(app) as client:
        approved = client.post("/api/billing/paypal/approve", json={"subscription_id": "I-test"})
        current = client.get("/api/billing/me")

    assert approved.status_code == 200
    assert approved.json()["entitlement"]["plan"] == "pro"
    assert current.json()["entitlement"]["documents_remaining"] == 288
    assert current.json()["entitlement"]["pages_remaining"] == 476


def test_router_maps_active_plus_plan_to_plus_entitlement(tmp_path: Path):
    app = FastAPI()

    app.include_router(
        build_billing_router(
            database_path=tmp_path / "app.sqlite3",
            require_user=lambda _request: {"id": "user-1", "email": "user@example.com"},
            usage_for_user=lambda _user_id: {"documents_parsed": 12, "pages_processed": 24},
            settings=billing_settings(),
            paypal=FakePlusPayPal(),  # type: ignore[arg-type]
        )
    )

    with TestClient(app) as client:
        approved = client.post("/api/billing/paypal/approve", json={"subscription_id": "I-plus"})

    assert approved.status_code == 200
    assert approved.json()["entitlement"]["plan"] == "plus"
    assert approved.json()["entitlement"]["documents_remaining"] == 88
    assert approved.json()["entitlement"]["pages_remaining"] == 176
    assert approved.json()["entitlement"]["max_files_per_batch"] == 25
