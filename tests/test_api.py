import json
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend import server
from backend.atlas_parser import AtlasParseError
from backend.batch_repository import BatchRepository
from backend.batch_worker import BatchWorker
from backend.billing import BillingError
from backend.billing_repository import BillingRepository
from backend.diagnostics import DiagnosticRepository, canonical_result_payload
from backend.operations import OperationsRepository
from backend.repository import DocumentRepository
from backend.runtime_security import InMemoryRateLimiter, RuntimeMonitor
from backend.sample import create_sample_pdf

TEST_PASSWORD = "CorrectHorse2026!"
NEW_PASSWORD = "NewCorrectHorse2026!"


class FakeMailer:
    configured = True

    def __init__(self):
        self.messages: list[dict[str, str]] = []

    def send(self, **message):
        self.messages.append(message)


class DisabledMailer:
    configured = False


class FakePayPal:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.cancelled: list[str] = []
        self.refunded: list[tuple[str, str, str, str]] = []

    def cancel_subscription(self, subscription_id: str, _reason: str) -> None:
        if self.fail:
            raise BillingError("paypal_api_error", "PayPal rejected the request.")
        self.cancelled.append(subscription_id)

    def refund_sale(self, payment_id: str, amount: str, currency: str, reason: str) -> dict[str, str]:
        if self.fail:
            raise BillingError("paypal_api_error", "PayPal rejected the request.")
        self.refunded.append((payment_id, amount, currency, reason))
        return {"id": "R-test", "state": "completed"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    preview_dir = data_dir / "previews"
    preview_dir.mkdir(parents=True)
    test_settings = replace(
        server.settings,
        data_dir=data_dir,
        session_secret="test-session-secret",
        secure_cookies=False,
        site_url="http://testserver",
        owner_only_mode=False,
        owner_email="",
        batch_encryption_key=Fernet.generate_key().decode("ascii"),
        batch_worker_mode="disabled",
    )
    monkeypatch.setattr(server, "settings", test_settings)
    monkeypatch.setattr(server, "repository", DocumentRepository(test_settings.database_path, preview_dir))
    monkeypatch.setattr(server, "billing_repository", BillingRepository(test_settings.database_path))
    monkeypatch.setattr(server, "operations_repository", OperationsRepository(test_settings.database_path))
    monkeypatch.setattr(
        server,
        "diagnostic_repository",
        DiagnosticRepository(
            test_settings.database_path,
            data_dir / "diagnostics",
            Fernet.generate_key().decode("ascii"),
            14,
        ),
    )
    monkeypatch.setattr(
        server,
        "batch_repository",
        BatchRepository(
            test_settings.database_path,
            data_dir / "batch-objects",
            test_settings.batch_encryption_key,
            source_retention_days=30,
            result_retention_days=90,
        ),
    )
    monkeypatch.setattr(server, "mailer", FakeMailer())
    monkeypatch.setattr(server, "paypal_client", FakePayPal())
    monkeypatch.setattr(server, "auth_rate_limiter", InMemoryRateLimiter())
    monkeypatch.setattr(server, "runtime_monitor", RuntimeMonitor(data_dir / "runtime-operations.json"))
    with TestClient(server.app) as test_client:
        yield test_client


def register(client: TestClient, email: str = "owner@example.com") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["verification_required"] is True
    message = next(message for message in reversed(server.mailer.messages) if message["subject"] == "Verify your ReceiptSift email")
    token = re.search(r"[?&]token=([^\s]+)", message["text"]).group(1)
    verified = client.get(f"/verify-email?token={token}", follow_redirects=False)
    assert verified.status_code == 303
    login = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    return login.json()["user"]


def test_missing_provider_usage_keeps_conservative_cost_reservation():
    assert server._conservative_usage_cost("test/model", {}, 0.25) == 0.25
    assert (
        server._conservative_usage_cost(
            "test/model",
            {"input_tokens": 1_000_000, "output_tokens": 0},
            0.25,
        )
        == server.settings.atlas_primary_input_usd_per_million
    )


def test_health_reports_privacy_and_ocr(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["source_pdf_retained"] is True
    assert response.json()["retention_days"] == 7
    assert response.json()["document_storage_enabled"] is True
    assert response.json()["access_protected"] is True
    assert response.json()["parse_audit_metadata_retained"] is True
    assert response.json()["diagnostic_reporting_available"] is True
    assert isinstance(response.json()["ocr_available"], bool)
    assert response.json()["daily_ai_budget_guard_enabled"] is True
    assert response.json()["capacity_monitoring_enabled"] is True
    assert response.json()["auth_rate_limit_scope"] == "single_replica_memory"
    assert response.json()["pdf_active_content_rejected"] is True
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_static_allow_list_does_not_expose_backend_or_data(client):
    assert client.get("/backend/server.py").status_code == 404
    assert client.get("/data/clearledger.sqlite3").status_code == 404
    assert client.get("/app.js").status_code == 200
    assert client.get("/auth.css").status_code == 200
    assert client.get("/app-shell.css").status_code == 200


def test_public_site_and_account_routes_are_separate(client):
    public_page = client.get("/")
    tool_page = client.get("/app", follow_redirects=False)

    assert public_page.status_code == 200
    assert "PDF Receipt Parser &amp; Bill Data Extractor" in public_page.text
    assert "Receipt data" in public_page.text
    assert tool_page.status_code == 303
    assert tool_page.headers["location"].startswith("/login")
    assert client.get("/register").status_code == 200
    assert client.get("/forgot-password").status_code == 200
    assert client.get("/pricing").status_code == 200
    assert client.get("/account", follow_redirects=False).status_code == 303
    assert client.get("/privacy").status_code == 200
    assert client.get("/terms").status_code == 200
    assert client.get("/sitemap.xml").headers["content-type"].startswith("application/xml")


def test_public_language_follows_open_app_and_survives_login_redirect(client):
    public_page = client.get("/")
    seo_script = client.get("/seo.js")
    app_script = client.get("/app.js")
    locale_script = client.get("/locale.js")

    assert 'href="/app"' in public_page.text
    assert "window.ReceiptSiftLocale" in seo_script.text
    assert "window.ReceiptSiftLocale" in app_script.text
    assert 'localStorage.setItem(STORAGE_KEY, language)' in locale_script.text
    assert 'url.searchParams.set("lang", language)' in locale_script.text

    chinese_redirect = client.get("/app?lang=zh", follow_redirects=False)
    english_redirect = client.get("/app?lang=en", follow_redirects=False)
    assert chinese_redirect.headers["location"] == "/login?next=%2Fapp%3Flang%3Dzh&lang=zh"
    assert english_redirect.headers["location"] == "/login?next=%2Fapp%3Flang%3Den&lang=en"


def test_docker_image_includes_shared_locale_assets():
    dockerfile = (server.settings.root_dir / "Dockerfile").read_text(encoding="utf-8")
    assert "locale.css" in dockerfile
    assert "locale.js" in dockerfile


def test_single_document_review_exposes_side_by_side_compare_mode(client):
    register(client)

    page = client.get("/app")
    script = client.get("/app.js")
    styles = client.get("/styles.css")

    assert 'id="reviewWorkspace"' in page.text
    assert 'data-review-mode="compare"' in page.text
    assert 'id="compareModeButton"' in page.text
    assert 'function setReviewMode(nextMode' in script.text
    assert 'preview.scrollTo' in script.text
    assert '.review-workspace.compare-mode' in styles.text


def test_configured_public_and_app_hosts_redirect_protected_pages(client, monkeypatch):
    host_settings = replace(
        server.settings,
        public_host="www.receiptsift.example",
        app_host="app.receiptsift.example",
        app_host_redirect_enabled=True,
    )
    monkeypatch.setattr(server, "settings", host_settings)
    public_headers = {"host": "www.receiptsift.example", "x-forwarded-proto": "https"}
    app_headers = {"host": "app.receiptsift.example", "x-forwarded-proto": "https"}

    redirected = client.get("/app", headers=public_headers, follow_redirects=False)
    assert redirected.status_code == 308
    assert redirected.headers["location"] == "https://app.receiptsift.example/app"

    app_root = client.get("/", headers=app_headers, follow_redirects=False)
    assert app_root.status_code == 303
    assert app_root.headers["location"] == "/login"
    assert app_root.headers["x-robots-tag"] == "noindex, nofollow"
    assert client.get("/login", headers=app_headers).status_code == 200

    register(client)
    authenticated_root = client.get("/", headers=app_headers, follow_redirects=False)
    assert authenticated_root.status_code == 303
    assert authenticated_root.headers["location"] == "/batches"


def test_app_host_redirect_stays_off_until_explicitly_enabled(client, monkeypatch):
    monkeypatch.setattr(
        server,
        "settings",
        replace(server.settings, app_host="app.receiptsift.example", app_host_redirect_enabled=False),
    )

    response = client.get("/app", headers={"host": "www.receiptsift.example"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/app"


def test_open_registration_and_login(client):
    assert client.get("/api/v1/documents").status_code == 401
    user = register(client)
    assert user["email"] == "owner@example.com"
    assert client.get("/app").status_code == 200
    assert client.get("/batches").status_code == 200
    assert client.get("/login", follow_redirects=False).headers["location"] == "/batches"
    assert client.get("/register", follow_redirects=False).headers["location"] == "/batches"
    assert 'href="/batches" aria-label="ReceiptSift batch workspace"' in client.get("/batches").text
    assert 'href="/batches">Batch workspace</a>' in client.get("/account").text
    login_script = client.get("/login.js").text
    assert "safeTarget(requested)" in login_script

    client.post("/api/auth/logout")
    rejected_login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "wrong"},
    )
    assert rejected_login.status_code == 401

    accepted = client.post(
        "/api/auth/login",
        json={"email": "OWNER@example.com", "password": TEST_PASSWORD},
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["id"] == user["id"]


def test_language_is_preserved_through_protected_route_redirects(client):
    batch_redirect = client.get("/batches?lang=zh", follow_redirects=False)
    app_redirect = client.get("/app?lang=zh", follow_redirects=False)

    assert batch_redirect.status_code == 303
    assert batch_redirect.headers["location"] == "/login?next=%2Fbatches%3Flang%3Dzh&lang=zh"
    assert app_redirect.headers["location"] == "/login?next=%2Fapp%3Flang%3Dzh&lang=zh"

    login_page = client.get(batch_redirect.headers["location"])
    assert 'src="/locale.js?v=6"' in login_page.text
    assert 'id="loginContext"' in login_page.text


def test_product_language_selector_has_five_locales_in_requested_order(client):
    locale_source = client.get("/locale.js").text
    assert 'const localeOrder = ["en", "hi", "es", "ar", "zh"]' in locale_source

    account_source = (server.settings.root_dir / "account.html").read_text(encoding="utf-8")
    positions = [account_source.index(f'value="{code}"') for code in ("en", "hi", "es", "ar", "zh")]
    assert positions == sorted(positions)
    assert "简体中文" in account_source


def test_owner_only_registration_page_redirects_to_truthful_login_state(client, monkeypatch):
    monkeypatch.setattr(server, "settings", replace(server.settings, owner_only_mode=True))

    response = client.get("/register?lang=zh", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?registration=closed&lang=zh"
    pricing = client.get("/pricing").text
    assert "data-registration-action" in pricing
    assert "Private beta · Sign in" in pricing
    assert client.get("/locale.js").headers["content-type"].startswith("application/javascript")


def test_product_shell_and_retention_copy_are_unambiguous(client):
    root = server.settings.root_dir
    app_html = (root / "index.html").read_text(encoding="utf-8")
    batch_html = (root / "batches.html").read_text(encoding="utf-8")
    account_html = (root / "account.html").read_text(encoding="utf-8")
    pricing_html = (root / "pricing.html").read_text(encoding="utf-8")
    account_styles = (root / "auth.css").read_text(encoding="utf-8")
    batch_styles = (root / "batch-workspace.css").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    shell_styles = (root / "app-shell.css").read_text(encoding="utf-8")
    pricing_script = (root / "pricing.js").read_text(encoding="utf-8")

    assert "navSecurity" not in app_html
    assert "privacyButton" not in app_html
    assert "helpButton" not in app_html
    assert "subnavTryButton" not in app_html
    assert all(label in app_html for label in ("单份解析", "批量工作台", "套餐", "账户", "帮助"))
    assert all(path in batch_html for path in ('href="/app"', 'href="/batches"', 'href="/pricing"', 'href="/account"', 'href="/resources"'))
    shell_paths = ('href="/app"', 'href="/batches"', 'href="/pricing"', 'href="/account"', 'href="/resources"')
    assert all(path in account_html for path in shell_paths)
    assert all(path in pricing_html for path in shell_paths)
    assert all('data-app-help' in page for page in (app_html, batch_html, account_html, pricing_html))
    assert 'class="account-nav"' in account_html
    assert 'class="global-links"' in account_html
    assert 'aria-current="page" href="/account"' in account_html
    assert ".account-nav { height: 52px" in account_styles
    assert ".global-links a.active::after" in account_styles
    assert 'id="batchSignOutButton"' in batch_html
    assert ".topbar {\n  height: 52px" in batch_styles
    assert ".global-links { width: 100%" in styles
    assert all('href="/app-shell.css?v=4"' in page for page in (app_html, batch_html, account_html, pricing_html))
    assert 'aria-current="page" href="/pricing"' in pricing_html
    assert 'id="pricingAuthAction"' in pricing_html
    assert "min-width: 120px" in shell_styles
    assert "grid-template-columns: var(--app-shell-side) minmax(0, 1fr) var(--app-shell-side)" in shell_styles
    assert ".global-links > button" in shell_styles
    assert 'class="operations-action hidden" id="operationsLink"' in account_html

    public_page = client.get("/").text
    pricing_page = client.get("/pricing").text
    assert "Single-document and batch history is encrypted for up to 7 days" in public_page
    assert "Receipt files and extracted results are not retained" not in public_page
    assert "Single-document and batch source files, results, and corrections are encrypted for up to 7 days" in pricing_page
    assert "Checkout unavailable" in pricing_script


def test_registration_fails_closed_when_transactional_email_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(server, "mailer", DisabledMailer())

    response = client.post(
        "/api/auth/register",
        json={"email": "blocked@example.com", "password": TEST_PASSWORD},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "registration_email_unavailable"
    assert server.repository.get_user_by_email("blocked@example.com") is None
    assert client.get("/api/health").json()["registration_open"] is False


def test_owner_only_mode_blocks_registration_other_accounts_and_existing_sessions(client, monkeypatch):
    register(client, "owner@example.com")
    client.post("/api/auth/logout")

    with TestClient(server.app) as guest_client:
        register(guest_client, "guest@example.com")
        owner_settings = replace(
            server.settings,
            owner_only_mode=True,
            owner_email="owner@example.com",
        )
        monkeypatch.setattr(server, "settings", owner_settings)

        assert guest_client.get("/api/v1/account").status_code == 401
        guest_login = guest_client.post(
            "/api/auth/login",
            json={"email": "guest@example.com", "password": TEST_PASSWORD},
        )
        assert guest_login.status_code == 403
        assert guest_login.json()["error"]["code"] == "owner_only_access"

        blocked_registration = guest_client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": TEST_PASSWORD},
        )
        assert blocked_registration.status_code == 403
        assert server.repository.get_user_by_email("new@example.com") is None

        owner_login = client.post(
            "/api/auth/login",
            json={"email": "OWNER@example.com", "password": TEST_PASSWORD},
        )
        assert owner_login.status_code == 200
        assert client.get("/api/v1/account").status_code == 200

        status_payload = client.get("/api/auth/status").json()
        assert status_payload["access_mode"] == "owner_only"
        assert status_payload["owner_only_mode"] is True
        assert status_payload["owner_access_configured"] is True
        assert status_payload["registration_open"] is False

        health_payload = client.get("/api/health").json()
        assert health_payload["owner_only_mode"] is True
        assert health_payload["owner_access_configured"] is True
        assert health_payload["registration_open"] is False


def test_login_rate_limit_is_enforced_without_database_state(client, monkeypatch):
    limited_settings = replace(
        server.settings,
        auth_login_limit=2,
        auth_login_window_seconds=900,
    )
    monkeypatch.setattr(server, "settings", limited_settings)

    for _ in range(2):
        rejected = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        )
        assert rejected.status_code == 401

    limited = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limit_reached"
    assert int(limited.headers["retry-after"]) > 0


def test_email_verification_and_password_reset(client):
    registered = client.post(
        "/api/auth/register",
        json={"email": "verify@example.com", "password": TEST_PASSWORD},
    )
    assert registered.status_code == 201
    assert registered.json()["email_sent"] is True
    assert client.post("/api/auth/login", json={"email": "verify@example.com", "password": TEST_PASSWORD}).status_code == 403

    verify_message = server.mailer.messages[-1]
    verify_token = re.search(r"[?&]token=([^\s]+)", verify_message["text"]).group(1)
    assert client.get(f"/verify-email?token={verify_token}", follow_redirects=False).headers["location"] == "/login?verified=1"
    assert client.get(f"/verify-email?token={verify_token}", follow_redirects=False).headers["location"] == "/login?verification=invalid"
    assert client.post("/api/auth/login", json={"email": "verify@example.com", "password": TEST_PASSWORD}).status_code == 200

    second_session = TestClient(server.app)
    assert second_session.post("/api/auth/login", json={"email": "verify@example.com", "password": TEST_PASSWORD}).status_code == 200
    forgotten = client.post("/api/auth/password/forgot", json={"email": "verify@example.com"})
    unknown = client.post("/api/auth/password/forgot", json={"email": "missing@example.com"})
    assert forgotten.status_code == unknown.status_code == 202
    assert forgotten.json() == unknown.json()
    reset_message = server.mailer.messages[-1]
    reset_token = re.search(r"[?&]token=([^\s]+)", reset_message["text"]).group(1)
    reset = client.post("/api/auth/password/reset", json={"token": reset_token, "password": NEW_PASSWORD})
    assert reset.status_code == 200
    assert client.post("/api/auth/login", json={"email": "verify@example.com", "password": TEST_PASSWORD}).status_code == 401
    assert second_session.get("/api/v1/account").status_code == 401
    assert client.post("/api/auth/login", json={"email": "verify@example.com", "password": NEW_PASSWORD}).status_code == 200
    assert client.post("/api/auth/password/reset", json={"token": reset_token, "password": TEST_PASSWORD}).status_code == 400
    second_session.close()


def test_recent_document_history_is_private_to_each_user(client):
    register(client, "first@example.com")
    first_document = client.post("/api/v1/documents/sample").json()
    assert first_document["storage_mode"] == "recent_7d"
    assert first_document["preview_url"] is None
    assert first_document["preview_data_url"].startswith("data:image/png;base64,")
    listed = client.get("/api/v1/documents").json()
    assert listed["storage_enabled"] is True
    assert [item["id"] for item in listed["documents"]] == [first_document["id"]]

    with TestClient(server.app) as second_client:
        register(second_client, "second@example.com")
        assert second_client.get("/api/v1/documents").json()["documents"] == []
        assert second_client.get(f"/api/v1/documents/{first_document['id']}").status_code == 404
        assert second_client.get(f"/api/v1/documents/{first_document['id']}/source.pdf").status_code == 404
        assert second_client.delete(f"/api/v1/documents/{first_document['id']}").status_code == 404
        second_document = second_client.post("/api/v1/documents/sample").json()

    assert first_document["id"] != second_document["id"]


def test_atlas_outage_falls_back_to_local_parser(client, monkeypatch):
    register(client)
    atlas_settings = replace(server.settings, parser_provider="atlas", atlas_api_key="test-key")
    monkeypatch.setattr(server, "settings", atlas_settings)

    def unavailable(*_args, **_kwargs):
        raise AtlasParseError("service unavailable")

    monkeypatch.setattr(server, "parse_pdf_with_markitdown_router", unavailable)
    response = client.post("/api/v1/documents/sample")

    assert response.status_code == 201
    result = response.json()
    assert result["fields"]["total"]["value"] == 27.06
    assert result["extraction_method"] == "embedded_text_atlas_fallback"
    assert "atlas_unavailable" in {warning["code"] for warning in result["warnings"]}


def test_atlas_review_result_runs_independent_gpt_verifier(client, monkeypatch):
    register(client)
    atlas_settings = replace(
        server.settings,
        parser_provider="atlas",
        atlas_api_key="test-key",
        gpt_verifier_enabled=True,
    )
    monkeypatch.setattr(server, "settings", atlas_settings)

    def review_result(pdf_bytes, **kwargs):
        result, preview = server.parse_pdf(pdf_bytes, kwargs["max_pages"])
        result["status"] = "needs_review"
        result["quality_gate"] = {"decision": "verify"}
        return result, preview

    calls = []

    def verified(images, extraction, **kwargs):
        calls.append((images, extraction, kwargs))
        return {
            "model": "openai/gpt-5.6-terra",
            "document_type": "receipt",
            "verdict": "corrected",
            "confidence": 0.97,
            "independent": {"total": 27.06, "items": []},
            "discrepancies": [{"field": "total", "severity": "high"}],
            "notes": [],
            "usage": {"calls": 1},
        }

    monkeypatch.setattr(server, "parse_pdf_with_markitdown_router", review_result)
    monkeypatch.setattr(server, "verify_receipt_with_gpt", verified)
    response = client.post("/api/v1/documents/sample")

    assert response.status_code == 201
    result = response.json()
    assert len(calls) == 1
    assert result["verification"]["status"] == "completed"
    assert result["verification"]["verdict"] == "corrected"
    assert result["status"] == "needs_review"
    assert "independent_verification_required" in {warning["code"] for warning in result["warnings"]}


def test_atlas_ready_result_skips_gpt_verifier(client, monkeypatch):
    register(client)
    atlas_settings = replace(
        server.settings,
        parser_provider="atlas",
        atlas_api_key="test-key",
        gpt_verifier_enabled=True,
    )
    monkeypatch.setattr(server, "settings", atlas_settings)

    def ready_result(pdf_bytes, **kwargs):
        result, preview = server.parse_pdf(pdf_bytes, kwargs["max_pages"])
        result["status"] = "ready"
        result["quality_gate"] = {"decision": "accept"}
        return result, preview

    monkeypatch.setattr(server, "parse_pdf_with_markitdown_router", ready_result)
    monkeypatch.setattr(
        server,
        "verify_receipt_with_gpt",
        lambda *_args, **_kwargs: pytest.fail("Verifier must not run after the quality gate passes."),
    )
    result = client.post("/api/v1/documents/sample").json()

    assert result["verification"] == {"status": "not_run", "reason": "quality_gate_passed"}


def test_usage_account_export_and_deletion(client):
    user = register(client)
    document = client.post("/api/v1/documents/sample").json()
    preview_path = server.settings.preview_dir / f"{document['id']}.png"
    assert not preview_path.exists()

    assert client.post("/api/v1/account/usage/csv-export").status_code == 202
    usage = client.get("/api/v1/account/usage").json()
    assert usage["documents_parsed"] == 1
    assert usage["pages_processed"] == document["page_count"]
    assert usage["csv_exports"] == 1
    assert usage["saved_documents"] == 1
    assert usage["document_storage_enabled"] is True

    exported = client.get("/api/v1/account/export.json")
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith('"receiptsift-account-export.json"')
    export_body = exported.json()
    assert export_body["account"]["id"] == user["id"]
    assert "password_hash" not in export_body["account"]
    assert "documents" not in export_body

    wrong_password = client.request("DELETE", "/api/v1/account", json={"password": "wrong"})
    assert wrong_password.status_code == 401
    assert not preview_path.exists()

    deleted = client.request("DELETE", "/api/v1/account", json={"password": TEST_PASSWORD})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert not preview_path.exists()
    assert server.repository.get_user(user["id"]) is None
    assert client.get("/api/v1/account").status_code == 401


def test_account_deletion_cancels_paypal_before_removing_data(client, monkeypatch):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-active",
        provider_plan_id="P-pro",
        status="ACTIVE",
    )
    paypal = FakePayPal()
    monkeypatch.setattr(server, "paypal_client", paypal)

    deleted = client.request("DELETE", "/api/v1/account", json={"password": TEST_PASSWORD})

    assert deleted.status_code == 200
    assert paypal.cancelled == ["I-active"]
    assert server.repository.get_user(user["id"]) is None
    assert server.billing_repository.get_for_user(user["id"]) is None


def test_account_is_kept_when_paypal_cancellation_fails(client, monkeypatch):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-active",
        provider_plan_id="P-pro",
        status="ACTIVE",
    )
    monkeypatch.setattr(server, "paypal_client", FakePayPal(fail=True))

    rejected = client.request("DELETE", "/api/v1/account", json={"password": TEST_PASSWORD})

    assert rejected.status_code == 502
    assert rejected.json()["error"]["code"] == "subscription_cancellation_failed"
    assert server.repository.get_user(user["id"]) is not None


def test_recent_document_can_be_reopened_corrected_exported_and_deleted(client):
    register(client)
    created = client.post("/api/v1/documents/sample")
    assert created.status_code == 201
    document = created.json()
    document_id = document["id"]
    assert document["fields"]["total"]["value"] == 27.06
    assert document["preview_data_url"].startswith("data:image/png;base64,")

    assert client.get("/api/v1/documents").json()["documents"][0]["id"] == document_id
    reopened = client.get(f"/api/v1/documents/{document_id}")
    assert reopened.status_code == 200
    assert reopened.json()["fields"]["total"]["value"] == 27.06

    updated = client.patch(
        f"/api/v1/documents/{document_id}",
        json={"merchant": "CEDAR & FINCH KITCHEN ATX", "vendor_name": "CEDAR & FINCH KITCHEN ATX", "total": 28.00},
    )
    assert updated.status_code == 200
    assert updated.json()["fields"]["merchant"]["value"] == "CEDAR & FINCH KITCHEN ATX"
    assert updated.json()["fields"]["total"]["value"] == 28.0

    exported = client.get(f"/api/v1/documents/{document_id}/export.csv")
    assert exported.status_code == 200
    assert "CEDAR & FINCH KITCHEN ATX" in exported.content.decode("utf-8-sig")

    source = client.get(f"/api/v1/documents/{document_id}/source.pdf")
    assert source.status_code == 200
    assert source.content.startswith(b"%PDF-")

    deleted = client.delete(f"/api/v1/documents/{document_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404


def test_recent_document_can_be_confirmed_into_ledger_without_raw_pdf(client):
    register(client)
    document = client.post("/api/v1/documents/sample").json()

    promoted = client.post(
        "/api/v1/ledger",
        json={"source_type": "single", "document_id": document["id"]},
    )
    assert promoted.status_code == 201
    entry = promoted.json()
    assert entry["fields"]["total"]["value"] == 27.06
    assert "preview_data_url" not in entry
    assert "pages" not in entry

    assert client.delete(f"/api/v1/documents/{document['id']}").status_code == 204
    ledger = client.get("/api/v1/ledger").json()["entries"]
    assert [item["entry_id"] for item in ledger] == [entry["entry_id"]]

    assert client.delete(f"/api/v1/ledger/{entry['entry_id']}").status_code == 204
    assert client.get("/api/v1/ledger").json()["entries"] == []


def test_expired_recent_history_removes_encrypted_source_and_result(client):
    register(client)
    document = client.post("/api/v1/documents/sample").json()
    document_dir = server.diagnostic_repository.history_dir / document["id"]
    assert (document_dir / "source.pdf.enc").is_file()
    assert (document_dir / "result.json.enc").is_file()

    with server.diagnostic_repository._connect() as connection:
        connection.execute(
            "UPDATE recent_documents SET expires_at = ? WHERE order_id = ?",
            ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), document["id"]),
        )

    assert client.get("/api/v1/history").json()["documents"] == []
    assert not document_dir.exists()


