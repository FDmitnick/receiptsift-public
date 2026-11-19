from __future__ import annotations

import base64
import copy
import hmac
import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from . import __version__
from .atlas_parser import AtlasParseError
from .auth import (
    COOKIE_NAME,
    DUMMY_PASSWORD_HASH,
    LEGACY_COOKIE_NAME,
    auth_token_digest,
    create_auth_token,
    create_session,
    hash_password,
    normalize_email,
    session_identity,
    verify_password,
)
from .batch_repository import BatchRepository, BatchStorageError
from .batch_worker import BatchWorker, ProgressCallback
from .billing import BillingError, BillingSettings, Entitlement, PayPalClient, entitlement
from .billing_repository import BillingRepository
from .billing_router import build_billing_router
from .config import settings
from .diagnostics import DiagnosticRepository, result_digest, sha256_bytes
from .document_schema import detailed_document_result, finalize_document_result
from .email import EmailDeliveryError, EmailSettings, ResendMailer
from .exports import documents_json, line_items_csv, summary_csv
from .gpt_verifier import GptVerificationError, verify_receipt_with_gpt
from .markitdown_router import parse_pdf_with_markitdown_router
from .models import (
    BatchCreateRequest,
    BatchDocumentDeleteRequest,
    DeleteAccountRequest,
    DocumentPatch,
    EmailRequest,
    HistoryPromoteRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from .object_store import LocalObjectStore, ObjectStoreError, S3ObjectStore
from .operations import (
    PUBLIC_ANALYTICS_EVENTS,
    AdminCancelRequest,
    AdminRefundRequest,
    AnalyticsEventRequest,
    OperationsRepository,
)
from .parser import PdfParseError, locate_result_sources, ocr_available, parse_pdf, pdf_page_count
from .repository import DocumentRepository
from .runtime_security import InMemoryRateLimiter, RuntimeMonitor, pseudonymous_subject, structured_event
from .sample import create_sample_pdf
from .tax_workbook import schedule_c_workbook

logger = logging.getLogger(__name__)

settings.prepare()
repository = DocumentRepository(settings.database_path, settings.preview_dir)
billing_settings = BillingSettings()
billing_repository = BillingRepository(settings.database_path)
operations_repository = OperationsRepository(settings.database_path)
diagnostic_repository = DiagnosticRepository(
    settings.database_path,
    settings.diagnostic_dir,
    settings.diagnostic_encryption_key,
    settings.diagnostic_retention_days,
    settings.history_retention_days,
)


def _batch_object_store():
    if settings.batch_object_store == "s3":
        return S3ObjectStore(
            settings.batch_object_bucket,
            endpoint_url=settings.batch_object_endpoint,
            region=settings.batch_object_region,
            access_key_id=settings.batch_object_access_key_id,
            secret_access_key=settings.batch_object_secret_access_key,
            prefix=settings.batch_object_prefix,
        )
    if settings.batch_object_store == "local":
        return LocalObjectStore(settings.batch_object_dir)
    raise ObjectStoreError("unsupported_object_store")


batch_repository = BatchRepository(
    settings.batch_database_url or settings.database_path,
    _batch_object_store(),
    settings.batch_encryption_key,
    source_retention_days=settings.batch_source_retention_days,
    result_retention_days=settings.batch_result_retention_days,
)
paypal_client = PayPalClient(billing_settings)
mailer = ResendMailer(EmailSettings(settings.resend_api_key, settings.email_from))
auth_rate_limiter = InMemoryRateLimiter()
runtime_monitor = RuntimeMonitor(settings.data_dir / "runtime-operations.json")


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.purge_all_documents()
    operations_repository.purge_analytics(settings.analytics_retention_days)
    diagnostic_repository.purge_expired()
    diagnostic_repository.purge_recent_history()
    batch_repository.purge_expired()
    batch_repository.requeue_stale_processing(datetime.now(UTC) - timedelta(minutes=15))
    worker_stop: threading.Event | None = None
    worker_thread: threading.Thread | None = None
    if settings.batch_worker_mode == "embedded" and batch_repository.configured:
        worker_stop = threading.Event()
        worker = BatchWorker(
            batch_repository,
            _parse_with_reserved_quota,
            poll_seconds=settings.batch_worker_poll_seconds,
            monitor=runtime_monitor,
            queue_delay_warning_seconds=settings.batch_queue_delay_warning_seconds,
        )
        worker_thread = threading.Thread(
            target=worker.run_forever,
            args=(worker_stop,),
            name="receiptsift-batch-worker",
            daemon=True,
        )
        worker_thread.start()
    try:
        yield
    finally:
        if worker_stop is not None:
            worker_stop.set()
        if worker_thread is not None:
            worker_thread.join(timeout=5)


app = FastAPI(
    title="ReceiptSift PDF API",
    version=__version__,
    description="Protected PDF bill and receipt extraction API.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request_started = time.perf_counter()
    protected_api = request.url.path.startswith(("/api/v1/", "/api/admin/")) or request.url.path in {
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }
    try:
        if protected_api and not _is_authenticated(request):
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": {"code": "authentication_required", "message": "Sign in to use ReceiptSift."}},
            )
        else:
            response = await call_next(request)
    except Exception as error:
        elapsed_seconds = time.perf_counter() - request_started
        runtime_monitor.record_http(
            status_code=500,
            elapsed_seconds=elapsed_seconds,
            slow_request_ms=settings.slow_request_ms,
            error=error,
        )
        structured_event(
            "http_request_failed",
            level=logging.ERROR,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error_type=type(error).__name__,
            elapsed_ms=round(elapsed_seconds * 1000),
        )
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if (
        protected_api
        or request.url.path.startswith("/admin/")
        or request.url.path
        in {
            "/app",
            "/batches",
            "/account",
            "/login",
            "/register",
            "/forgot-password",
            "/reset-password",
            "/verify-email",
            "/admin",
        }
        or _is_app_host(request)
    ):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = "private, no-store"
    if _request_scheme(request) == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    elapsed_seconds = time.perf_counter() - request_started
    runtime_monitor.record_http(
        status_code=response.status_code,
        elapsed_seconds=elapsed_seconds,
        slow_request_ms=settings.slow_request_ms,
    )
    structured_event(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round(elapsed_seconds * 1000),
    )
    return response


def _request_scheme(request: Request) -> str:
    return request.headers.get("x-forwarded-proto", request.url.scheme).split(",", 1)[0].strip().lower()


def _request_host(request: Request) -> str:
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    return host.split(",", 1)[0].split(":", 1)[0].strip().lower()


def _request_network_hint(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(
    request: Request,
    *,
    action: str,
    identity: str | None,
    limit: int,
    window_seconds: int,
    include_network: bool = True,
) -> None:
    values = [("network", _request_network_hint(request))] if include_network else []
    if identity:
        values.append(("identity", identity))
    for namespace, value in values:
        subject = pseudonymous_subject(settings.session_secret, f"{action}:{namespace}", value)
        decision = auth_rate_limiter.check(
            f"{action}:{namespace}:{subject}",
            limit=limit,
            window_seconds=window_seconds,
        )
        if not decision.allowed:
            structured_event("auth_rate_limited", action=action, scope=namespace)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limit_reached", "message": "Too many attempts. Try again later."},
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )


def _is_app_host(request: Request) -> bool:
    host = _request_host(request)
    return bool((settings.app_host and host == settings.app_host) or host.startswith("app."))


def _configured_app_redirect(request: Request) -> RedirectResponse | None:
    if not settings.app_host_redirect_enabled or not settings.app_host or _request_host(request) == settings.app_host:
        return None
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        f"{_request_scheme(request)}://{settings.app_host}{request.url.path}{query}",
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


def _is_owner_user(user: dict[str, Any] | None) -> bool:
    if user is None or not settings.owner_email:
        return False
    return hmac.compare_digest(str(user["email"]).casefold(), settings.owner_email)


def _current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(COOKIE_NAME) or request.cookies.get(LEGACY_COOKIE_NAME)
    identity = session_identity(token, settings.session_secret)
    if identity is None:
        return None
    user_id, session_version = identity
    user = repository.get_user(user_id)
    if user is None or user["session_version"] != session_version:
        return None
    if settings.owner_only_mode and not _is_owner_user(user):
        return None
    return user


def _is_authenticated(request: Request) -> bool:
    return _current_user(request) is not None


def _require_user(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Sign in to use ReceiptSift."},
        )
    return user


def _is_admin_user(user: dict[str, Any] | None) -> bool:
    if user is None or not settings.admin_email:
        return False
    return hmac.compare_digest(str(user["email"]).casefold(), settings.admin_email)


def _require_admin(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    if not _is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required", "message": "Owner access is required."},
        )
    return user


async def _require_admin_password(request: Request, user: dict[str, Any], password: str) -> None:
    _enforce_rate_limit(
        request,
        action="admin_reauthentication",
        identity=str(user["id"]),
        limit=settings.auth_login_limit,
        window_seconds=settings.auth_login_window_seconds,
    )
    if not await run_in_threadpool(verify_password, password, user["password_hash"]):
        structured_event("admin_reauthentication_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "admin_reauthentication_failed", "message": "Owner password is incorrect."},
        )


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "email_verified": bool(user["email_verified_at"]),
        "email_verified_at": user["email_verified_at"],
        "created_at": user["created_at"],
        "is_admin": _is_admin_user(user),
    }


