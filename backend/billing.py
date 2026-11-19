from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


class BillingError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error
    if value < 1:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


def _money(name: str, default: str) -> str:
    value = os.getenv(name, default)
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise RuntimeError(f"{name} must be a valid amount.") from error
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return f"{parsed:.2f}"


@dataclass(frozen=True)
class BillingSettings:
    paypal_environment: str = field(default_factory=lambda: os.getenv("PAYPAL_ENVIRONMENT", "sandbox").strip().lower())
    paypal_client_id: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_ID", "").strip())
    paypal_client_secret: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_SECRET", "").strip())
    paypal_webhook_id: str = field(default_factory=lambda: os.getenv("PAYPAL_WEBHOOK_ID", "").strip())
    paypal_plus_plan_id: str = field(default_factory=lambda: os.getenv("PAYPAL_PLUS_PLAN_ID", "").strip())
    paypal_pro_plan_id: str = field(default_factory=lambda: os.getenv("PAYPAL_PRO_PLAN_ID", "").strip())
    free_monthly_documents: int = field(default_factory=lambda: _positive_int("BILLING_FREE_MONTHLY_DOCUMENTS", 5))
    free_monthly_pages: int = field(default_factory=lambda: _positive_int("BILLING_FREE_MONTHLY_PAGES", 20))
    free_max_pages_per_document: int = field(
        default_factory=lambda: _positive_int("BILLING_FREE_MAX_PAGES_PER_DOCUMENT", 5)
    )
    plus_monthly_documents: int = field(default_factory=lambda: _positive_int("BILLING_PLUS_MONTHLY_DOCUMENTS", 100))
    plus_monthly_pages: int = field(default_factory=lambda: _positive_int("BILLING_PLUS_MONTHLY_PAGES", 200))
    plus_max_pages_per_document: int = field(
        default_factory=lambda: _positive_int("BILLING_PLUS_MAX_PAGES_PER_DOCUMENT", 15)
    )
    plus_max_files_per_batch: int = field(
        default_factory=lambda: _positive_int("BILLING_PLUS_MAX_FILES_PER_BATCH", 25)
    )
    plus_price_usd: str = field(default_factory=lambda: _money("BILLING_PLUS_PRICE_USD", "9.00"))
    pro_monthly_documents: int = field(default_factory=lambda: _positive_int("BILLING_PRO_MONTHLY_DOCUMENTS", 300))
    pro_monthly_pages: int = field(default_factory=lambda: _positive_int("BILLING_PRO_MONTHLY_PAGES", 500))
    pro_max_pages_per_document: int = field(
        default_factory=lambda: _positive_int("BILLING_PRO_MAX_PAGES_PER_DOCUMENT", 30)
    )
    pro_max_files_per_batch: int = field(
        default_factory=lambda: _positive_int("BILLING_PRO_MAX_FILES_PER_BATCH", 100)
    )
    pro_price_usd: str = field(default_factory=lambda: _money("BILLING_PRO_PRICE_USD", "19.00"))
    currency: str = field(default_factory=lambda: os.getenv("BILLING_CURRENCY", "USD").strip().upper())

    def __post_init__(self) -> None:
        if self.paypal_environment not in {"sandbox", "live"}:
            raise RuntimeError("PAYPAL_ENVIRONMENT must be sandbox or live.")
        if not self.free_monthly_documents < self.plus_monthly_documents < self.pro_monthly_documents:
            raise RuntimeError("Document allowances must increase from Free to Plus to Pro.")
        if self.free_monthly_pages < self.free_max_pages_per_document:
            raise RuntimeError("The Free monthly page allowance must cover at least one maximum-size Free document.")
        if self.plus_monthly_pages < self.plus_max_pages_per_document:
            raise RuntimeError("The Plus monthly page allowance must cover at least one maximum-size Plus document.")
        if self.pro_monthly_pages < self.pro_max_pages_per_document:
            raise RuntimeError("The Pro monthly page allowance must cover at least one maximum-size Pro document.")
        if not self.free_max_pages_per_document < self.plus_max_pages_per_document < self.pro_max_pages_per_document:
            raise RuntimeError("Per-document page limits must increase from Free to Plus to Pro.")
        if self.plus_max_files_per_batch >= self.pro_max_files_per_batch:
            raise RuntimeError("The Pro batch limit must exceed the Plus batch limit.")
        if self.currency != "USD":
            raise RuntimeError("The initial ReceiptSift billing integration supports USD only.")

    @property
    def api_base_url(self) -> str:
        return "https://api-m.paypal.com" if self.paypal_environment == "live" else "https://api-m.sandbox.paypal.com"

    @property
    def configured(self) -> bool:
        return bool(
            self.paypal_client_id
            and self.paypal_client_secret
            and self.paypal_plus_plan_id
            and self.paypal_pro_plan_id
        )

    def public_config(self) -> dict[str, Any]:
        return {
            "provider": "paypal",
            "environment": self.paypal_environment,
            "client_id": self.paypal_client_id,
            "plans": {
                "free": {
                    "code": "free",
                    "price": "0.00",
                    "currency": self.currency,
                    "monthly_documents": self.free_monthly_documents,
                    "monthly_pages": self.free_monthly_pages,
                    "max_pages_per_document": self.free_max_pages_per_document,
                    "max_files_per_batch": 0,
                },
                "plus": {
                    "code": "plus",
                    "price": self.plus_price_usd,
                    "currency": self.currency,
                    "monthly_documents": self.plus_monthly_documents,
                    "monthly_pages": self.plus_monthly_pages,
                    "max_pages_per_document": self.plus_max_pages_per_document,
                    "max_files_per_batch": self.plus_max_files_per_batch,
                    "paypal_plan_id": self.paypal_plus_plan_id,
                },
                "pro": {
                    "code": "pro",
                    "price": self.pro_price_usd,
                    "currency": self.currency,
                    "monthly_documents": self.pro_monthly_documents,
                    "monthly_pages": self.pro_monthly_pages,
                    "max_pages_per_document": self.pro_max_pages_per_document,
                    "max_files_per_batch": self.pro_max_files_per_batch,
                    "paypal_plan_id": self.paypal_pro_plan_id,
                },
            },
            "overage_policy": "hard_limit",
            "checkout_available": self.configured,
        }


