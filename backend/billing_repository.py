from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class BillingRepository:
    """PayPal state kept separate from account and document persistence."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_subscriptions (
                    user_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_subscription_id TEXT NOT NULL UNIQUE,
                    provider_plan_id TEXT NOT NULL,
                    plan_code TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payer_email TEXT,
                    current_period_end TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_subscription_external "
                "ON billing_subscriptions(provider, provider_subscription_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_webhook_events (
                    provider_event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_quota_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    period TEXT NOT NULL,
                    pages INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            reservation_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(billing_quota_reservations)").fetchall()
            }
            if "pages" not in reservation_columns:
                connection.execute("ALTER TABLE billing_quota_reservations ADD COLUMN pages INTEGER NOT NULL DEFAULT 1")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_quota_user_period "
                "ON billing_quota_reservations(user_id, period, expires_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_payments (
                    provider_payment_id TEXT PRIMARY KEY,
                    provider_subscription_id TEXT NOT NULL,
                    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    status TEXT NOT NULL,
                    amount_value TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    payer_email TEXT,
                    paid_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_payments_paid ON billing_payments(paid_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_payments_user ON billing_payments(user_id, paid_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_refunds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_refund_id TEXT NOT NULL UNIQUE,
                    provider_payment_id TEXT NOT NULL REFERENCES billing_payments(provider_payment_id),
                    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    amount_value TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_refunds_payment ON billing_refunds(provider_payment_id, created_at DESC)"
            )

    @staticmethod
    def _subscription(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def get_for_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM billing_subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return self._subscription(row) if row else None

    def get_by_provider_id(self, subscription_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM billing_subscriptions WHERE provider = 'paypal' AND provider_subscription_id = ?",
                (subscription_id,),
            ).fetchone()
        return self._subscription(row) if row else None

    def upsert_paypal(
        self,
        *,
        user_id: str,
        subscription_id: str,
        provider_plan_id: str,
        status: str,
        plan_code: str = "pro",
        payer_email: str | None = None,
        current_period_end: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO billing_subscriptions (
                    user_id, provider, provider_subscription_id, provider_plan_id, plan_code,
                    status, payer_email, current_period_end, created_at, updated_at
                ) VALUES (?, 'paypal', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    provider = excluded.provider,
                    provider_subscription_id = excluded.provider_subscription_id,
                    provider_plan_id = excluded.provider_plan_id,
                    plan_code = excluded.plan_code,
                    status = excluded.status,
                    payer_email = excluded.payer_email,
                    current_period_end = excluded.current_period_end,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    subscription_id,
                    provider_plan_id,
                    plan_code,
                    status,
                    payer_email,
                    current_period_end,
                    now,
                    now,
                ),
            )
        return self.get_for_user(user_id)  # type: ignore[return-value]

    def claim_webhook_event(self, event_id: str, event_type: str) -> bool:
        if not event_id:
            return False
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO billing_webhook_events (provider_event_id, event_type, received_at) VALUES (?, ?, ?)",
                    (event_id, event_type, datetime.now(UTC).isoformat()),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def has_webhook_event(self, event_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM billing_webhook_events WHERE provider_event_id = ?",
                (event_id,),
            ).fetchone()
        return row is not None

    def delete_for_user(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM billing_subscriptions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM billing_quota_reservations WHERE user_id = ?", (user_id,))

    def update_status(self, user_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE billing_subscriptions SET status = ?, updated_at = ? WHERE user_id = ?",
                (status, datetime.now(UTC).isoformat(), user_id),
            )

    def upsert_payment_event(self, event_type: str, event: dict[str, Any]) -> dict[str, Any] | None:
        resource = event.get("resource") or {}
        payment_id = str(resource.get("id", ""))
        subscription_id = str(resource.get("billing_agreement_id", ""))
        if not payment_id or not subscription_id:
            return None
        subscription = self.get_by_provider_id(subscription_id)
        amount = resource.get("amount") or {}
        amount_value = str(amount.get("total") or amount.get("value") or "0.00")
        currency = str(amount.get("currency") or amount.get("currency_code") or "USD").upper()
        status = {
            "PAYMENT.SALE.COMPLETED": "COMPLETED",
            "PAYMENT.SALE.DENIED": "DENIED",
            "PAYMENT.SALE.REFUNDED": "REFUNDED",
            "PAYMENT.SALE.REVERSED": "REVERSED",
        }.get(event_type, str(resource.get("state") or resource.get("status") or "UNKNOWN").upper())
        now = datetime.now(UTC).isoformat()
        paid_at = str(resource.get("create_time") or event.get("create_time") or now)
        user_id = subscription.get("user_id") if subscription else None
        payer_email = subscription.get("payer_email") if subscription else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO billing_payments (
                    provider_payment_id, provider_subscription_id, user_id, status,
                    amount_value, currency, payer_email, paid_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_payment_id) DO UPDATE SET
                    provider_subscription_id = excluded.provider_subscription_id,
                    user_id = COALESCE(excluded.user_id, billing_payments.user_id),
                    status = excluded.status,
                    amount_value = CASE
                        WHEN excluded.amount_value = '0.00' THEN billing_payments.amount_value
                        ELSE excluded.amount_value
                    END,
                    currency = excluded.currency,
                    payer_email = COALESCE(excluded.payer_email, billing_payments.payer_email),
                    updated_at = excluded.updated_at
                """,
                (payment_id, subscription_id, user_id, status, amount_value, currency, payer_email, paid_at, now),
            )
        return self.get_payment(payment_id)

    def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT p.*, u.email AS account_email, s.status AS subscription_status,
                    COALESCE((SELECT SUM(CAST(r.amount_value AS REAL)) FROM billing_refunds r
                        WHERE r.provider_payment_id = p.provider_payment_id
                        AND r.status IN ('COMPLETED', 'PENDING')), 0) AS refunded_amount
                FROM billing_payments p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN billing_subscriptions s ON s.provider_subscription_id = p.provider_subscription_id
                WHERE p.provider_payment_id = ?
                """,
                (payment_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_payments(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.*, u.email AS account_email, s.status AS subscription_status,
                    COALESCE((SELECT SUM(CAST(r.amount_value AS REAL)) FROM billing_refunds r
                        WHERE r.provider_payment_id = p.provider_payment_id
                        AND r.status IN ('COMPLETED', 'PENDING')), 0) AS refunded_amount,
                    (SELECT MAX(r.status) FROM billing_refunds r
                        WHERE r.provider_payment_id = p.provider_payment_id) AS refund_status
                FROM billing_payments p
                LEFT JOIN users u ON u.id = p.user_id
                LEFT JOIN billing_subscriptions s ON s.provider_subscription_id = p.provider_subscription_id
                ORDER BY p.paid_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_refund(
        self,
        *,
        provider_refund_id: str,
        provider_payment_id: str,
        amount_value: str,
        currency: str,
        status: str,
        reason: str,
        requested_by: str,
    ) -> dict[str, Any]:
        payment = self.get_payment(provider_payment_id)
        if payment is None:
            raise ValueError("payment_not_found")
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO billing_refunds (
                    provider_refund_id, provider_payment_id, user_id, amount_value, currency,
                    status, reason, requested_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider_refund_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    provider_refund_id,
                    provider_payment_id,
                    payment.get("user_id"),
                    amount_value,
                    currency,
                    status,
                    reason[:180],
                    requested_by[:254],
                    now,
                    now,
                ),
            )
            totals = connection.execute(
                """
                SELECT COALESCE(SUM(CAST(amount_value AS REAL)), 0) AS refunded
                FROM billing_refunds
                WHERE provider_payment_id = ? AND status IN ('COMPLETED', 'PENDING')
                """,
                (provider_payment_id,),
            ).fetchone()
            refunded = float(totals["refunded"])
            original = float(payment["amount_value"])
            payment_status = "REFUNDED" if refunded >= original else "PARTIALLY_REFUNDED"
            if status == "PENDING":
                payment_status = "REFUND_PENDING"
            connection.execute(
                "UPDATE billing_payments SET status = ?, updated_at = ? WHERE provider_payment_id = ?",
                (payment_status, now, provider_payment_id),
            )
            row = connection.execute(
                "SELECT * FROM billing_refunds WHERE provider_refund_id = ?",
                (provider_refund_id,),
            ).fetchone()
        return dict(row)

    def reserve_document(
        self,
        user_id: str,
        monthly_document_limit: int,
        reservation_id: str,
        *,
        requested_pages: int = 1,
        monthly_page_limit: int | None = None,
        max_pages_per_document: int = 30,
    ) -> bool:
        """Atomically reserve one parse slot so concurrent uploads cannot exceed the limit."""
        if requested_pages < 1 or requested_pages > max_pages_per_document:
            return False
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        expires_at = now + timedelta(minutes=30)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT 1 FROM billing_quota_reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            if existing:
                return True
            usage_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'usage_events'",
            ).fetchone()
            documents_used = 0
            pages_used = 0
            if usage_table:
                usage = connection.execute(
                    """
                    SELECT COUNT(*) AS documents, COALESCE(SUM(quantity), 0) AS pages
                    FROM usage_events
                    WHERE user_id = ? AND event_type = 'document_parsed' AND created_at >= ?
                    """,
                    (user_id, month_start.isoformat()),
                ).fetchone()
                documents_used = int(usage["documents"])
                pages_used = int(usage["pages"])
            reserved = connection.execute(
                """
                SELECT COUNT(*) AS documents, COALESCE(SUM(pages), 0) AS pages
                FROM billing_quota_reservations
                WHERE user_id = ? AND period = ? AND expires_at > ?
                """,
                (user_id, month_start.strftime("%Y-%m"), now.isoformat()),
            ).fetchone()
            documents_reserved = int(reserved["documents"])
            pages_reserved = int(reserved["pages"])
            if documents_used + documents_reserved >= monthly_document_limit:
                return False
            if monthly_page_limit is not None and pages_used + pages_reserved + requested_pages > monthly_page_limit:
                return False
            connection.execute(
                """
                INSERT INTO billing_quota_reservations (reservation_id, user_id, period, pages, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reservation_id,
                    user_id,
                    month_start.strftime("%Y-%m"),
                    requested_pages,
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
        return True

    def release_document_reservation(self, reservation_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM billing_quota_reservations WHERE reservation_id = ?",
                (reservation_id,),
            )