def _session_response(request: Request, user: dict[str, Any], status_code: int = 200) -> JSONResponse:
    response = JSONResponse({"authenticated": True, "user": _public_user(user)}, status_code=status_code)
    response.set_cookie(
        COOKIE_NAME,
        create_session(settings.session_secret, user["id"], settings.session_days, user["session_version"]),
        max_age=max(settings.session_days, 1) * 86400,
        httponly=True,
        secure=settings.secure_cookies and _request_scheme(request) == "https",
        samesite="strict",
        path="/",
    )
    return response


def _send_auth_email(user: dict[str, Any], purpose: str) -> bool:
    if not mailer.configured or not settings.site_url:
        return False
    token, digest = create_auth_token()
    if purpose == "verify_email":
        expires_at = datetime.now(UTC) + timedelta(hours=max(settings.email_verification_hours, 1))
        path = f"/verify-email?token={token}"
        subject = "Verify your ReceiptSift email"
        heading = "Verify your email"
        action = "Verify email"
        explanation = "Confirm this email address to activate your ReceiptSift account."
    else:
        expires_at = datetime.now(UTC) + timedelta(minutes=max(settings.password_reset_minutes, 5))
        path = f"/reset-password?token={token}"
        subject = "Reset your ReceiptSift password"
        heading = "Reset your password"
        action = "Reset password"
        explanation = "Use this single-use link to choose a new ReceiptSift password."
    created = repository.create_auth_token(user["id"], purpose, digest, expires_at)
    if not created:
        return True
    url = f"{settings.site_url}{path}"
    safe_url = escape(url, quote=True)
    text = f"{explanation}\n\n{url}\n\nIf you did not request this, you can ignore this email."
    html = (
        '<div style="font-family:Arial,sans-serif;color:#1d1d1f;max-width:560px;margin:auto">'
        f"<h1>{heading}</h1><p>{explanation}</p>"
        f'<p><a href="{safe_url}" style="background:#1d1d1f;color:#fff;padding:12px 18px;text-decoration:none">{action}</a></p>'
        '<p style="color:#6e6e73">If you did not request this, you can ignore this email.</p></div>'
    )
    mailer.send(
        to=user["email"],
        subject=subject,
        text=text,
        html=html,
        idempotency_key=f"receiptsift-{purpose}-{digest}",
    )
    return True


async def _deliver_auth_email(user: dict[str, Any], purpose: str) -> bool:
    try:
        return await run_in_threadpool(_send_auth_email, user, purpose)
    except EmailDeliveryError:
        return False


def _attempt_auth_email(user: dict[str, Any], purpose: str) -> None:
    try:
        _send_auth_email(user, purpose)
    except EmailDeliveryError:
        pass


@app.exception_handler(PdfParseError)
async def pdf_error_handler(_: Request, error: PdfParseError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": error.code, "message": str(error)}},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, error: HTTPException):
    detail = error.detail
    if isinstance(detail, dict) and "code" in detail:
        body = detail
    else:
        body = {"code": "request_error", "message": str(detail)}
    return JSONResponse(status_code=error.status_code, content={"error": body}, headers=error.headers)


def _model_token_prices(model: str) -> tuple[float, float]:
    if model == settings.gpt_verifier_model:
        return settings.gpt_verifier_input_usd_per_million, settings.gpt_verifier_output_usd_per_million
    if model == settings.atlas_fallback_model:
        return settings.atlas_fallback_input_usd_per_million, settings.atlas_fallback_output_usd_per_million
    if model == settings.atlas_text_model:
        return settings.atlas_text_input_usd_per_million, settings.atlas_text_output_usd_per_million
    return settings.atlas_primary_input_usd_per_million, settings.atlas_primary_output_usd_per_million


def _usage_cost(model: str, usage: dict[str, Any]) -> float:
    input_rate, output_rate = _model_token_prices(model)
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 6)


def _conservative_usage_cost(model: str, usage: dict[str, Any], reservation: float) -> float:
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    if input_tokens <= 0 and output_tokens <= 0:
        return reservation
    return _usage_cost(model, usage)


