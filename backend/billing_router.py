from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from .billing import BillingError, BillingSettings, Entitlement, PayPalClient, entitlement
from .billing_repository import BillingRepository

CurrentUser = Callable[[Request], dict[str, Any]]
UsageForUser = Callable[[str], dict[str, Any]]
BillingRepositoryProvider = Callable[[], BillingRepository]
EntitlementForUser = Callable[[str], Entitlement]


def _payer_email(subscription: dict[str, Any]) -> str | None:
    value = subscription.get("subscriber", {}).get("email_address")
    return str(value) if value else None


def _period_end(subscription: dict[str, Any]) -> str | None:
    value = subscription.get("billing_info", {}).get("next_billing_time")
    return str(value) if value else None


def _subscription_id_from_event(event: dict[str, Any]) -> str | None:
    resource = event.get("resource") or {}
    resource_type = str(event.get("resource_type", "")).lower()
    if resource_type == "subscription" or str(event.get("event_type", "")).startswith("BILLING.SUBSCRIPTION."):
        return str(resource.get("id", "")) or None
    value = resource.get("billing_agreement_id")
    return str(value) if value else None


def build_billing_router(
    *,
    database_path: Path,
    require_user: CurrentUser,
    usage_for_user: UsageForUser,
    settings: BillingSettings | None = None,
    paypal: PayPalClient | None = None,
    repository_provider: BillingRepositoryProvider | None = None,
    entitlement_for_user: EntitlementForUser | None = None,
) -> APIRouter:
    billing_settings = settings or BillingSettings()
    default_repository = BillingRepository(database_path)
    paypal_client = paypal or PayPalClient(billing_settings)
    router = APIRouter(prefix="/api/billing", tags=["billing"])

    def billing_repository() -> BillingRepository:
        return repository_provider() if repository_provider else default_repository

    def billing_error(error: BillingError) -> HTTPException:
        return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)})

    def current_entitlement(user_id: str, subscription: dict[str, Any] | None = None) -> Entitlement:
        if entitlement_for_user is not None:
            return entitlement_for_user(user_id)
        current_subscription = subscription if subscription is not None else billing_repository().get_for_user(user_id)
        usage = usage_for_user(user_id)
        return entitlement(
            billing_settings,
            current_subscription.get("status") if current_subscription else None,
            int(usage.get("documents_parsed", 0)),
            int(usage.get("pages_processed", 0)),
            current_subscription.get("plan_code") if current_subscription else None,
        )

    def store_subscription(user_id: str, subscription: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(subscription.get("plan_id", ""))
        plan_code = {
            billing_settings.paypal_plus_plan_id: "plus",
            billing_settings.paypal_pro_plan_id: "pro",
        }.get(plan_id)
        if plan_code is None:
            raise BillingError("paypal_plan_mismatch", "The PayPal subscription does not match a ReceiptSift plan.", 400)
        custom_id = subscription.get("custom_id")
        if custom_id and str(custom_id) != user_id:
            raise BillingError("paypal_owner_mismatch", "The PayPal subscription belongs to a different account.", 403)
        return billing_repository().upsert_paypal(
            user_id=user_id,
            subscription_id=str(subscription["id"]),
            provider_plan_id=plan_id,
            plan_code=plan_code,
            status=str(subscription.get("status", "UNKNOWN")),
            payer_email=_payer_email(subscription),
            current_period_end=_period_end(subscription),
        )

    @router.get("/config")
    def billing_config() -> dict[str, Any]:
        return billing_settings.public_config()

    @router.get("/me")
    def my_billing(request: Request) -> dict[str, Any]:
        user = require_user(request)
        subscription = billing_repository().get_for_user(user["id"])
        current = current_entitlement(user["id"], subscription)
        return {"subscription": subscription, "entitlement": current.as_dict()}

    @router.post("/paypal/approve")
    async def approve_paypal_subscription(
        request: Request,
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, Any]:
        user = require_user(request)
        try:
            subscription = await run_in_threadpool(paypal_client.get_subscription, str(payload.get("subscription_id", "")))
            stored = store_subscription(user["id"], subscription)
        except BillingError as error:
            raise billing_error(error) from error
        current = current_entitlement(user["id"], stored)
        return {"subscription": stored, "entitlement": current.as_dict()}

    @router.post("/paypal/cancel", status_code=status.HTTP_202_ACCEPTED)
    async def cancel_paypal_subscription(request: Request) -> dict[str, Any]:
        user = require_user(request)
        subscription = billing_repository().get_for_user(user["id"])
        if subscription is None:
            raise HTTPException(status_code=404, detail={"code": "subscription_not_found", "message": "No subscription found."})
        try:
            await run_in_threadpool(paypal_client.cancel_subscription, subscription["provider_subscription_id"])
        except BillingError as error:
            raise billing_error(error) from error
        return {"accepted": True}

    @router.post("/paypal/webhook")
    async def paypal_webhook(request: Request) -> dict[str, Any]:
        try:
            event = await request.json()
        except ValueError as error:
            raise HTTPException(status_code=400, detail={"code": "invalid_webhook", "message": "Invalid JSON."}) from error
        try:
            verified = await run_in_threadpool(paypal_client.verify_webhook, request.headers, event)
        except BillingError as error:
            raise billing_error(error) from error
        if not verified:
            raise HTTPException(status_code=400, detail={"code": "invalid_webhook_signature", "message": "Invalid signature."})
        event_id = str(event.get("id", ""))
        event_type = str(event.get("event_type", ""))
        if billing_repository().has_webhook_event(event_id):
            return {"received": True, "duplicate": True}
        subscription_id = _subscription_id_from_event(event)
        if subscription_id is None:
            billing_repository().claim_webhook_event(event_id, event_type)
            return {"received": True, "handled": False}
        payment = None
        if event_type.startswith("PAYMENT.SALE."):
            payment = billing_repository().upsert_payment_event(event_type, event)
        try:
            subscription = await run_in_threadpool(paypal_client.get_subscription, subscription_id)
        except BillingError as error:
            raise billing_error(error) from error
        existing = billing_repository().get_by_provider_id(subscription_id)
        if existing is None:
            billing_repository().claim_webhook_event(event_id, event_type)
            return {"received": True, "handled": False}
        try:
            store_subscription(existing["user_id"], subscription)
        except BillingError as error:
            raise billing_error(error) from error
        billing_repository().claim_webhook_event(event_id, event_type)
        return {"received": True, "handled": True, "payment_recorded": payment is not None}

    return router