def test_parse_order_audit_and_opt_in_encrypted_diagnostic_case(client, monkeypatch):
    user = register(client)
    source_pdf = create_sample_pdf()
    created = client.post(
        "/api/v1/documents",
        files={"file": ("source-receipt.pdf", source_pdf, "application/pdf")},
    )
    assert created.status_code == 201
    document = created.json()
    assert document["order_id"] == document["id"]

    order = server.diagnostic_repository.get_parse_order(user["id"], document["order_id"])
    assert order is not None
    assert order["status"] == document["status"]
    assert order["page_count"] == document["page_count"]
    assert order["output_sha256"]
    serialized_order = json.dumps(order)
    assert "source-receipt.pdf" not in serialized_order
    assert "Cedar & Finch" not in serialized_order
    assert "27.06" not in serialized_order

    original = canonical_result_payload(document)
    corrected = json.loads(json.dumps(original))
    corrected["fields"]["total"]["value"] = 28.06
    reported = client.post(
        "/api/v1/diagnostic-cases",
        data={
            "order_id": document["order_id"],
            "description": "The total should be 28.06.",
            "consent": "true",
            "original_result_json": json.dumps(original),
            "corrected_result_json": json.dumps(corrected),
        },
        files={"file": ("source-receipt.pdf", source_pdf, "application/pdf")},
    )
    assert reported.status_code == 201
    case = reported.json()["case"]
    assert case["has_source_pdf"] is True
    case_dir = server.diagnostic_repository.evidence_dir / case["case_id"]
    encrypted_report = (case_dir / "report.json.enc").read_bytes()
    encrypted_pdf = (case_dir / "source.pdf.enc").read_bytes()
    assert b"The total should be" not in encrypted_report
    assert b"%PDF-" not in encrypted_pdf

    monkeypatch.setattr(server, "settings", replace(server.settings, admin_email="owner@example.com"))
    listed = client.get("/api/admin/diagnostic-cases")
    assert listed.status_code == 200
    assert listed.json()["cases"][0]["case_id"] == case["case_id"]
    detail = client.get(f"/api/admin/diagnostic-cases/{case['case_id']}")
    assert detail.status_code == 200
    assert detail.json()["report"]["description"] == "The total should be 28.06."
    source = client.get(f"/api/admin/diagnostic-cases/{case['case_id']}/source.pdf")
    assert source.status_code == 200
    assert source.content == source_pdf

    deleted = client.delete(f"/api/v1/diagnostic-cases/{case['case_id']}")
    assert deleted.status_code == 204
    assert not case_dir.exists()