def _complete_atlas_monitor(reservation: float, result: dict[str, Any], elapsed_seconds: float) -> None:
    attempts = result.get("model_attempts") if isinstance(result.get("model_attempts"), list) else []
    if attempts:
        actual_cost = 0.0
        input_tokens = 0
        output_tokens = 0
        models = []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            model = str(attempt.get("model") or settings.atlas_primary_model)
            usage = attempt.get("usage") if isinstance(attempt.get("usage"), dict) else {}
            models.append(model)
            input_tokens += int(usage.get("input_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or 0)
            actual_cost += _conservative_usage_cost(model, usage, reservation)
        model_label = ",".join(models) or settings.atlas_primary_model
    else:
        usage = result.get("provider_usage") if isinstance(result.get("provider_usage"), dict) else {}
        model_label = str(result.get("extraction_model") or settings.atlas_primary_model)
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        actual_cost = _conservative_usage_cost(model_label, usage, reservation)
    runtime_monitor.complete_ai(
        reservation_usd=reservation,
        actual_cost_usd=actual_cost,
        model=model_label,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        elapsed_seconds=elapsed_seconds,
        success=True,
    )


def _complete_gpt_monitor(reservation: float, verification: dict[str, Any], elapsed_seconds: float) -> None:
    usage = verification.get("usage") if isinstance(verification.get("usage"), dict) else {}
    runtime_monitor.complete_ai(
        reservation_usd=reservation,
        actual_cost_usd=_conservative_usage_cost(settings.gpt_verifier_model, usage, reservation),
        model=settings.gpt_verifier_model,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        elapsed_seconds=elapsed_seconds,
        success=True,
        verifier=True,
    )


def _parse_ephemeral_document(
    user_id: str,
    order_id: str,
    pdf_bytes: bytes,
    filename: str,
    max_pages: int,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    parse_started = time.perf_counter()
    provider_used = "local"
    try:
        if settings.atlas_enabled:
            atlas_reservation = runtime_monitor.reserve_ai(
                daily_budget_usd=settings.daily_ai_budget_usd,
                reserve_usd=settings.ai_call_reserve_usd,
            )
            if atlas_reservation is None:
                if progress:
                    progress("local_extraction", 35, "AI budget unavailable; extracting locally")
                result, preview = parse_pdf(
                    pdf_bytes,
                    max_pages,
                    max_xref_objects=settings.max_pdf_xref_objects,
                    max_page_dimension=settings.max_pdf_page_dimension,
                    max_render_dimension=settings.atlas_max_render_dimension,
                )
                result["warnings"].append(
                    {
                        "code": "ai_daily_budget_reached",
                        "message": "The daily AI budget is unavailable; local extraction was used.",
                    }
                )
                result["status"] = "needs_review"
                result["extraction_method"] = f"{result['extraction_method']}_budget_fallback"
                structured_event("ai_budget_blocked", stage="atlas")
            else:
                atlas_started = time.perf_counter()
                try:
                    if progress:
                        progress("model_extraction", 35, "Reading pages and running the extraction model")
                    result, preview = parse_pdf_with_markitdown_router(
                        pdf_bytes,
                        api_key=settings.atlas_api_key,
                        base_url=settings.atlas_base_url,
                        text_model=settings.atlas_text_model,
                        primary_model=settings.atlas_primary_model,
                        fallback_model=settings.atlas_fallback_model,
                        max_pages=max_pages,
                        timeout_seconds=settings.atlas_timeout_seconds,
                        min_confidence=settings.atlas_min_confidence,
                        render_scale=settings.atlas_render_scale,
                        max_render_dimension=settings.atlas_max_render_dimension,
                        max_xref_objects=settings.max_pdf_xref_objects,
                        max_page_dimension=settings.max_pdf_page_dimension,
                    )
                except AtlasParseError:
                    runtime_monitor.complete_ai(
                        reservation_usd=atlas_reservation,
                        actual_cost_usd=atlas_reservation,
                        model=settings.atlas_primary_model,
                        input_tokens=0,
                        output_tokens=0,
                        elapsed_seconds=time.perf_counter() - atlas_started,
                        success=False,
                    )
                    if progress:
                        progress("local_fallback", 65, "Cloud extraction unavailable; retrying locally")
                    result, preview = parse_pdf(
                        pdf_bytes,
                        max_pages,
                        max_xref_objects=settings.max_pdf_xref_objects,
                        max_page_dimension=settings.max_pdf_page_dimension,
                        max_render_dimension=settings.atlas_max_render_dimension,
                    )
                    result["warnings"].append(
                        {
                            "code": "atlas_unavailable",
                            "message": "Cloud extraction was unavailable; local extraction was used.",
                        }
                    )
                    result["status"] = "needs_review"
                    result["extraction_method"] = f"{result['extraction_method']}_atlas_fallback"
                except Exception:
                    runtime_monitor.release_ai_reservation(atlas_reservation)
                    raise
                else:
                    provider_used = "atlas"
                    if progress:
                        progress("quality_check", 78, "Checking totals, fields, and extraction confidence")
                    _complete_atlas_monitor(atlas_reservation, result, time.perf_counter() - atlas_started)
                    if not settings.gpt_verifier_enabled:
                        result["verification"] = {"status": "not_run", "reason": "disabled"}
                    elif result.get("status") == "ready" and result.get("quality_gate", {}).get("decision") != "verify":
                        result["verification"] = {"status": "not_run", "reason": "quality_gate_passed"}
                    elif result.get("page_count") != 1 or not preview:
                        result["verification"] = {"status": "not_run", "reason": "single_page_preview_required"}
                    else:
                        gpt_reservation = runtime_monitor.reserve_ai(
                            daily_budget_usd=settings.daily_ai_budget_usd,
                            reserve_usd=settings.ai_call_reserve_usd,
                        )
                        if gpt_reservation is None:
                            result["verification"] = {"status": "not_run", "reason": "daily_budget_reached"}
                            result["warnings"].append(
                                {
                                    "code": "verifier_budget_reached",
                                    "message": "Independent verification was skipped because the daily AI budget was reached.",
                                }
                            )
                            result["status"] = "needs_review"
                            structured_event("ai_budget_blocked", stage="gpt_verifier")
                        else:
                            gpt_started = time.perf_counter()
                            try:
                                if progress:
                                    progress("independent_verification", 86, "Independently verifying the extracted result")
                                verification = verify_receipt_with_gpt(
                                    [preview],
                                    result,
                                    api_key=settings.atlas_api_key,
                                    base_url=settings.atlas_base_url,
                                    model=settings.gpt_verifier_model,
                                    timeout_seconds=settings.atlas_timeout_seconds,
                                )
                                _complete_gpt_monitor(
                                    gpt_reservation,
                                    verification,
                                    time.perf_counter() - gpt_started,
                                )
                                result["verification"] = {"status": "completed", **verification}
                                if verification.get("verdict") != "pass":
                                    result["warnings"].append(
                                        {
                                            "code": "independent_verification_required",
                                            "message": "Independent verification found a discrepancy or could not confirm the result.",
                                        }
                                    )
                                result["status"] = "needs_review"
                            except GptVerificationError:
                                runtime_monitor.complete_ai(
                                    reservation_usd=gpt_reservation,
                                    actual_cost_usd=gpt_reservation,
                                    model=settings.gpt_verifier_model,
                                    input_tokens=0,
                                    output_tokens=0,
                                    elapsed_seconds=time.perf_counter() - gpt_started,
                                    success=False,
                                    verifier=True,
                                )
                                result["verification"] = {"status": "unavailable", "reason": "provider_error"}
                                result["warnings"].append(
                                    {
                                        "code": "verifier_unavailable",
                                        "message": "Independent verification was unavailable; manual review is required.",
                                    }
                                )
                                result["status"] = "needs_review"
        else:
            if progress:
                progress("local_extraction", 35, "Extracting text and fields locally")
            result, preview = parse_pdf(
                pdf_bytes,
                max_pages,
                max_xref_objects=settings.max_pdf_xref_objects,
                max_page_dimension=settings.max_pdf_page_dimension,
                max_render_dimension=settings.atlas_max_render_dimension,
            )
        if progress:
            progress("finalizing", 92, "Finalizing fields and confidence warnings")
        if result.get("status") == "needs_review":
            locate_result_sources(
                pdf_bytes,
                result,
                max_render_dimension=settings.atlas_max_render_dimension,
            )
        now = datetime.now(UTC).isoformat()
        result.update(
            {
                "id": order_id,
                "order_id": order_id,
                "filename": filename,
                "created_at": now,
                "updated_at": now,
                "preview_url": None,
                "preview_data_url": (f"data:image/png;base64,{base64.b64encode(preview).decode('ascii')}" if preview else None),
                "storage_mode": "ephemeral",
            }
        )
        repository.record_usage(user_id, "document_parsed", int(result["page_count"]))
        runtime_monitor.record_parse(
            provider=provider_used,
            elapsed_seconds=time.perf_counter() - parse_started,
            success=True,
            status=str(result.get("status") or "unknown"),
            processed_images=int(result.get("page_count") or 0),
        )
        return result
    except Exception:
        runtime_monitor.record_parse(
            provider=provider_used,
            elapsed_seconds=time.perf_counter() - parse_started,
            success=False,
            status="error",
        )
        raise


def _billing_entitlement(user_id: str) -> Entitlement:
    subscription = billing_repository.get_for_user(user_id)
    usage = repository.usage(user_id)
    user = repository.get_user(user_id)
    owner_plan = settings.owner_plan_code if _is_owner_user(user) else "free"
    if owner_plan in {"plus", "pro"}:
        return entitlement(
            billing_settings,
            "ACTIVE",
            int(usage.get("documents_parsed", 0)),
            int(usage.get("pages_processed", 0)),
            owner_plan,
        )
    return entitlement(
        billing_settings,
        subscription.get("status") if subscription else None,
        int(usage.get("documents_parsed", 0)),
        int(usage.get("pages_processed", 0)),
        subscription.get("plan_code") if subscription else None,
    )


def _parse_with_reserved_quota(
    user_id: str,
    pdf_bytes: bytes,
    filename: str,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    if progress:
        progress("security_check", 8, "Checking PDF safety and page limits")
    page_count = pdf_page_count(
        pdf_bytes,
        max_xref_objects=settings.max_pdf_xref_objects,
        max_page_dimension=settings.max_pdf_page_dimension,
    )
    if progress:
        progress("quota_check", 15, "Checking plan and page allowance")
    current = _billing_entitlement(user_id)
    if page_count > current.max_pages_per_document:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "plan_page_limit_exceeded",
                "message": (f"Your {current.plan_code.title()} plan accepts up to {current.max_pages_per_document} pages per PDF."),
            },
        )
    if not current.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "monthly_limit_reached",
                "message": "Your monthly PDF allowance is used. Upgrade your plan or wait for the next monthly reset.",
            },
        )

    reservation_id = uuid.uuid4().hex
    reserved = billing_repository.reserve_document(
        user_id,
        current.monthly_document_limit,
        reservation_id,
        requested_pages=page_count,
        monthly_page_limit=current.monthly_page_limit,
        max_pages_per_document=current.max_pages_per_document,
    )
    if not reserved:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "monthly_limit_reached",
                "message": "Your monthly PDF allowance is used. Upgrade to Pro or wait for the next monthly reset.",
            },
        )
    order_id = diagnostic_repository.create_parse_order(
        user_id,
        sha256_bytes(pdf_bytes),
        page_count,
        __version__,
    )
    started_at = time.perf_counter()
    try:
        if progress:
            progress("document_analysis", 22, "Reading document structure and selecting an extraction route")
        result = _parse_ephemeral_document(
            user_id,
            order_id,
            pdf_bytes,
            filename,
            current.max_pages_per_document,
            progress,
        )
        diagnostic_repository.complete_parse_order(
            order_id,
            extraction_method=str(result.get("extraction_method") or "unknown"),
            output_sha256=result_digest(result),
            duration_ms=round((time.perf_counter() - started_at) * 1000),
            overall_confidence=float(result.get("overall_confidence") or 0),
            warning_count=len(result.get("warnings") or []),
            result_status=str(result.get("status") or "completed"),
        )
        return diagnostic_repository.save_recent_document(user_id, order_id, pdf_bytes, result)
    except Exception as error:
        diagnostic_repository.fail_parse_order(
            order_id,
            str(getattr(error, "code", error.__class__.__name__)),
            round((time.perf_counter() - started_at) * 1000),
        )
        raise
    finally:
        billing_repository.release_document_reservation(reservation_id)


def _summary(document: dict[str, Any]) -> dict[str, Any]:
    fields = document.get("fields", {})
    return {
        "id": document["id"],
        "filename": document["filename"],
        "status": document["status"],
        "page_count": document["page_count"],
        "extraction_method": document["extraction_method"],
        "overall_confidence": document.get("overall_confidence", 0),
        "merchant": fields.get("merchant", {}).get("value"),
        "date": fields.get("date", {}).get("value"),
        "currency": fields.get("currency", {}).get("value"),
        "total": fields.get("total", {}).get("value"),
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }


@app.post("/api/events", status_code=status.HTTP_202_ACCEPTED)
def collect_analytics_event(request: Request, payload: AnalyticsEventRequest) -> dict[str, bool]:
    if payload.event not in PUBLIC_ANALYTICS_EVENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unsupported_event", "message": "This analytics event is not accepted."},
        )
    if not payload.path.startswith("/") or payload.path.startswith("//"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_event_path", "message": "Analytics paths must be site-relative."},
        )
    user = _current_user(request)
    operations_repository.record_event(
        payload.event,
        user_id=user["id"] if user else None,
        visitor_id=payload.visitor_id,
        path=payload.path,
        source=payload.source,
        properties=payload.properties,
    )
    return {"accepted": True}


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    email_ready = bool(mailer.configured and settings.site_url)
    registration_open = bool(email_ready and not settings.owner_only_mode)
    return {
        "authenticated": user is not None,
        "access_mode": "owner_only" if settings.owner_only_mode else "accounts",
        "owner_only_mode": settings.owner_only_mode,
        "owner_access_configured": bool(settings.owner_email),
        "registration_open": registration_open,
        "registration_requires_invite": False,
        "transactional_email_configured": email_ready,
        "user": _public_user(user) if user else None,
    }


