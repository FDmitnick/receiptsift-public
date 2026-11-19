from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

PUBLIC_ANALYTICS_EVENTS = {
    "page_view",
    "cta_click",
    "pricing_view",
    "registration_started",
    "login_started",
}


class AnalyticsEventRequest(BaseModel):
    event: str = Field(min_length=2, max_length=48)
    visitor_id: str | None = Field(default=None, max_length=64)
    path: str = Field(default="/", min_length=1, max_length=300)
    source: str | None = Field(default=None, max_length=300)
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AdminRefundRequest(BaseModel):
    amount: str = Field(min_length=1, max_length=20)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    reason: str = Field(min_length=3, max_length=180)
    confirmation: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class AdminCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=128)
    confirmation: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class OperationsRepository:
    """Privacy-minimized product analytics and owner action history."""

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
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    visitor_id TEXT,
                    path TEXT NOT NULL,
                    source TEXT,
                    properties_json TEXT NOT NULL DEFAULT '{}',
                    occurred_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_occurred ON analytics_events(occurred_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_type_occurred ON analytics_events(event_type, occurred_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_user_occurred ON analytics_events(user_id, occurred_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    admin_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_events(created_at DESC)"
            )

    @staticmethod
    def _properties(value: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
        clean: dict[str, str | int | float | bool | None] = {}
        for key, item in list(value.items())[:12]:
            safe_key = str(key)[:48]
            if isinstance(item, str):
                clean[safe_key] = item[:240]
            elif item is None or isinstance(item, (int, float, bool)):
                clean[safe_key] = item
        return clean

    def record_event(
        self,
        event_type: str,
        *,
        user_id: str | None = None,
        visitor_id: str | None = None,
        path: str = "/",
        source: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analytics_events
                    (event_type, user_id, visitor_id, path, source, properties_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type[:48],
                    user_id,
                    visitor_id[:64] if visitor_id else None,
                    path[:300],
                    source[:300] if source else None,
                    json.dumps(self._properties(properties or {}), separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def record_audit(
        self,
        *,
        admin_user_id: str,
        admin_email: str,
        action: str,
        target_type: str,
        target_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_audit_events
                    (admin_user_id, admin_email, action, target_type, target_id, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    admin_user_id,
                    admin_email[:254],
                    action[:64],
                    target_type[:48],
                    target_id[:128],
                    json.dumps(self._properties(details or {}), separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def overview(self, days: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        current_start = datetime.combine(now.date() - timedelta(days=days - 1), datetime.min.time(), tzinfo=UTC)
        previous_start = current_start - timedelta(days=days)
        since = current_start.isoformat()
        previous_since = previous_start.isoformat()
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM users) AS total_users,
                    (SELECT COUNT(*) FROM users WHERE created_at >= ?) AS registrations,
                    (SELECT COUNT(*) FROM analytics_events WHERE event_type = 'page_view' AND occurred_at >= ?) AS page_views,
                    (SELECT COUNT(DISTINCT visitor_id) FROM analytics_events
                        WHERE event_type = 'page_view' AND occurred_at >= ? AND visitor_id IS NOT NULL) AS visitors,
                    (SELECT COUNT(*) FROM analytics_events WHERE event_type = 'cta_click' AND occurred_at >= ?) AS cta_clicks,
                    (SELECT COUNT(*) FROM usage_events WHERE event_type = 'document_parsed' AND created_at >= ?) AS documents_parsed,
                    (SELECT COUNT(DISTINCT user_id) FROM usage_events
                        WHERE event_type = 'document_parsed' AND created_at >= ?) AS users_parsed,
                    (SELECT COUNT(*) FROM usage_events WHERE event_type = 'csv_exported' AND created_at >= ?) AS csv_exports,
                    (SELECT COUNT(*) FROM billing_subscriptions WHERE status = 'ACTIVE') AS active_subscribers,
                    (SELECT COUNT(DISTINCT user_id) FROM (
                        SELECT user_id FROM usage_events WHERE created_at >= ?
                        UNION SELECT user_id FROM analytics_events WHERE occurred_at >= ? AND user_id IS NOT NULL
                    )) AS active_users
                """,
                (since, since, since, since, since, since, since, since, since),
            ).fetchone()
            money = connection.execute(
                """
                SELECT
                    COALESCE((SELECT SUM(CAST(amount_value AS REAL)) FROM billing_payments
                        WHERE status NOT IN ('DENIED', 'PENDING') AND paid_at >= ?), 0) AS gross_revenue,
                    COALESCE((SELECT SUM(CAST(amount_value AS REAL)) FROM billing_refunds
                        WHERE status IN ('COMPLETED', 'PENDING') AND created_at >= ?), 0) AS refunds
                """,
                (since, since),
            ).fetchone()
            previous = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM users WHERE created_at >= ? AND created_at < ?) AS registrations,
                    (SELECT COUNT(*) FROM analytics_events
                        WHERE event_type = 'page_view' AND occurred_at >= ? AND occurred_at < ?) AS page_views,
                    (SELECT COUNT(DISTINCT visitor_id) FROM analytics_events
                        WHERE event_type = 'page_view' AND occurred_at >= ? AND occurred_at < ?
                        AND visitor_id IS NOT NULL) AS visitors,
                    (SELECT COUNT(*) FROM usage_events
                        WHERE event_type = 'document_parsed' AND created_at >= ? AND created_at < ?) AS documents_parsed,
                    (SELECT COUNT(DISTINCT user_id) FROM usage_events
                        WHERE event_type = 'document_parsed' AND created_at >= ? AND created_at < ?) AS users_parsed,
                    (SELECT COUNT(*) FROM usage_events
                        WHERE event_type = 'csv_exported' AND created_at >= ? AND created_at < ?) AS csv_exports,
                    (SELECT COUNT(DISTINCT user_id) FROM (
                        SELECT user_id FROM usage_events WHERE created_at >= ? AND created_at < ?
                        UNION SELECT user_id FROM analytics_events
                            WHERE occurred_at >= ? AND occurred_at < ? AND user_id IS NOT NULL
                    )) AS active_users
                """,
                (
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                    previous_since,
                    since,
                ),
            ).fetchone()
            previous_money = connection.execute(
                """
                SELECT
                    COALESCE((SELECT SUM(CAST(amount_value AS REAL)) FROM billing_payments
                        WHERE status NOT IN ('DENIED', 'PENDING') AND paid_at >= ? AND paid_at < ?), 0) AS gross_revenue,
                    COALESCE((SELECT SUM(CAST(amount_value AS REAL)) FROM billing_refunds
                        WHERE status IN ('COMPLETED', 'PENDING') AND created_at >= ? AND created_at < ?), 0) AS refunds
                """,
                (previous_since, since, previous_since, since),
            ).fetchone()
            daily_rows = connection.execute(
                """
                WITH dates AS (
                    SELECT date(?) AS day
                    UNION
                    SELECT date(created_at) FROM users WHERE created_at >= ?
                    UNION
                    SELECT date(occurred_at) FROM analytics_events WHERE occurred_at >= ?
                    UNION
                    SELECT date(created_at) FROM usage_events WHERE created_at >= ?
                )
                SELECT
                    dates.day AS date,
                    (SELECT COUNT(*) FROM users u WHERE date(u.created_at) = dates.day) AS registrations,
                    (SELECT COUNT(*) FROM analytics_events a
                        WHERE a.event_type = 'page_view' AND date(a.occurred_at) = dates.day) AS page_views,
                    (SELECT COUNT(DISTINCT a.visitor_id) FROM analytics_events a
                        WHERE a.event_type = 'page_view' AND date(a.occurred_at) = dates.day
                        AND a.visitor_id IS NOT NULL) AS visitors,
                    (SELECT COUNT(*) FROM usage_events e
                        WHERE e.event_type = 'document_parsed' AND date(e.created_at) = dates.day) AS documents_parsed,
                    (SELECT COUNT(*) FROM usage_events e
                        WHERE e.event_type = 'csv_exported' AND date(e.created_at) = dates.day) AS csv_exports
                FROM dates
                WHERE dates.day >= date(?)
                ORDER BY dates.day
                """,
                (now.isoformat(), since, since, since, since),
            ).fetchall()
        daily_by_date = {str(row["date"]): dict(row) for row in daily_rows if row["date"]}
        daily = []
        for offset in range(days):
            day = (current_start.date() + timedelta(days=offset)).isoformat()
            daily.append(
                daily_by_date.get(day)
                or {
                    "date": day,
                    "registrations": 0,
                    "page_views": 0,
                    "visitors": 0,
                    "documents_parsed": 0,
                    "csv_exports": 0,
                }
            )
        result = dict(totals)
        previous_result = dict(previous)
        previous_result.update(
            {
                "gross_revenue": round(float(previous_money["gross_revenue"]), 2),
                "refunds": round(float(previous_money["refunds"]), 2),
                "net_revenue": round(
                    float(previous_money["gross_revenue"]) - float(previous_money["refunds"]),
                    2,
                ),
            }
        )
        result.update(
            {
                "days": days,
                "gross_revenue": round(float(money["gross_revenue"]), 2),
                "refunds": round(float(money["refunds"]), 2),
                "net_revenue": round(float(money["gross_revenue"]) - float(money["refunds"]), 2),
                "currency": "USD",
                "daily": daily,
                "previous_period": previous_result,
            }
        )
        return result

    def list_users(self, limit: int = 200, search: str = "") -> list[dict[str, Any]]:
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        search_value = f"%{search.strip()}%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    u.id, u.email, u.email_verified_at, u.created_at,
                    COALESCE(s.plan_code, 'free') AS plan_code,
                    COALESCE(s.status, 'FREE') AS subscription_status,
                    s.provider_subscription_id, s.current_period_end,
                    (SELECT COUNT(*) FROM usage_events e WHERE e.user_id = u.id
                        AND e.event_type = 'document_parsed' AND e.created_at >= ?) AS documents_this_month,
                    (SELECT COALESCE(SUM(quantity), 0) FROM usage_events e WHERE e.user_id = u.id
                        AND e.event_type = 'document_parsed' AND e.created_at >= ?) AS pages_this_month,
                    (SELECT COUNT(*) FROM usage_events e WHERE e.user_id = u.id
                        AND e.event_type = 'csv_exported' AND e.created_at >= ?) AS exports_this_month,
                    0 AS saved_documents,
                    MAX(
                        COALESCE((SELECT MAX(created_at) FROM usage_events e WHERE e.user_id = u.id), ''),
                        COALESCE((SELECT MAX(occurred_at) FROM analytics_events a WHERE a.user_id = u.id), ''),
                        u.created_at
                    ) AS last_active_at
                FROM users u
                LEFT JOIN billing_subscriptions s ON s.user_id = u.id
                WHERE (? = '%%' OR u.email LIKE ? COLLATE NOCASE)
                ORDER BY u.created_at DESC
                LIMIT ?
                """,
                (month_start, month_start, month_start, search_value, search_value, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_events(self, limit: int = 200, event_type: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id, a.event_type, a.visitor_id, a.path, a.source, a.properties_json,
                       a.occurred_at, u.email
                FROM analytics_events a
                LEFT JOIN users u ON u.id = a.user_id
                WHERE (? = '' OR a.event_type = ?)
                ORDER BY a.occurred_at DESC
                LIMIT ?
                """,
                (event_type, event_type, limit),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["properties"] = json.loads(item.pop("properties_json") or "{}")
            result.append(item)
        return result

    def list_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_audit_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json") or "{}")
            result.append(item)
        return result

    def purge_analytics(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM analytics_events WHERE occurred_at < ?", (cutoff,))
        return cursor.rowcount
