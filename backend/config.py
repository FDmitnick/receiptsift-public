from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str | Path | None = None) -> str | None:
    """Read ReceiptSift settings while accepting legacy ClearLedger variables."""
    value = os.getenv(name)
    if value is None and name.startswith("RECEIPTSIFT_"):
        value = os.getenv(name.replace("RECEIPTSIFT_", "CLEARLEDGER_", 1))
    if value is not None:
        return value
    return str(default) if default is not None else None


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = Path(_env("RECEIPTSIFT_DATA_DIR", ROOT_DIR / "data") or ROOT_DIR / "data")
    max_upload_bytes: int = int(_env("RECEIPTSIFT_MAX_UPLOAD_MB", "20") or "20") * 1024 * 1024
    max_pages: int = int(_env("RECEIPTSIFT_MAX_PAGES", "30") or "30")
    session_secret: str = _env("RECEIPTSIFT_SESSION_SECRET", "") or ""
    session_days: int = int(_env("RECEIPTSIFT_SESSION_DAYS", "7") or "7")
    secure_cookies: bool = _env_bool("RECEIPTSIFT_SECURE_COOKIES", True)
    public_host: str = (_env("RECEIPTSIFT_PUBLIC_HOST", "") or "").strip().lower()
    app_host: str = (_env("RECEIPTSIFT_APP_HOST", "") or "").strip().lower()
    app_host_redirect_enabled: bool = _env_bool("RECEIPTSIFT_APP_HOST_REDIRECT_ENABLED", False)
    site_url: str = (_env("RECEIPTSIFT_SITE_URL", "") or "").strip().rstrip("/")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "").strip()
    email_from: str = (_env("RECEIPTSIFT_EMAIL_FROM", "") or "").strip()
    email_verification_hours: int = int(_env("RECEIPTSIFT_EMAIL_VERIFICATION_HOURS", "24") or "24")
    password_reset_minutes: int = int(_env("RECEIPTSIFT_PASSWORD_RESET_MINUTES", "30") or "30")
    admin_email: str = (_env("RECEIPTSIFT_ADMIN_EMAIL", "") or "").strip().casefold()
    owner_only_mode: bool = _env_bool("RECEIPTSIFT_OWNER_ONLY_MODE", True)
    owner_email: str = (
        _env(
            "RECEIPTSIFT_OWNER_EMAIL",
            _env("RECEIPTSIFT_ADMIN_EMAIL", "contact@example.invalid"),
        )
        or ""
    ).strip().casefold()
    owner_plan_code: str = (_env("RECEIPTSIFT_OWNER_PLAN", "free") or "free").strip().casefold()
    analytics_retention_days: int = int(_env("RECEIPTSIFT_ANALYTICS_RETENTION_DAYS", "180") or "180")
    diagnostic_encryption_key: str = (_env("RECEIPTSIFT_DIAGNOSTIC_ENCRYPTION_KEY", "") or "").strip()
    diagnostic_retention_days: int = int(_env("RECEIPTSIFT_DIAGNOSTIC_RETENTION_DAYS", "14") or "14")
    history_retention_days: int = int(_env("RECEIPTSIFT_HISTORY_RETENTION_DAYS", "7") or "7")
    batch_encryption_key: str = (_env("RECEIPTSIFT_BATCH_ENCRYPTION_KEY", "") or "").strip()
    batch_database_url: str = (
        _env("RECEIPTSIFT_BATCH_DATABASE_URL", os.getenv("DATABASE_URL", "")) or ""
    ).strip()
    batch_source_retention_days: int = int(_env("RECEIPTSIFT_BATCH_SOURCE_RETENTION_DAYS", "7") or "7")
    batch_result_retention_days: int = int(_env("RECEIPTSIFT_BATCH_RESULT_RETENTION_DAYS", "7") or "7")
    batch_object_store: str = (_env("RECEIPTSIFT_BATCH_OBJECT_STORE", "local") or "local").strip().lower()
    batch_object_bucket: str = (_env("RECEIPTSIFT_BATCH_OBJECT_BUCKET", "") or "").strip()
    batch_object_endpoint: str = (_env("RECEIPTSIFT_BATCH_OBJECT_ENDPOINT", "") or "").strip()
    batch_object_region: str = (_env("RECEIPTSIFT_BATCH_OBJECT_REGION", "auto") or "auto").strip()
    batch_object_access_key_id: str = (_env("RECEIPTSIFT_BATCH_OBJECT_ACCESS_KEY_ID", "") or "").strip()
    batch_object_secret_access_key: str = (
        _env("RECEIPTSIFT_BATCH_OBJECT_SECRET_ACCESS_KEY", "") or ""
    ).strip()
    batch_object_prefix: str = (_env("RECEIPTSIFT_BATCH_OBJECT_PREFIX", "receipt-sources") or "receipt-sources").strip()
    batch_worker_mode: str = (_env("RECEIPTSIFT_BATCH_WORKER_MODE", "embedded") or "embedded").strip().lower()
    batch_worker_poll_seconds: float = float(_env("RECEIPTSIFT_BATCH_WORKER_POLL_SECONDS", "1") or "1")
    batch_max_files: int = int(_env("RECEIPTSIFT_BATCH_MAX_FILES", "100") or "100")
    parser_provider: str = (_env("RECEIPTSIFT_PARSER_PROVIDER", "local") or "local").strip().lower()
    atlas_api_key: str = (
        _env("RECEIPTSIFT_ATLAS_API_KEY", os.getenv("ATLASCLOUD_API_KEY", "")) or ""
    ).strip()
    atlas_base_url: str = (
        _env("RECEIPTSIFT_ATLAS_BASE_URL", "https://api.atlascloud.ai/v1") or "https://api.atlascloud.ai/v1"
    ).rstrip("/")
    atlas_primary_model: str = (
        _env("RECEIPTSIFT_ATLAS_PRIMARY_MODEL", "qwen/qwen3.5-35b-a3b") or "qwen/qwen3.5-35b-a3b"
    ).strip()
    atlas_text_model: str = (
        _env("RECEIPTSIFT_ATLAS_TEXT_MODEL", "openai/gpt-5.6-luna") or "openai/gpt-5.6-luna"
    ).strip()
    atlas_fallback_model: str = (
        _env("RECEIPTSIFT_ATLAS_FALLBACK_MODEL", "qwen/qwen3-vl-235b-a22b-thinking")
        or "qwen/qwen3-vl-235b-a22b-thinking"
    ).strip()
    atlas_timeout_seconds: float = float(_env("RECEIPTSIFT_ATLAS_TIMEOUT_SECONDS", "90") or "90")
    atlas_min_confidence: float = float(_env("RECEIPTSIFT_ATLAS_MIN_CONFIDENCE", "0.85") or "0.85")
    atlas_render_scale: float = float(_env("RECEIPTSIFT_ATLAS_RENDER_SCALE", "2.0") or "2.0")
    atlas_max_render_dimension: int = int(_env("RECEIPTSIFT_ATLAS_MAX_RENDER_DIMENSION", "3000") or "3000")
    max_pdf_xref_objects: int = int(_env("RECEIPTSIFT_MAX_PDF_XREF_OBJECTS", "50000") or "50000")
    max_pdf_page_dimension: float = float(_env("RECEIPTSIFT_MAX_PDF_PAGE_DIMENSION", "14400") or "14400")
    gpt_verifier_enabled: bool = _env_bool("RECEIPTSIFT_GPT_VERIFIER_ENABLED", True)
    gpt_verifier_model: str = (
        _env("RECEIPTSIFT_GPT_VERIFIER_MODEL", "openai/gpt-5.6-terra") or "openai/gpt-5.6-terra"
    ).strip()
    daily_ai_budget_usd: float = float(_env("RECEIPTSIFT_DAILY_AI_BUDGET_USD", "5.00") or "5.00")
    ai_call_reserve_usd: float = float(_env("RECEIPTSIFT_AI_CALL_RESERVE_USD", "0.25") or "0.25")
    slow_request_ms: int = int(_env("RECEIPTSIFT_SLOW_REQUEST_MS", "2000") or "2000")
    sqlite_contention_threshold: int = int(_env("RECEIPTSIFT_SQLITE_CONTENTION_THRESHOLD", "3") or "3")
    batch_queue_delay_warning_seconds: int = int(
        _env("RECEIPTSIFT_BATCH_QUEUE_DELAY_WARNING_SECONDS", "300") or "300"
    )
    atlas_primary_input_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_PRIMARY_INPUT_USD_PER_MILLION", "0.225") or "0.225"
    )
    atlas_primary_output_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_PRIMARY_OUTPUT_USD_PER_MILLION", "1.80") or "1.80"
    )
    atlas_text_input_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_TEXT_INPUT_USD_PER_MILLION", "1.00") or "1.00"
    )
    atlas_text_output_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_TEXT_OUTPUT_USD_PER_MILLION", "6.00") or "6.00"
    )
    atlas_fallback_input_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_FALLBACK_INPUT_USD_PER_MILLION", "0.50") or "0.50"
    )
    atlas_fallback_output_usd_per_million: float = float(
        _env("RECEIPTSIFT_ATLAS_FALLBACK_OUTPUT_USD_PER_MILLION", "2.50") or "2.50"
    )
    gpt_verifier_input_usd_per_million: float = float(
        _env("RECEIPTSIFT_GPT_VERIFIER_INPUT_USD_PER_MILLION", "2.50") or "2.50"
    )
    gpt_verifier_output_usd_per_million: float = float(
        _env("RECEIPTSIFT_GPT_VERIFIER_OUTPUT_USD_PER_MILLION", "15.00") or "15.00"
    )
    auth_login_limit: int = int(_env("RECEIPTSIFT_AUTH_LOGIN_LIMIT", "10") or "10")
    auth_login_window_seconds: int = int(_env("RECEIPTSIFT_AUTH_LOGIN_WINDOW_SECONDS", "900") or "900")
    auth_registration_limit: int = int(_env("RECEIPTSIFT_AUTH_REGISTRATION_LIMIT", "5") or "5")
    auth_recovery_limit: int = int(_env("RECEIPTSIFT_AUTH_RECOVERY_LIMIT", "5") or "5")
    auth_recovery_window_seconds: int = int(
        _env("RECEIPTSIFT_AUTH_RECOVERY_WINDOW_SECONDS", "3600") or "3600"
    )

    @property
    def atlas_enabled(self) -> bool:
        return self.parser_provider == "atlas" and bool(self.atlas_api_key)

    @property
    def database_path(self) -> Path:
        current = self.data_dir / "receiptsift.sqlite3"
        legacy = self.data_dir / "clearledger.sqlite3"
        return legacy if legacy.exists() and not current.exists() else current

    @property
    def preview_dir(self) -> Path:
        return self.data_dir / "previews"

    @property
    def diagnostic_dir(self) -> Path:
        return self.data_dir / "diagnostics"

    @property
    def batch_object_dir(self) -> Path:
        return self.data_dir / "batch-objects"

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.preview_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