@app.post("/api/auth/login")
async def auth_login(request: Request, payload: LoginRequest) -> Response:
    _enforce_rate_limit(
        request,
        action="login",
        identity=None,
        limit=settings.auth_login_limit,
        window_seconds=settings.auth_login_window_seconds,
    )
    try:
        email = normalize_email(payload.email)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Email or password is incorrect."},
        ) from error
    _enforce_rate_limit(
        request,
        action="login",
        identity=email,
        limit=settings.auth_login_limit,
        window_seconds=settings.auth_login_window_seconds,
        include_network=False,
    )
    user = repository.get_user_by_email(email)
    password_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
    password_matches = await run_in_threadpool(verify_password, payload.password, password_hash)
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Email or password is incorrect."},
        )
    if not user["email_verified_at"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "message": "Verify your email before signing in."},
        )
    if settings.owner_only_mode and not _is_owner_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "owner_only_access",
                "message": "ReceiptSift is currently restricted to the site owner.",
            },
        )
    operations_repository.record_event("account_login", user_id=user["id"], path="/login")
    return _session_response(request, user)


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def auth_register(request: Request, payload: RegisterRequest) -> Response:
    _enforce_rate_limit(
        request,
        action="register",
        identity=payload.email,
        limit=settings.auth_registration_limit,
        window_seconds=settings.auth_recovery_window_seconds,
    )
    if settings.owner_only_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "owner_only_access",
                "message": "Account registration is closed while ReceiptSift is owner-only.",
            },
        )
    if not mailer.configured or not settings.site_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "registration_email_unavailable",
                "message": "Account registration is temporarily unavailable while email delivery is being configured.",
            },
        )
    try:
        email = normalize_email(payload.email)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_email", "message": "Enter a valid email address."},
        ) from error
    password_hash = await run_in_threadpool(hash_password, payload.password)
    try:
        user = repository.create_user(email, password_hash)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_exists", "message": "An account with this email already exists."},
        ) from error
    operations_repository.record_event("account_registered", user_id=user["id"], path="/register")
    email_sent = await _deliver_auth_email(user, "verify_email")
    return JSONResponse(
        {
            "registered": True,
            "verification_required": True,
            "email_sent": email_sent,
            "message": (
                "Check your email to activate the account."
                if email_sent
                else "The account was created, but verification email delivery is not configured."
            ),
        },
        status_code=status.HTTP_201_CREATED,
    )


@app.post("/api/auth/verification/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    request: Request,
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    _enforce_rate_limit(
        request,
        action="verification_resend",
        identity=payload.email,
        limit=settings.auth_recovery_limit,
        window_seconds=settings.auth_recovery_window_seconds,
    )
    try:
        email = normalize_email(payload.email)
    except ValueError:
        email = ""
    user = repository.get_user_by_email(email) if email else None
    if user and not user["email_verified_at"] and (not settings.owner_only_mode or _is_owner_user(user)):
        background_tasks.add_task(_attempt_auth_email, user, "verify_email")
    return {"accepted": True, "message": "If the account needs verification, an email will be sent."}


@app.post("/api/auth/password/forgot", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: Request,
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    _enforce_rate_limit(
        request,
        action="password_forgot",
        identity=payload.email,
        limit=settings.auth_recovery_limit,
        window_seconds=settings.auth_recovery_window_seconds,
    )
    try:
        email = normalize_email(payload.email)
    except ValueError:
        email = ""
    user = repository.get_user_by_email(email) if email else None
    if user and (not settings.owner_only_mode or _is_owner_user(user)):
        background_tasks.add_task(_attempt_auth_email, user, "reset_password")
    return {"accepted": True, "message": "If the account exists, a reset email will be sent."}


@app.post("/api/auth/password/reset")
async def reset_password(request: Request, payload: ResetPasswordRequest) -> dict[str, Any]:
    _enforce_rate_limit(
        request,
        action="password_reset",
        identity=None,
        limit=settings.auth_recovery_limit,
        window_seconds=settings.auth_recovery_window_seconds,
    )
    password_hash = await run_in_threadpool(hash_password, payload.password)
    user = repository.reset_password_with_token(auth_token_digest(payload.token), password_hash)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_or_expired_token", "message": "This password reset link is invalid or expired."},
        )
    return {"reset": True, "message": "Password updated. Sign in with your new password."}


@app.get("/verify-email", include_in_schema=False)
def verify_email(token: str = Query(min_length=32, max_length=256)) -> Response:
    user = repository.verify_email_token(auth_token_digest(token))
    if user is None:
        return RedirectResponse("/login?verification=invalid", status_code=303)
    return RedirectResponse("/login?verified=1", status_code=303)


@app.post("/api/auth/logout")
def auth_logout() -> Response:
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(LEGACY_COOKIE_NAME, path="/", samesite="strict")
    return response


@app.get("/api/v1/account")
def account_profile(request: Request) -> dict[str, Any]:
    return _public_user(_require_user(request))


@app.get("/api/v1/account/usage")
def account_usage(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    usage = repository.usage(user["id"])
    recent = diagnostic_repository.list_recent_documents(user["id"], limit=10000)
    usage.update(
        {
            "saved_documents": len(recent),
            "saved_pages": sum(int(item.get("page_count") or 0) for item in recent),
            "document_storage_enabled": diagnostic_repository.configured,
            "history_retention_days": diagnostic_repository.history_retention_days,
        }
    )
    return usage


@app.post("/api/v1/account/usage/csv-export", status_code=status.HTTP_202_ACCEPTED)
def record_csv_export(request: Request) -> dict[str, bool]:
    user = _require_user(request)
    repository.record_usage(user["id"], "csv_exported")
    return {"accepted": True}


def _diagnostic_json(value: str, field_name: str) -> dict[str, Any]:
    if len(value.encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "diagnostic_result_too_large", "message": f"{field_name} exceeds the 2 MB limit."},
        )
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_diagnostic_result", "message": f"{field_name} must be valid JSON."},
        ) from error
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_diagnostic_result", "message": f"{field_name} must be a JSON object."},
        )
    return parsed


@app.get("/api/v1/diagnostic-cases")
def list_diagnostic_cases(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    return {
        "cases": diagnostic_repository.list_cases(user["id"]),
        "retention_days": diagnostic_repository.retention_days,
        "available": diagnostic_repository.configured,
    }


@app.post("/api/v1/diagnostic-cases", status_code=status.HTTP_201_CREATED)
async def create_diagnostic_case(
    request: Request,
    order_id: Annotated[str, Form(min_length=32, max_length=32)],
    description: Annotated[str, Form(min_length=3, max_length=2000)],
    consent: Annotated[bool, Form()],
    original_result_json: Annotated[str, Form()],
    corrected_result_json: Annotated[str, Form()],
    file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, Any]:
    user = _require_user(request)
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "diagnostic_consent_required",
                "message": "Explicit consent is required before diagnostic evidence can be stored.",
            },
        )
    if not diagnostic_repository.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "diagnostic_reporting_unavailable",
                "message": "Secure diagnostic reporting is not configured. No evidence was stored.",
            },
        )
    source_pdf: bytes | None = None
    if file is not None:
        source_pdf = await file.read(settings.max_upload_bytes + 1)
        await file.close()
        if len(source_pdf) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"code": "file_too_large", "message": "The diagnostic PDF exceeds the upload limit."},
            )
        if not source_pdf.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"code": "not_pdf", "message": "Diagnostic evidence must be the original PDF."},
            )
    original_result = _diagnostic_json(original_result_json, "Original result")
    corrected_result = _diagnostic_json(corrected_result_json, "Corrected result")
    try:
        case = diagnostic_repository.create_case(
            user_id=user["id"],
            order_id=order_id,
            description=description.strip(),
            original_result=original_result,
            corrected_result=corrected_result,
            source_pdf=source_pdf,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": str(error), "message": "The parse order was not found for this account."},
        ) from error
    except ValueError as error:
        messages = {
            "parse_order_not_complete": "This parse order is not complete.",
            "original_result_mismatch": "The original result no longer matches this parse order.",
            "source_pdf_mismatch": "The selected PDF is not the file used for this parse order.",
            "diagnostic_case_exists": "A diagnostic case already exists for this parse order.",
        }
        code = str(error)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": code, "message": messages.get(code, "The diagnostic report could not be accepted.")},
        ) from error
    return {"case": case, "retention_days": diagnostic_repository.retention_days}


@app.delete("/api/v1/diagnostic-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diagnostic_case(request: Request, case_id: str) -> Response:
    user = _require_user(request)
    if not diagnostic_repository.delete_case(user["id"], case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "diagnostic_case_not_found", "message": "Diagnostic case not found."},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/account/export.json")
def export_account_data(request: Request) -> Response:
    user = _require_user(request)
    exported = repository.export_user_data(user["id"])
    if exported is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Account not found."})
    exported["billing"] = billing_repository.get_for_user(user["id"])
    exported["parse_orders"] = diagnostic_repository.list_parse_orders(user["id"], limit=None)
    exported["diagnostic_cases"] = diagnostic_repository.list_cases(user["id"])
    exported["recent_documents"] = diagnostic_repository.list_recent_documents(user["id"], limit=10000)
    exported["ledger_entries"] = diagnostic_repository.list_ledger_entries(user["id"], limit=10000)
    exported["receipt_batches"] = [
        {**batch, "documents": batch_repository.list_documents(user["id"], batch["id"])}
        for batch in batch_repository.list_batches(user["id"], limit=100)
    ]
    payload = json.dumps(exported, ensure_ascii=False, indent=2).encode()
    return Response(
        payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="receiptsift-account-export.json"'},
    )


@app.delete("/api/v1/account")
async def delete_account(request: Request, payload: DeleteAccountRequest) -> Response:
    user = _require_user(request)
    password_matches = await run_in_threadpool(verify_password, payload.password, user["password_hash"])
    if not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_password", "message": "The account password is incorrect."},
        )
    subscription = billing_repository.get_for_user(user["id"])
    if subscription and subscription["status"] not in {"CANCELLED", "EXPIRED"}:
        try:
            await run_in_threadpool(
                paypal_client.cancel_subscription,
                subscription["provider_subscription_id"],
                "ReceiptSift account deleted by customer",
            )
        except BillingError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "subscription_cancellation_failed",
                    "message": "We could not cancel the PayPal subscription, so the account was not deleted. Try again or contact support.",
                },
            ) from error
        billing_repository.update_status(user["id"], "CANCELLED")
    diagnostic_repository.delete_user_cases(user["id"])
    diagnostic_repository.delete_user_history(user["id"])
    batch_repository.delete_user_batches(user["id"])
    if not repository.delete_user(user["id"]):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Account not found."})
    billing_repository.delete_for_user(user["id"])
    response = JSONResponse({"deleted": True})
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict")
    response.delete_cookie(LEGACY_COOKIE_NAME, path="/", samesite="strict")
    return response