def test_diagnostic_case_requires_explicit_consent(client):
    register(client)
    document = client.post("/api/v1/documents/sample").json()
    original = canonical_result_payload(document)
    response = client.post(
        "/api/v1/diagnostic-cases",
        data={
            "order_id": document["order_id"],
            "description": "Wrong merchant.",
            "consent": "false",
            "original_result_json": json.dumps(original),
            "corrected_result_json": json.dumps(original),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "diagnostic_consent_required"
    assert server.diagnostic_repository.list_cases(server.repository.get_user_by_email("owner@example.com")["id"]) == []


def test_expired_diagnostic_case_is_purged_with_encrypted_files(client):
    register(client)
    document = client.post("/api/v1/documents/sample").json()
    original = canonical_result_payload(document)
    reported = client.post(
        "/api/v1/diagnostic-cases",
        data={
            "order_id": document["order_id"],
            "description": "The date is incorrect.",
            "consent": "true",
            "original_result_json": json.dumps(original),
            "corrected_result_json": json.dumps(original),
        },
    )
    assert reported.status_code == 201
    case_id = reported.json()["case"]["case_id"]
    case_dir = server.diagnostic_repository.evidence_dir / case_id
    assert case_dir.exists()
    with server.diagnostic_repository._connect() as connection:
        connection.execute(
            "UPDATE diagnostic_cases SET expires_at = ? WHERE case_id = ?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), case_id),
        )

    assert client.get("/api/v1/diagnostic-cases").json()["cases"] == []
    assert not case_dir.exists()


def test_free_plan_blocks_the_sixth_successful_pdf(client):
    register(client)

    accepted = [client.post("/api/v1/documents/sample") for _ in range(5)]
    blocked = client.post("/api/v1/documents/sample")

    assert all(response.status_code == 201 for response in accepted)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "monthly_limit_reached"
    assert client.get("/api/v1/account/usage").json()["documents_parsed"] == 5


def test_active_pro_subscription_unlocks_pro_allowance(client):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-pro-quota",
        provider_plan_id=server.billing_settings.paypal_pro_plan_id,
        status="ACTIVE",
    )

    responses = [client.post("/api/v1/documents/sample") for _ in range(3)]
    billing = client.get("/api/billing/me")

    assert all(response.status_code == 201 for response in responses)
    assert billing.status_code == 200
    assert billing.json()["entitlement"]["plan"] == "pro"
    assert billing.json()["entitlement"]["monthly_document_limit"] == 300
    assert billing.json()["entitlement"]["monthly_page_limit"] == 500


def test_owner_plan_override_grants_pro_without_fake_paypal_subscription(client, monkeypatch):
    monkeypatch.setattr(
        server,
        "settings",
        replace(server.settings, owner_email="owner@example.com", owner_plan_code="pro"),
    )
    user = register(client, "owner@example.com")

    billing = client.get("/api/billing/me")
    created_batch = client.post("/api/v1/batches", json={"name": "Owner Pro batch"})

    assert billing.status_code == 200
    assert billing.json()["subscription"] is None
    assert billing.json()["entitlement"]["plan"] == "pro"
    assert billing.json()["entitlement"]["monthly_document_limit"] == 300
    assert billing.json()["entitlement"]["monthly_page_limit"] == 500
    assert billing.json()["entitlement"]["max_files_per_batch"] == 100
    assert created_batch.status_code == 201
    assert server.billing_repository.get_for_user(user["id"]) is None


def test_upload_rejects_non_pdf_signature(client):
    register(client)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "not_pdf"


def test_batch_api_stages_starts_duplicates_reviews_and_exports_csv(client):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-plus-batch",
        provider_plan_id="P-plus",
        status="ACTIVE",
        plan_code="plus",
    )
    created = client.post("/api/v1/batches", json={"name": "August receipts"})
    assert created.status_code == 201
    batch_id = created.json()["id"]
    source = create_sample_pdf()

    uploaded = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[
            ("files", ("receipt-01.pdf", source, "application/pdf")),
            ("files", ("duplicate.pdf", source, "application/pdf")),
        ],
    )
    assert uploaded.status_code == 202
    assert uploaded.json()["accepted_count"] == 1
    assert uploaded.json()["rejected"] == [{"filename": "duplicate.pdf", "code": "duplicate_document"}]
    assert uploaded.json()["accepted"][0]["status"] == "staged"
    assert BatchWorker(server.batch_repository, lambda *_: {}).process_one() is False

    started = client.post(f"/api/v1/batches/{batch_id}/start")
    assert started.status_code == 202
    assert started.json()["queued_count"] == 1

    def fake_processor(_user_id, _payload, filename, progress):
        progress("model_extraction", 50, "Running model")
        return {
            "status": "needs_review",
            "filename": filename,
            "page_count": 1,
            "extraction_method": "synthetic",
            "fields": {
                "merchant": {"value": "Cedar & Finch Kitchen", "confidence": 0.91, "source": None},
                "currency": {"value": "USD", "confidence": 0.95, "source": None},
                "subtotal": {"value": 25.0, "confidence": 0.95, "source": None},
                "tax": {"value": 2.06, "confidence": 0.95, "source": None},
                "tip": {"value": 0.0, "confidence": 0.95, "source": None},
                "total": {"value": 27.06, "confidence": 0.95, "source": {"page": 1, "bbox": None, "text": "Total USD 27.06"}},
            },
            "warnings": [{"code": "manual_check", "message": "Review."}],
        }

    assert BatchWorker(server.batch_repository, fake_processor).process_one() is True
    batch = client.get(f"/api/v1/batches/{batch_id}").json()
    assert batch["review_count"] == 1
    document = batch["documents"][0]
    assert "preview_data_url" not in document["result"]
    assert client.get(f"/api/v1/batch-documents/{document['id']}/source.pdf").content == source
    preview = client.get(f"/api/v1/batch-documents/{document['id']}/preview.png?page=1")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["cache-control"] == "private, no-store"
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert client.get(f"/api/v1/batch-documents/{document['id']}/preview.png?page=2").status_code == 404
    regions = client.get(f"/api/v1/batch-documents/{document['id']}/source-regions")
    assert regions.status_code == 200
    assert regions.json()["fields"]["total"]["page"] == 1
    assert all(0 <= coordinate <= 1 for coordinate in regions.json()["fields"]["total"]["bbox"])

    reviewed = client.patch(
        f"/api/v1/batch-documents/{document['id']}",
        json={"merchant": "Cedar and Finch", "total": 27.06},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "ready"
    assert reviewed.json()["result"]["fields"]["merchant"]["value"] == "Cedar and Finch"

    exported = client.get(f"/api/v1/batches/{batch_id}/export.csv")
    assert exported.status_code == 200
    assert "Cedar and Finch" in exported.content.decode("utf-8-sig")
    items_export = client.get(f"/api/v1/batches/{batch_id}/export-items.csv")
    assert items_export.status_code == 200
    assert "document_number" in items_export.content.decode("utf-8-sig")
    tax_export = client.get(f"/api/v1/batches/{batch_id}/export-tax-prep.xlsx")
    assert tax_export.status_code == 200
    assert tax_export.content.startswith(b"PK")
    assert tax_export.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert tax_export.headers["content-disposition"].endswith('-tax-prep.xlsx"')
    clean_json = client.get(f"/api/v1/batches/{batch_id}/export.json?mode=clean")
    assert clean_json.status_code == 200
    assert clean_json.json()["documents"][0]["fields"]["vendor_name"] == "Cedar and Finch"
    detailed_json = client.get(f"/api/v1/batch-documents/{document['id']}/export.json?mode=detailed")
    assert detailed_json.status_code == 200
    assert detailed_json.json()["schema_version"] == "1.0"
    batches_page = client.get("/batches")
    assert batches_page.status_code == 200
    assert 'id="exportTaxButton"' in batches_page.text
    batch_script = client.get("/batch-workspace.js")
    assert batch_script.status_code == 200
    assert "export-tax-prep.xlsx" in batch_script.text
    assert 'id="selectVisibleDocuments"' in batches_page.text
    assert 'id="deleteSelectedButton"' in batches_page.text
    assert 'data-i18n="backToBatch">Back to batch</button>' in batches_page.text
    assert 'batch-workspace.css?v=10' in batches_page.text
    assert 'batch-workspace.js?v=11' in batches_page.text
    assert 'id="moreExportsMenu"' in batches_page.text
    assert "/documents/delete" in batch_script.text
    assert 'classList.add("is-reviewing")' in batch_script.text
    assert 'classList.remove("is-reviewing")' in batch_script.text


def test_batch_api_deletes_staged_and_waiting_documents_but_not_processing(client):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-plus-delete-one",
        provider_plan_id="P-plus",
        status="ACTIVE",
        plan_code="plus",
    )
    batch_id = client.post("/api/v1/batches", json={"name": "Choose files"}).json()["id"]

    staged = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[("files", ("staged.pdf", create_sample_pdf(), "application/pdf"))],
    ).json()["accepted"][0]
    assert client.delete(f"/api/v1/batch-documents/{staged['id']}").status_code == 204

    queued = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[("files", ("queued.pdf", create_sample_pdf() + b"\n% queued", "application/pdf"))],
    ).json()["accepted"][0]
    assert client.post(f"/api/v1/batches/{batch_id}/start").json()["queued_count"] == 1
    assert client.delete(f"/api/v1/batch-documents/{queued['id']}").status_code == 204

    processing = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[("files", ("processing.pdf", create_sample_pdf() + b"\n% processing", "application/pdf"))],
    ).json()["accepted"][0]
    assert client.post(f"/api/v1/batches/{batch_id}/start").json()["queued_count"] == 1
    assert server.batch_repository.claim_next_document()["id"] == processing["id"]
    conflict = client.delete(f"/api/v1/batch-documents/{processing['id']}")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "document_processing"

    staged_with_processing = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[("files", ("keep.pdf", create_sample_pdf() + b"\n% keep", "application/pdf"))],
    ).json()["accepted"][0]
    bulk_conflict = client.post(
        f"/api/v1/batches/{batch_id}/documents/delete",
        json={"document_ids": [processing["id"], staged_with_processing["id"]]},
    )
    assert bulk_conflict.status_code == 409
    assert bulk_conflict.json()["error"]["code"] == "document_processing"
    remaining_ids = {item["id"] for item in client.get(f"/api/v1/batches/{batch_id}").json()["documents"]}
    assert {processing["id"], staged_with_processing["id"]}.issubset(remaining_ids)