@dataclass(frozen=True)
class Entitlement:
    plan_code: str
    monthly_document_limit: int
    documents_used: int
    monthly_page_limit: int | None
    pages_used: int
    max_pages_per_document: int
    max_files_per_batch: int

    @property
    def documents_remaining(self) -> int:
        return max(self.monthly_document_limit - self.documents_used, 0)

    @property
    def pages_remaining(self) -> int | None:
        if self.monthly_page_limit is None:
            return None
        return max(self.monthly_page_limit - self.pages_used, 0)

    @property
    def allowed(self) -> bool:
        documents_available = self.documents_used < self.monthly_document_limit
        pages_available = self.monthly_page_limit is None or self.pages_used < self.monthly_page_limit
        return documents_available and pages_available

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan_code,
            "monthly_document_limit": self.monthly_document_limit,
            "documents_used": self.documents_used,
            "documents_remaining": self.documents_remaining,
            "monthly_page_limit": self.monthly_page_limit,
            "pages_used": self.pages_used,
            "pages_remaining": self.pages_remaining,
            "max_pages_per_document": self.max_pages_per_document,
            "max_files_per_batch": self.max_files_per_batch,
            "allowed": self.allowed,
            "overage_policy": "hard_limit",
        }


def entitlement(
    settings: BillingSettings,
    subscription_status: str | None,
    monthly_documents: int,
    monthly_pages: int = 0,
    subscription_plan_code: str | None = None,
) -> Entitlement:
    paid_plan = subscription_plan_code if subscription_status == "ACTIVE" else None
    if paid_plan not in {"plus", "pro"}:
        paid_plan = "pro" if subscription_status == "ACTIVE" else "free"
    plan_limits = {
        "free": (
            settings.free_monthly_documents,
            settings.free_monthly_pages,
            settings.free_max_pages_per_document,
            0,
        ),
        "plus": (
            settings.plus_monthly_documents,
            settings.plus_monthly_pages,
            settings.plus_max_pages_per_document,
            settings.plus_max_files_per_batch,
        ),
        "pro": (
            settings.pro_monthly_documents,
            settings.pro_monthly_pages,
            settings.pro_max_pages_per_document,
            settings.pro_max_files_per_batch,
        ),
    }
    document_limit, page_limit, per_document_limit, batch_limit = plan_limits[paid_plan]
    return Entitlement(
        plan_code=paid_plan,
        monthly_document_limit=document_limit,
        documents_used=max(int(monthly_documents), 0),
        monthly_page_limit=page_limit,
        pages_used=max(int(monthly_pages), 0),
        max_pages_per_document=per_document_limit,
        max_files_per_batch=batch_limit,
    )


Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, dict[str, Any]]]