@app.get("/api/admin/overview")
def admin_overview(request: Request, days: int = Query(default=30, ge=1, le=365)) -> dict[str, Any]:
    _require_admin(request)
    return operations_repository.overview(days)


@app.get("/api/admin/users")
def admin_users(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    search: str = Query(default="", max_length=120),
) -> dict[str, Any]:
    _require_admin(request)
    users = operations_repository.list_users(limit=limit, search=search)
    return {"users": users, "limit": limit}


@app.get("/api/admin/payments")
def admin_payments(request: Request, limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    _require_admin(request)
    return {"payments": billing_repository.list_payments(limit), "limit": limit}


@app.get("/api/admin/events")
def admin_events(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    event_type: str = Query(default="", max_length=48),
) -> dict[str, Any]:
    _require_admin(request)
    return {"events": operations_repository.list_events(limit=limit, event_type=event_type), "limit": limit}


@app.get("/api/admin/audit")
def admin_audit(request: Request, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    _require_admin(request)
    return {"events": operations_repository.list_audit(limit), "limit": limit}


@app.get("/api/admin/runtime")
def admin_runtime(request: Request) -> dict[str, Any]:
    _require_admin(request)
    return runtime_monitor.snapshot(
        daily_budget_usd=settings.daily_ai_budget_usd,
        database_backend="postgresql" if settings.batch_database_url else "sqlite",
        sqlite_contention_threshold=settings.sqlite_contention_threshold,
    )


@app.get("/api/admin/diagnostic-cases")
def admin_diagnostic_cases(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    _require_admin(request)
    return {
        "cases": diagnostic_repository.list_cases_for_admin(limit),
        "available": diagnostic_repository.configured,
        "retention_days": diagnostic_repository.retention_days,
    }


@app.get("/api/admin/diagnostic-cases/{case_id}")
def admin_diagnostic_case(request: Request, case_id: str) -> dict[str, Any]:
    admin = _require_admin(request)
    case = diagnostic_repository.get_case_for_admin(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "diagnostic_case_not_found", "message": "Diagnostic case not found."},
        )
    try:
        report = diagnostic_repository.read_case_bundle(case_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": str(error), "message": "Diagnostic decryption is not configured."},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": str(error), "message": "The encrypted diagnostic evidence could not be opened."},
        ) from error
    operations_repository.record_audit(
        admin_user_id=admin["id"],
        admin_email=admin["email"],
        action="diagnostic_case_viewed",
        target_type="diagnostic_case",
        target_id=case_id,
        details={"order_id": case["order_id"]},
    )
    return {"case": case, "report": report}


@app.get("/api/admin/diagnostic-cases/{case_id}/source.pdf")
def admin_diagnostic_source(request: Request, case_id: str) -> Response:
    admin = _require_admin(request)
    case = diagnostic_repository.get_case_for_admin(case_id)
    if case is None or not case["has_source_pdf"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "diagnostic_source_not_found", "message": "No source PDF is attached to this case."},
        )
    try:
        payload = diagnostic_repository.read_source_pdf(case_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": str(error), "message": "Diagnostic decryption is not configured."},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": str(error), "message": "The encrypted source PDF could not be opened."},
        ) from error
    operations_repository.record_audit(
        admin_user_id=admin["id"],
        admin_email=admin["email"],
        action="diagnostic_source_downloaded",
        target_type="diagnostic_case",
        target_id=case_id,
        details={"order_id": case["order_id"]},
    )
    return Response(
        payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="diagnostic-{case_id[:12]}.pdf"'},
    )


@app.delete("/api/admin/diagnostic-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_diagnostic_case(request: Request, case_id: str) -> Response:
    admin = _require_admin(request)
    case = diagnostic_repository.get_case_for_admin(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "diagnostic_case_not_found", "message": "Diagnostic case not found."},
        )
    if not diagnostic_repository.delete_case_for_admin(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "diagnostic_case_not_found", "message": "Diagnostic case not found."},
        )
    operations_repository.record_audit(
        admin_user_id=admin["id"],
        admin_email=admin["email"],
        action="diagnostic_case_deleted",
        target_type="diagnostic_case",
        target_id=case_id,
        details={"order_id": case["order_id"]},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/admin/payments/{payment_id}/refund")
async def admin_refund_payment(
    request: Request,
    payment_id: str,
    payload: AdminRefundRequest,
) -> dict[str, Any]:
    admin = _require_admin(request)
    await _require_admin_password(request, admin, payload.password)
    if payload.confirmation != "REFUND":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "confirmation_required", "message": "Type REFUND to confirm this operation."},
        )
    payment = billing_repository.get_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail={"code": "payment_not_found", "message": "Payment not found."})
    if payment["status"] in {"DENIED", "PENDING", "REFUNDED", "REFUND_PENDING", "REVERSED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "payment_not_refundable", "message": "This payment cannot be refunded in its current state."},
        )
    try:
        requested_amount = Decimal(payload.amount)
        original_amount = Decimal(str(payment["amount_value"]))
        refunded_amount = Decimal(str(payment.get("refunded_amount") or 0))
    except InvalidOperation as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_refund_amount", "message": "Enter a valid refund amount."},
        ) from error
    available = original_amount - refunded_amount
    if requested_amount <= 0 or requested_amount > available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "refund_amount_exceeds_available",
                "message": f"Refund no more than {available:.2f} {payment['currency']}.",
            },
        )
    currency = payload.currency.upper()
    if currency != payment["currency"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "refund_currency_mismatch", "message": "Refund currency must match the original payment."},
        )
    try:
        paypal_refund = await run_in_threadpool(
            paypal_client.refund_sale,
            payment_id,
            f"{requested_amount:.2f}",
            currency,
            payload.reason,
        )
    except BillingError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error
    refund_id = str(paypal_refund.get("id", ""))
    if not refund_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "paypal_refund_missing_id", "message": "PayPal did not return a refund ID."},
        )
    refund_status = str(paypal_refund.get("state") or paypal_refund.get("status") or "PENDING").upper()
    refund = billing_repository.record_refund(
        provider_refund_id=refund_id,
        provider_payment_id=payment_id,
        amount_value=f"{requested_amount:.2f}",
        currency=currency,
        status=refund_status,
        reason=payload.reason,
        requested_by=admin["email"],
    )
    operations_repository.record_audit(
        admin_user_id=admin["id"],
        admin_email=admin["email"],
        action="payment_refund_requested",
        target_type="payment",
        target_id=payment_id,
        details={
            "refund_id": refund_id,
            "amount": f"{requested_amount:.2f}",
            "currency": currency,
            "status": refund_status,
        },
    )
    return {"refund": refund, "payment": billing_repository.get_payment(payment_id)}


@app.post("/api/admin/subscriptions/{subscription_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def admin_cancel_subscription(
    request: Request,
    subscription_id: str,
    payload: AdminCancelRequest,
) -> dict[str, Any]:
    admin = _require_admin(request)
    await _require_admin_password(request, admin, payload.password)
    if payload.confirmation != "CANCEL":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "confirmation_required", "message": "Type CANCEL to confirm this operation."},
        )
    subscription = billing_repository.get_by_provider_id(subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail={"code": "subscription_not_found", "message": "Subscription not found."})
    if subscription["status"] in {"CANCELLED", "EXPIRED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "subscription_not_active", "message": "This subscription is already inactive."},
        )
    try:
        await run_in_threadpool(paypal_client.cancel_subscription, subscription_id, payload.reason)
    except BillingError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)}) from error
    billing_repository.update_status(subscription["user_id"], "CANCELLED")
    operations_repository.record_audit(
        admin_user_id=admin["id"],
        admin_email=admin["email"],
        action="subscription_cancelled",
        target_type="subscription",
        target_id=subscription_id,
        details={"reason": payload.reason},
    )
    return {"accepted": True, "subscription_id": subscription_id}