def test_batch_api_bulk_deletes_selected_documents(client):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-plus-delete-selected",
        provider_plan_id="P-plus",
        status="ACTIVE",
        plan_code="plus",
    )
    batch_id = client.post("/api/v1/batches", json={"name": "Bulk selection"}).json()["id"]
    uploaded = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[
            ("files", ("first.pdf", create_sample_pdf() + b"\n% first", "application/pdf")),
            ("files", ("second.pdf", create_sample_pdf() + b"\n% second", "application/pdf")),
        ],
    ).json()["accepted"]

    response = client.post(
        f"/api/v1/batches/{batch_id}/documents/delete",
        json={"document_ids": [document["id"] for document in uploaded]},
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    batch = client.get(f"/api/v1/batches/{batch_id}").json()
    assert batch["document_count"] == 0
    assert batch["documents"] == []


def test_account_deletion_removes_batch_sources_and_results(client):
    user = register(client)
    server.billing_repository.upsert_paypal(
        user_id=user["id"],
        subscription_id="I-plus-delete",
        provider_plan_id="P-plus",
        status="ACTIVE",
        plan_code="plus",
    )
    batch_id = client.post("/api/v1/batches", json={"name": "Delete me"}).json()["id"]
    uploaded = client.post(
        f"/api/v1/batches/{batch_id}/documents",
        files=[("files", ("private.pdf", create_sample_pdf(), "application/pdf"))],
    ).json()
    document_id = uploaded["accepted"][0]["id"]

    deleted = client.request("DELETE", "/api/v1/account", json={"password": TEST_PASSWORD})

    assert deleted.status_code == 200
    assert server.repository.get_user(user["id"]) is None
    assert server.batch_repository.get_batch(user["id"], batch_id) is None
    assert server.batch_repository.get_document(user["id"], document_id) is None


def test_owner_only_operations_console_tracks_events_and_refunds_manually(client, monkeypatch):
    owner_settings = replace(server.settings, admin_email="owner@example.com")
    monkeypatch.setattr(server, "settings", owner_settings)

    assert client.get("/admin", follow_redirects=False).status_code == 303
    assert client.get("/admin/runtime", follow_redirects=False).headers["location"] == "/login?next=/admin/runtime"
    tracked = client.post(
        "/api/events",
        json={
            "event": "page_view",
            "visitor_id": "anonymous-visitor-1",
            "path": "/pdf-receipt-parser",
            "source": "google.com",
            "properties": {"title": "PDF Receipt Parser"},
        },
    )
    assert tracked.status_code == 202

    register(client, "member@example.com")
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/users").status_code == 404
    assert client.get("/api/admin/overview").status_code == 403
    client.post("/api/auth/logout")

    owner = register(client, "owner@example.com")
    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert 'src="/analytics.js' not in admin_page.text
    assert 'id="overviewTrendChart"' in admin_page.text
    assert 'id="runtimeTrendChart"' in admin_page.text
    assert 'id="runtimeHealth"' in admin_page.text
    admin_sections = ("runtime", "users", "billing", "traffic", "diagnostics", "audit")
    for section in admin_sections:
        section_page = client.get(f"/admin/{section}")
        assert section_page.status_code == 200
        assert section_page.headers["x-robots-tag"] == "noindex, nofollow"
        assert f'href="/admin/{section}"' in section_page.text
    assert client.get("/admin/not-a-page").status_code == 404
    overview = client.get("/api/admin/overview").json()
    assert overview["visitors"] == 1
    assert len(overview["daily"]) == 30
    assert overview["daily"][-1]["visitors"] == 1
    assert overview["daily"][-1]["page_views"] == 1
    assert "previous_period" in overview

    server.billing_repository.upsert_paypal(
        user_id=owner["id"],
        subscription_id="I-owner",
        provider_plan_id="P-pro",
        status="ACTIVE",
        payer_email="owner@example.com",
    )
    server.billing_repository.upsert_payment_event(
        "PAYMENT.SALE.COMPLETED",
        {
            "create_time": "2026-08-21T00:00:00Z",
            "resource": {
                "id": "SALE-123",
                "billing_agreement_id": "I-owner",
                "amount": {"total": "9.00", "currency": "USD"},
            },
        },
    )

    rejected = client.post(
        "/api/admin/payments/SALE-123/refund",
        json={
            "amount": "9.00",
            "currency": "USD",
            "reason": "Approved request",
            "confirmation": "wrong",
            "password": TEST_PASSWORD,
        },
    )
    assert rejected.status_code == 422

    wrong_password = client.post(
        "/api/admin/payments/SALE-123/refund",
        json={
            "amount": "9.00",
            "currency": "USD",
            "reason": "Approved request",
            "confirmation": "REFUND",
            "password": "wrong",
        },
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "admin_reauthentication_failed"

    refunded = client.post(
        "/api/admin/payments/SALE-123/refund",
        json={
            "amount": "9.00",
            "currency": "USD",
            "reason": "Approved request",
            "confirmation": "REFUND",
            "password": TEST_PASSWORD,
        },
    )
    assert refunded.status_code == 200
    assert server.paypal_client.refunded == [("SALE-123", "9.00", "USD", "Approved request")]
    assert refunded.json()["payment"]["status"] == "REFUNDED"
    assert client.get("/api/admin/audit").json()["events"][0]["action"] == "payment_refund_requested"
    runtime = client.get("/api/admin/runtime").json()
    assert runtime["contains_receipt_data"] is False
    assert runtime["capacity_assessment"]["database"]["status"] == "sqlite_ok"
    assert runtime["usage_summary"]["timezone"] == "UTC"
    assert len(runtime["usage_summary"]["daily"]) == 30
    assert runtime["usage_summary"]["today"]["processed_images"] >= 0