class PayPalClient:
    def __init__(self, settings: BillingSettings, transport: Transport | None = None) -> None:
        self.settings = settings
        self.transport = transport or self._urllib_transport
        self._access_token = ""
        self._access_token_expires_at = 0.0

    @staticmethod
    def _urllib_transport(
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = response.read()
                return response.status, json.loads(payload) if payload else {}
        except urllib.error.HTTPError as error:
            payload = error.read()
            try:
                detail = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                detail = {"message": payload.decode("utf-8", errors="replace")}
            return error.code, detail
        except urllib.error.URLError as error:
            raise BillingError("paypal_unavailable", "PayPal could not be reached.") from error

    def _token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at - 60:
            return self._access_token
        if not self.settings.paypal_client_id or not self.settings.paypal_client_secret:
            raise BillingError("paypal_not_configured", "PayPal server credentials are not configured.", 503)
        credentials = f"{self.settings.paypal_client_id}:{self.settings.paypal_client_secret}".encode()
        status_code, payload = self.transport(
            "POST",
            f"{self.settings.api_base_url}/v1/oauth2/token",
            {
                "Accept": "application/json",
                "Accept-Language": "en_US",
                "Authorization": f"Basic {base64.b64encode(credentials).decode()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            b"grant_type=client_credentials",
        )
        if status_code != 200 or not payload.get("access_token"):
            raise BillingError("paypal_auth_failed", "PayPal rejected the server credentials.")
        self._access_token = str(payload["access_token"])
        self._access_token_expires_at = time.time() + int(payload.get("expires_in", 300))
        return self._access_token

    def _api(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        status_code, response = self.transport(
            method,
            f"{self.settings.api_base_url}{path}",
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": os.urandom(16).hex(),
            },
            body,
        )
        if not 200 <= status_code < 300:
            debug_id = response.get("debug_id")
            suffix = f" PayPal debug ID: {debug_id}." if debug_id else ""
            raise BillingError("paypal_api_error", f"PayPal rejected the request.{suffix}")
        return response

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        if not subscription_id or len(subscription_id) > 64:
            raise BillingError("invalid_subscription_id", "Invalid PayPal subscription ID.", 400)
        return self._api("GET", f"/v1/billing/subscriptions/{subscription_id}")

    def cancel_subscription(self, subscription_id: str, reason: str = "Cancelled by the customer") -> None:
        self._api("POST", f"/v1/billing/subscriptions/{subscription_id}/cancel", {"reason": reason[:128]})

    def refund_sale(self, sale_id: str, amount: str, currency: str, reason: str) -> dict[str, Any]:
        if not sale_id or len(sale_id) > 64 or not sale_id.replace("-", "").isalnum():
            raise BillingError("invalid_payment_id", "Invalid PayPal payment ID.", 400)
        try:
            parsed = Decimal(amount)
        except InvalidOperation as error:
            raise BillingError("invalid_refund_amount", "Enter a valid refund amount.", 400) from error
        if parsed <= 0:
            raise BillingError("invalid_refund_amount", "Refund amount must be greater than zero.", 400)
        normalized_currency = currency.strip().upper()
        if normalized_currency != self.settings.currency:
            raise BillingError("invalid_refund_currency", "Refund currency must match the original payment.", 400)
        return self._api(
            "POST",
            f"/v1/payments/sale/{sale_id}/refund",
            {
                "amount": {"total": f"{parsed:.2f}", "currency": normalized_currency},
                "description": reason[:127],
            },
        )

    def verify_webhook(self, headers: Mapping[str, str], event: dict[str, Any]) -> bool:
        if not self.settings.paypal_webhook_id:
            raise BillingError("paypal_webhook_not_configured", "The PayPal webhook ID is not configured.", 503)
        normalized = {key.lower(): value for key, value in headers.items()}
        required = {
            "auth_algo": normalized.get("paypal-auth-algo"),
            "cert_url": normalized.get("paypal-cert-url"),
            "transmission_id": normalized.get("paypal-transmission-id"),
            "transmission_sig": normalized.get("paypal-transmission-sig"),
            "transmission_time": normalized.get("paypal-transmission-time"),
        }
        if any(not value for value in required.values()):
            return False
        response = self._api(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            {**required, "webhook_id": self.settings.paypal_webhook_id, "webhook_event": event},
        )
        return response.get("verification_status") == "SUCCESS"

    def create_product(self, name: str = "ReceiptSift") -> dict[str, Any]:
        return self._api(
            "POST",
            "/v1/catalogs/products",
            {"name": name, "description": "PDF bill and receipt extraction subscription", "type": "SERVICE", "category": "SOFTWARE"},
        )

    def create_monthly_plan(self, product_id: str, plan_code: str) -> dict[str, Any]:
        if plan_code == "plus":
            name = "ReceiptSift Plus Monthly"
            documents = self.settings.plus_monthly_documents
            pages = self.settings.plus_monthly_pages
            price = self.settings.plus_price_usd
        elif plan_code == "pro":
            name = "ReceiptSift Pro Monthly"
            documents = self.settings.pro_monthly_documents
            pages = self.settings.pro_monthly_pages
            price = self.settings.pro_price_usd
        else:
            raise BillingError("invalid_plan", "Only Plus and Pro PayPal plans can be created.", 400)
        return self._api(
            "POST",
            "/v1/billing/plans",
            {
                "product_id": product_id,
                "name": name,
                "description": (
                    f"Up to {documents} PDF documents and {pages} pages per month"
                ),
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,
                        "pricing_scheme": {
                            "fixed_price": {"value": price, "currency_code": self.settings.currency}
                        },
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee": {"value": "0.00", "currency_code": self.settings.currency},
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3,
                },
            },
        )

    def create_webhook(self, url: str) -> dict[str, Any]:
        return self._api(
            "POST",
            "/v1/notifications/webhooks",
            {
                "url": url,
                "event_types": [
                    {"name": "BILLING.SUBSCRIPTION.ACTIVATED"},
                    {"name": "BILLING.SUBSCRIPTION.UPDATED"},
                    {"name": "BILLING.SUBSCRIPTION.SUSPENDED"},
                    {"name": "BILLING.SUBSCRIPTION.CANCELLED"},
                    {"name": "BILLING.SUBSCRIPTION.EXPIRED"},
                    {"name": "PAYMENT.SALE.COMPLETED"},
                    {"name": "PAYMENT.SALE.DENIED"},
                    {"name": "PAYMENT.SALE.REFUNDED"},
                    {"name": "PAYMENT.SALE.REVERSED"},
                ],
            },
        )