app.include_router(
    build_billing_router(
        database_path=settings.database_path,
        require_user=_require_user,
        usage_for_user=lambda user_id: repository.usage(user_id),
        settings=billing_settings,
        paypal=paypal_client,
        repository_provider=lambda: billing_repository,
        entitlement_for_user=_billing_entitlement,
    )
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    email_ready = bool(mailer.configured and settings.site_url)
    registration_open = bool(email_ready and not settings.owner_only_mode)
    return {
        "status": "ok",
        "version": __version__,
        "ocr_available": ocr_available(),
        "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
        "max_pages": settings.max_pages,
        "source_pdf_retained": diagnostic_repository.configured,
        "structured_result_retained": diagnostic_repository.configured,
        "preview_retained": diagnostic_repository.configured,
        "retention_days": diagnostic_repository.history_retention_days if diagnostic_repository.configured else 0,
        "document_storage_enabled": diagnostic_repository.configured,
        "parse_audit_metadata_retained": True,
        "diagnostic_reporting_available": diagnostic_repository.configured,
        "diagnostic_retention_days": diagnostic_repository.retention_days,
        "diagnostic_evidence_requires_consent": True,
        "access_protected": True,
        "access_mode": "owner_only" if settings.owner_only_mode else "accounts",
        "owner_only_mode": settings.owner_only_mode,
        "owner_access_configured": bool(settings.owner_email),
        "registration_open": registration_open,
        "registration_requires_invite": False,
        "transactional_email_configured": email_ready,
        "parser_provider": "atlas" if settings.atlas_enabled else "local",
        "atlas_text_model": settings.atlas_text_model if settings.atlas_enabled else None,
        "atlas_primary_model": settings.atlas_primary_model if settings.atlas_enabled else None,
        "atlas_fallback_model": settings.atlas_fallback_model if settings.atlas_enabled else None,
        "gpt_verifier_enabled": bool(settings.atlas_enabled and settings.gpt_verifier_enabled),
        "gpt_verifier_model": settings.gpt_verifier_model if settings.atlas_enabled and settings.gpt_verifier_enabled else None,
        "batch_workspace_available": batch_repository.configured,
        "batch_database": "postgresql" if settings.batch_database_url else "sqlite",
        "batch_object_store": settings.batch_object_store,
        "batch_worker_mode": settings.batch_worker_mode,
        "batch_source_retention_days": settings.batch_source_retention_days,
        "batch_result_retention_days": settings.batch_result_retention_days,
        "capacity_monitoring_enabled": True,
        "daily_ai_budget_guard_enabled": settings.daily_ai_budget_usd > 0,
        "auth_rate_limit_scope": "single_replica_memory",
        "pdf_active_content_rejected": True,
        "pdf_structure_limits_enabled": True,
        "app_host_redirect_enabled": settings.app_host_redirect_enabled,
    }


def _require_batch_storage() -> None:
    if not batch_repository.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "batch_storage_not_configured",
                "message": "Batch storage is not configured for this environment.",
            },
        )


def _batch_storage_http_error(error: BatchStorageError) -> HTTPException:
    mapping = {
        "batch_not_found": (404, "Batch not found."),
        "document_not_found": (404, "Document not found."),
        "source_expired": (410, "The retained source PDF has expired."),
        "document_processing": (409, "This document has already started processing and cannot be deleted yet."),
        "not_pdf": (415, "Only valid PDF files are accepted."),
        "batch_storage_not_configured": (503, "Batch storage is not configured."),
    }
    status_code, message = mapping.get(error.code, (500, "Batch storage could not complete the request."))
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": message})


@app.post("/api/v1/batches", status_code=status.HTTP_201_CREATED)
def create_batch(request: Request, payload: BatchCreateRequest) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    return batch_repository.create_batch(user["id"], payload.name)


@app.get("/api/v1/batches")
def list_batches(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    return {"batches": batch_repository.list_batches(user["id"], limit, offset), "limit": limit, "offset": offset}


@app.get("/api/v1/batches/{batch_id}")
def get_batch(request: Request, batch_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    batch = batch_repository.get_batch(user["id"], batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    return {**batch, "documents": batch_repository.list_documents(user["id"], batch_id)}


@app.delete("/api/v1/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(request: Request, batch_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    if not batch_repository.delete_batch(user["id"], batch_id):
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/batches/{batch_id}/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_documents(
    request: Request,
    batch_id: str,
    files: Annotated[list[UploadFile], File()],
) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    batch = batch_repository.get_batch(user["id"], batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    entitlement_limits = _billing_entitlement(user["id"])
    plan_batch_limit = min(settings.batch_max_files, entitlement_limits.max_files_per_batch)
    if plan_batch_limit < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "batch_plan_required", "message": "Batch processing is available on Plus and Pro."},
        )
    remaining = max(0, plan_batch_limit - int(batch["document_count"]))
    if not files or len(files) > remaining:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "batch_file_limit_exceeded",
                "message": f"Your {entitlement_limits.plan_code.title()} plan allows up to {plan_batch_limit} PDFs per batch.",
            },
        )

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for upload in files:
        filename = Path(upload.filename or "receipt.pdf").name
        payload = await upload.read(settings.max_upload_bytes + 1)
        await upload.close()
        if len(payload) > settings.max_upload_bytes:
            rejected.append({"filename": filename, "code": "file_too_large"})
            continue
        if not payload.startswith(b"%PDF-"):
            rejected.append({"filename": filename, "code": "not_pdf"})
            continue
        try:
            document = await run_in_threadpool(
                batch_repository.add_document,
                user["id"],
                batch_id,
                filename,
                payload,
            )
        except BatchStorageError as error:
            if error.code == "duplicate_document":
                rejected.append({"filename": filename, "code": error.code})
                continue
            raise _batch_storage_http_error(error) from error
        accepted.append(document)
    return {
        "batch_id": batch_id,
        "accepted": accepted,
        "rejected": rejected,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
    }


@app.post("/api/v1/batches/{batch_id}/documents/delete")
def delete_batch_documents(
    request: Request,
    batch_id: str,
    payload: BatchDocumentDeleteRequest,
) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    try:
        deleted_count = batch_repository.delete_documents(user["id"], batch_id, payload.document_ids)
    except BatchStorageError as error:
        raise _batch_storage_http_error(error) from error
    return {"batch_id": batch_id, "deleted_count": deleted_count}


@app.post("/api/v1/batches/{batch_id}/start", status_code=status.HTTP_202_ACCEPTED)
def start_batch_processing(request: Request, batch_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    if _billing_entitlement(user["id"]).max_files_per_batch < 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "batch_plan_required", "message": "Batch processing is available on Plus and Pro."},
        )
    queued_count = batch_repository.start_batch(user["id"], batch_id)
    if queued_count is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    return {
        "batch_id": batch_id,
        "queued_count": queued_count,
        "batch": batch_repository.get_batch(user["id"], batch_id),
    }


@app.get("/api/v1/batches/{batch_id}/documents")
def list_batch_documents(request: Request, batch_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    if batch_repository.get_batch(user["id"], batch_id) is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    return {"documents": batch_repository.list_documents(user["id"], batch_id)}


@app.get("/api/v1/batch-documents/{document_id}")
def get_batch_document(request: Request, document_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    return document


@app.delete("/api/v1/batch-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch_document(request: Request, document_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    try:
        deleted = batch_repository.delete_document(user["id"], document_id)
    except BatchStorageError as error:
        raise _batch_storage_http_error(error) from error
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/batch-documents/{document_id}/source.pdf")
def get_batch_document_source(request: Request, document_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    try:
        payload = batch_repository.read_source(user["id"], document_id)
    except BatchStorageError as error:
        raise _batch_storage_http_error(error) from error
    filename = str(document["filename"]).replace('"', "")
    return Response(
        payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/api/v1/batch-documents/{document_id}/preview.png")
def get_batch_document_preview(
    request: Request,
    document_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document not found."})
    try:
        payload = batch_repository.read_source(user["id"], document_id)
    except BatchStorageError as error:
        raise _batch_storage_http_error(error) from error

    try:
        import pymupdf

        with pymupdf.open(stream=payload, filetype="pdf") as source:
            if page > source.page_count:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "page_not_found", "message": "Source page not found."},
                )
            source_page = source.load_page(page - 1)
            longest_side = max(float(source_page.rect.width), float(source_page.rect.height), 1.0)
            render_scale = min(1.6, 1800.0 / longest_side)
            pixmap = source_page.get_pixmap(matrix=pymupdf.Matrix(render_scale, render_scale), alpha=False)
            preview = pixmap.tobytes("png")
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("batch_preview_render_failed document_id=%s page=%s error=%s", document_id, page, type(error).__name__)
        raise HTTPException(
            status_code=422,
            detail={"code": "preview_unavailable", "message": "Source preview could not be rendered."},
        ) from error

    return Response(
        preview,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/v1/batch-documents/{document_id}/source-regions")
def get_batch_document_source_regions(request: Request, document_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None or not isinstance(document.get("result"), dict):
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document result not found."})
    try:
        payload = batch_repository.read_source(user["id"], document_id)
    except BatchStorageError as error:
        raise _batch_storage_http_error(error) from error

    result = copy.deepcopy(document["result"])
    locate_result_sources(
        payload,
        result,
        max_render_dimension=settings.atlas_max_render_dimension,
    )
    fields = result.get("fields") if isinstance(result.get("fields"), dict) else {}
    regions = {}
    for name, field in fields.items():
        source = field.get("source") if isinstance(field, dict) and isinstance(field.get("source"), dict) else None
        bbox = source.get("bbox") if source else None
        if isinstance(bbox, list) and len(bbox) == 4:
            regions[name] = {"page": source.get("page"), "bbox": bbox}
    return {"fields": regions}


def _apply_review_patch(result: dict[str, Any], payload: DocumentPatch) -> tuple[dict[str, Any], dict[str, Any]]:
    patch = payload.model_dump(exclude_unset=True)
    corrected = copy.deepcopy(result)
    document_type = patch.pop("document_type", corrected.get("document_type", "receipt"))
    document_subtype = patch.pop("document_subtype", corrected.get("document_subtype"))
    fields = corrected.setdefault("fields", {})
    for name, value in patch.items():
        if name == "items":
            corrected["items"] = [{**item, "confidence": 1.0, "source": None} for item in (value or [])]
            continue
        previous = fields.get(name) if isinstance(fields.get(name), dict) else {}
        fields[name] = {"value": value, "confidence": 1.0, "source": previous.get("source")}
    corrected["reviewed_at"] = datetime.now(UTC).isoformat()
    page_text = "\n".join(str(page.get("text") or "") for page in corrected.get("pages", []) if isinstance(page, dict))
    finalize_document_result(
        corrected,
        text=page_text,
        document_type=document_type,
        document_subtype=document_subtype,
    )
    corrected["status"] = "needs_review" if corrected.get("warnings") else "ready"
    stored_patch = {**patch, "document_type": document_type, "document_subtype": document_subtype}
    return stored_patch, corrected


@app.patch("/api/v1/batch-documents/{document_id}")
def review_batch_document(request: Request, document_id: str, payload: DocumentPatch) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None or document["result"] is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document result not found."})
    patch, corrected = _apply_review_patch(document["result"], payload)
    return batch_repository.save_review(user["id"], document_id, patch, corrected)  # type: ignore[return-value]


@app.post("/api/v1/batch-documents/{document_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_batch_document(request: Request, document_id: str) -> dict[str, Any]:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.retry_document(user["id"], document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "document_not_retryable", "message": "This document cannot be retried."},
        )
    return document


@app.get("/api/v1/batches/{batch_id}/export.csv")
def export_batch_csv(request: Request, batch_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    batch = batch_repository.get_batch(user["id"], batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    payload = summary_csv(batch_repository.list_documents(user["id"], batch_id))
    repository.record_usage(user["id"], "csv_exported")
    filename = f"receiptsift-{batch_id[:12]}.csv"
    return Response(
        payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batches/{batch_id}/export-items.csv")
def export_batch_line_items_csv(request: Request, batch_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    if batch_repository.get_batch(user["id"], batch_id) is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    payload = line_items_csv(batch_repository.list_documents(user["id"], batch_id))
    repository.record_usage(user["id"], "csv_exported")
    filename = f"receiptsift-{batch_id[:12]}-items.csv"
    return Response(
        payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batches/{batch_id}/export-tax-prep.xlsx")
def export_batch_tax_workbook(request: Request, batch_id: str) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    batch = batch_repository.get_batch(user["id"], batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    payload = schedule_c_workbook(
        batch_repository.list_documents(user["id"], batch_id),
        batch_name=str(batch["name"]),
    )
    filename = f"receiptsift-{batch_id[:12]}-tax-prep.xlsx"
    return Response(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batches/{batch_id}/export.json")
def export_batch_json(
    request: Request,
    batch_id: str,
    mode: str = Query(default="clean", pattern=r"^(clean|detailed)$"),
) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    if batch_repository.get_batch(user["id"], batch_id) is None:
        raise HTTPException(status_code=404, detail={"code": "batch_not_found", "message": "Batch not found."})
    payload = documents_json(batch_repository.list_documents(user["id"], batch_id), mode=mode)
    filename = f"receiptsift-{batch_id[:12]}-{mode}.json"
    return Response(
        payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batch-documents/{document_id}/export.json")
def export_batch_document_json(
    request: Request,
    document_id: str,
    mode: str = Query(default="clean", pattern=r"^(clean|detailed)$"),
) -> Response:
    user = _require_user(request)
    _require_batch_storage()
    document = batch_repository.get_document(user["id"], document_id)
    if document is None or not isinstance(document.get("result"), dict):
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document result not found."})
    if mode == "detailed":
        payload = detailed_document_result(document["result"], filename=document["filename"], status=document["status"])
    else:
        payload = json.loads(documents_json([document], mode="clean"))["documents"][0]
    filename = f"{Path(document['filename']).stem or 'document'}-{mode}.json"
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/v1/documents", status_code=status.HTTP_201_CREATED)
async def create_document(request: Request, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    user = _require_user(request)
    filename = Path(file.filename or "document.pdf").name
    payload = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "message": f"PDF exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."},
        )
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail={"code": "not_pdf", "message": "Only valid PDF files are accepted."})
    return await run_in_threadpool(_parse_with_reserved_quota, user["id"], payload, filename)


@app.post("/api/v1/documents/sample", status_code=status.HTTP_201_CREATED)
async def create_sample_document(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    payload = await run_in_threadpool(create_sample_pdf)
    return await run_in_threadpool(_parse_with_reserved_quota, user["id"], payload, "cedar-and-finch-sample.pdf")


@app.get("/api/v1/documents")
def list_documents(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    user = _require_user(request)
    documents = diagnostic_repository.list_recent_documents(user["id"], limit=limit, offset=offset)
    return {"documents": documents, "limit": limit, "offset": offset, "storage_enabled": diagnostic_repository.configured}


@app.get("/api/v1/documents/{document_id}")
def get_document(request: Request, document_id: str) -> dict[str, Any]:
    user = _require_user(request)
    document = diagnostic_repository.get_recent_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."})
    return document


@app.patch("/api/v1/documents/{document_id}")
def update_document(request: Request, document_id: str, payload: DocumentPatch) -> dict[str, Any]:
    user = _require_user(request)
    document = diagnostic_repository.get_recent_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."})
    _, corrected = _apply_review_patch(document, payload)
    corrected.update(
        {
            "id": document_id,
            "order_id": document_id,
            "filename": document.get("filename") or "document.pdf",
            "created_at": document.get("created_at"),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    saved = diagnostic_repository.update_recent_document(user["id"], document_id, corrected)
    if saved is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."})
    return saved


@app.delete("/api/v1/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(request: Request, document_id: str) -> Response:
    user = _require_user(request)
    if not diagnostic_repository.delete_recent_document(user["id"], document_id):
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/documents/{document_id}/source.pdf")
def document_source(request: Request, document_id: str) -> Response:
    user = _require_user(request)
    try:
        source = diagnostic_repository.read_recent_source_pdf(user["id"], document_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."}) from error
    return Response(source, media_type="application/pdf", headers={"Cache-Control": "private, no-store"})


@app.get("/api/v1/documents/{document_id}/export.csv")
def export_document(request: Request, document_id: str) -> Response:
    user = _require_user(request)
    document = diagnostic_repository.get_recent_document(user["id"], document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Recent document not found."})
    payload = summary_csv(
        [
            {
                "filename": document.get("filename"),
                "status": document.get("status"),
                "page_count": document.get("page_count"),
                "result": document,
            }
        ]
    )
    filename = f"{Path(document.get('filename') or 'document').stem or 'document'}.csv"
    return Response(payload, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _batch_history(user_id: str) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    if not batch_repository.configured:
        return history
    batch_repository.purge_expired()
    for batch in batch_repository.list_batches(user_id, limit=100, offset=0):
        for document in batch_repository.list_documents(user_id, batch["id"]):
            result = document.get("result")
            if not isinstance(result, dict):
                continue
            summary = DiagnosticRepository._history_summary(
                {
                    **result,
                    "id": document["id"],
                    "order_id": document["id"],
                    "filename": document["filename"],
                    "status": document["status"],
                    "page_count": document["page_count"],
                    "created_at": document["created_at"],
                    "updated_at": document["updated_at"],
                }
            )
            summary.update(
                {
                    "source_type": "batch",
                    "batch_id": batch["id"],
                    "batch_name": batch["name"],
                    "history_expires_at": batch["result_expires_at"],
                }
            )
            history.append(summary)
    return history


@app.get("/api/v1/history")
def unified_history(request: Request, limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
    user = _require_user(request)
    documents = [*diagnostic_repository.list_recent_documents(user["id"], limit=limit), *_batch_history(user["id"])]
    ledger_by_source = {
        (entry.get("source_type"), entry.get("source_id")): entry.get("entry_id")
        for entry in diagnostic_repository.list_ledger_entries(user["id"], limit=10000)
    }
    for document in documents:
        document["ledger_entry_id"] = ledger_by_source.get((document.get("source_type"), document.get("id")))
    documents.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"documents": documents[:limit], "retention_days": diagnostic_repository.history_retention_days}


@app.get("/api/v1/ledger")
def list_ledger(request: Request, limit: int = Query(default=100, ge=1, le=200)) -> dict[str, Any]:
    user = _require_user(request)
    return {"entries": diagnostic_repository.list_ledger_entries(user["id"], limit=limit)}


@app.post("/api/v1/ledger", status_code=status.HTTP_201_CREATED)
def promote_history_to_ledger(request: Request, payload: HistoryPromoteRequest) -> dict[str, Any]:
    user = _require_user(request)
    if payload.source_type == "single":
        result = diagnostic_repository.get_recent_document(user["id"], payload.document_id)
    else:
        batch_document = batch_repository.get_document(user["id"], payload.document_id) if batch_repository.configured else None
        result = batch_document.get("result") if batch_document and isinstance(batch_document.get("result"), dict) else None
        if isinstance(result, dict) and batch_document:
            result = {
                **result,
                "filename": batch_document.get("filename"),
                "created_at": batch_document.get("created_at"),
                "updated_at": batch_document.get("updated_at"),
            }
    if not isinstance(result, dict):
        raise HTTPException(status_code=404, detail={"code": "document_not_found", "message": "Document result not found."})
    return diagnostic_repository.promote_to_ledger(user["id"], payload.source_type, payload.document_id, result)


@app.delete("/api/v1/ledger/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ledger_entry(request: Request, entry_id: str) -> Response:
    user = _require_user(request)
    if not diagnostic_repository.delete_ledger_entry(user["id"], entry_id):
        raise HTTPException(status_code=404, detail={"code": "ledger_entry_not_found", "message": "Ledger entry not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _analytics_html(html: str) -> str:
    marker = '<script src="/analytics.js?v=2" defer></script>'
    if marker not in html and "</body>" in html:
        return html.replace("</body>", f"  {marker}\n  </body>")
    return html


def _shared_ui_html(html: str) -> str:
    marker = '<script src="/locale.js?v=6"></script>'
    if marker not in html and "</head>" in html:
        shared = '<link rel="stylesheet" href="/locale.css?v=5" />\n    <script src="/locale.js?v=6"></script>'
        return html.replace("</head>", f"  {shared}\n  </head>")
    return html


def _html(name: str, *, include_analytics: bool = True) -> HTMLResponse:
    html = _shared_ui_html((settings.root_dir / name).read_text(encoding="utf-8"))
    if include_analytics:
        html = _analytics_html(html)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300"})


def _site_base(request: Request) -> str:
    return settings.site_url or str(request.base_url).rstrip("/")


def _public_html(request: Request, name: str) -> HTMLResponse:
    html = _shared_ui_html(
        _analytics_html((settings.root_dir / name).read_text(encoding="utf-8").replace("{{BASE_URL}}", _site_base(request)))
    )
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300"})


def _requested_language(request: Request) -> str | None:
    language = request.query_params.get("lang")
    return language if language in {"en", "zh"} else None


def _localized_login_location(request: Request, target: str, **extra: str) -> str:
    from urllib.parse import urlencode

    language = _requested_language(request)
    if language is None and not extra:
        return f"/login?next={target}"
    localized_target = f"{target}?lang={language}" if language else target
    params = {"next": localized_target, **extra}
    if language:
        params["lang"] = language
    return f"/login?{urlencode(params)}"


def _safe_next_path(request: Request, fallback: str = "/batches") -> str:
    requested = request.query_params.get("next") or ""
    if requested.startswith("/") and not requested.startswith("//"):
        return requested
    language = _requested_language(request)
    return f"{fallback}?lang={language}" if language else fallback


@app.get("/", include_in_schema=False)
def frontend_index(request: Request) -> Response:
    if _is_app_host(request):
        target = "/batches" if _is_authenticated(request) else "/login"
        return RedirectResponse(target, status_code=303)
    return _public_html(request, "seo.html")


@app.get("/app", include_in_schema=False)
def frontend_app(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    return (
        _html("index.html")
        if _is_authenticated(request)
        else RedirectResponse(_localized_login_location(request, "/app"), status_code=303)
    )


@app.get("/batches", include_in_schema=False)
def frontend_batches(request: Request) -> Response:
    return _html("batches.html") if _is_authenticated(request) else RedirectResponse(
        _localized_login_location(request, "/batches"), status_code=303
    )


@app.get("/login", include_in_schema=False)
def frontend_login(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    if _is_authenticated(request):
        return RedirectResponse(_safe_next_path(request), status_code=303)
    return _html("login.html")


@app.get("/register", include_in_schema=False)
def frontend_register(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    if _is_authenticated(request):
        return RedirectResponse("/batches", status_code=303)
    if settings.owner_only_mode or not (mailer.configured and settings.site_url):
        language = _requested_language(request)
        suffix = f"&lang={language}" if language else ""
        return RedirectResponse(f"/login?registration=closed{suffix}", status_code=303)
    return _html("register.html")


@app.get("/forgot-password", include_in_schema=False)
def frontend_forgot_password(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    if _is_authenticated(request):
        return RedirectResponse("/account", status_code=303)
    return _html("forgot-password.html")


@app.get("/reset-password", include_in_schema=False)
def frontend_reset_password(request: Request, token: str = Query(default="", max_length=256)) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    if not token:
        return RedirectResponse("/forgot-password", status_code=303)
    return _html("reset-password.html")


@app.get("/account", include_in_schema=False)
def frontend_account(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    return _html("account.html") if _is_authenticated(request) else RedirectResponse("/login?next=/account", status_code=303)


@app.get("/admin", include_in_schema=False)
def frontend_admin(request: Request) -> Response:
    if redirect := _configured_app_redirect(request):
        return redirect
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login?next=/admin", status_code=303)
    if not _is_admin_user(user):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Page not found."})
    return _html("admin.html", include_analytics=False)


@app.get("/admin/{section}", include_in_schema=False)
def frontend_admin_section(request: Request, section: str) -> Response:
    if section not in {"runtime", "users", "billing", "traffic", "diagnostics", "audit"}:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Page not found."})
    if redirect := _configured_app_redirect(request):
        return redirect
    user = _current_user(request)
    if user is None:
        return RedirectResponse(f"/login?next=/admin/{section}", status_code=303)
    if not _is_admin_user(user):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Page not found."})
    return _html("admin.html", include_analytics=False)


@app.get("/pricing", include_in_schema=False)
def frontend_pricing() -> FileResponse:
    return _html("pricing.html")


@app.get("/privacy", include_in_schema=False)
def privacy_page() -> FileResponse:
    return _html("privacy.html")


@app.get("/terms", include_in_schema=False)
def terms_page() -> FileResponse:
    return _html("terms.html")


@app.get("/cookies", include_in_schema=False)
def cookies_page() -> FileResponse:
    return _html("cookies.html")


@app.get("/refunds", include_in_schema=False)
def refunds_page() -> FileResponse:
    return _html("refunds.html")


@app.get("/resources", include_in_schema=False)
def resources_page(request: Request) -> HTMLResponse:
    return _public_html(request, "content/resources.html")


@app.get("/pdf-receipt-parser", include_in_schema=False)
def receipt_parser_page(request: Request) -> HTMLResponse:
    return _public_html(request, "content/pdf-receipt-parser.html")


@app.get("/receipt-to-csv", include_in_schema=False)
def receipt_to_csv_page(request: Request) -> HTMLResponse:
    return _public_html(request, "content/receipt-to-csv.html")


@app.get("/guides/how-to-extract-data-from-pdf-receipts", include_in_schema=False)
def extraction_guide_page(request: Request) -> HTMLResponse:
    return _public_html(request, "content/how-to-extract-data-from-pdf-receipts.html")


@app.get("/compare/receipt-parser-vs-manual-data-entry", include_in_schema=False)
def parser_comparison_page(request: Request) -> HTMLResponse:
    return _public_html(request, "content/receipt-parser-vs-manual-data-entry.html")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    base = _site_base(request)
    pages = "".join(
        f"<url><loc>{base}{path}</loc></url>"
        for path in (
            "/",
            "/pdf-receipt-parser",
            "/receipt-to-csv",
            "/resources",
            "/guides/how-to-extract-data-from-pdf-receipts",
            "/compare/receipt-parser-vs-manual-data-entry",
            "/privacy",
            "/terms",
            "/cookies",
            "/refunds",
        )
    )
    return Response(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{pages}</urlset>',
        media_type="application/xml",
    )


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> Response:
    if _is_app_host(request):
        body = "User-agent: *\nDisallow: /\n"
    else:
        body = (
            "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /app\nDisallow: /batches\nDisallow: /account\nDisallow: /admin\n"
            "Disallow: /login\nDisallow: /register\nDisallow: /forgot-password\nDisallow: /reset-password\n"
            f"Disallow: /verify-email\n\nSitemap: {_site_base(request)}/sitemap.xml\n"
        )
    return Response(body, media_type="text/plain")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="7" fill="#1d1d1f"/>'
        '<path d="M8 10h6v14H8zm10-5h6v19h-6z" fill="#fbfbfd"/></svg>'
    )
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/{asset_name}", include_in_schema=False)
def frontend_asset(asset_name: str) -> FileResponse:
    allowed = {
        "app.js": "application/javascript",
        "styles.css": "text/css",
        "app-shell.css": "text/css",
        "seo.js": "application/javascript",
        "seo.css": "text/css",
        "legal.css": "text/css",
        "content.css": "text/css",
        "login.js": "application/javascript",
        "register.js": "application/javascript",
        "forgot-password.js": "application/javascript",
        "reset-password.js": "application/javascript",
        "account.js": "application/javascript",
        "pricing.js": "application/javascript",
        "analytics.js": "application/javascript",
        "admin.js": "application/javascript",
        "auth.css": "text/css",
        "pricing.css": "text/css",
        "admin.css": "text/css",
        "admin-diagnostics.css": "text/css",
        "batch-workspace.js": "application/javascript",
        "batch-workspace.css": "text/css",
        "locale.js": "application/javascript",
        "locale.css": "text/css",
        "robots.txt": "text/plain",
    }
    media_type = allowed.get(asset_name)
    asset_path = settings.root_dir / asset_name
    if media_type is None or not asset_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Asset not found."})
    return FileResponse(asset_path, media_type=media_type)
