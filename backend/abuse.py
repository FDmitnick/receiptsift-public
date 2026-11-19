from __future__ import annotations

import hashlib
import hmac
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


def protected_subject(secret: str, namespace: str, value: str) -> str:
    """Create a stable pseudonymous key without storing raw email, provider ID, or IP."""
    if len(secret) < 32:
        raise RuntimeError("ABUSE_HASH_SECRET must contain at least 32 characters.")
    normalized = f"{namespace.strip().lower()}:{value.strip().casefold()}".encode()
    return hmac.new(secret.encode(), normalized, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class AbuseDecision:
    allowed: bool
    challenge_required: bool
    retry_after_seconds: int
    reason: str | None = None


class AbuseRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS abuse_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_abuse_subject_action_time "
                "ON abuse_events(subject_hash, action, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS free_identity_claims (
                    identity_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )

    def check_and_record(
        self,
        *,
        subject_hash: str,
        action: str,
        limit: int,
        window_seconds: int,
        challenge_after: int | None = None,
    ) -> AbuseDecision:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=window_seconds)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recent = connection.execute(
                """
                SELECT created_at FROM abuse_events
                WHERE subject_hash = ? AND action = ? AND created_at >= ?
                ORDER BY created_at ASC
                """,
                (subject_hash, action, window_start.isoformat()),
            ).fetchall()
            count = len(recent)
            if count >= limit:
                oldest = datetime.fromisoformat(recent[0]["created_at"])
                retry_after = max(int((oldest + timedelta(seconds=window_seconds) - now).total_seconds()), 1)
                return AbuseDecision(False, True, retry_after, "rate_limit_reached")
            connection.execute(
                "INSERT INTO abuse_events (subject_hash, action, created_at) VALUES (?, ?, ?)",
                (subject_hash, action, now.isoformat()),
            )
        needs_challenge = challenge_after is not None and count + 1 >= challenge_after
        return AbuseDecision(True, needs_challenge, 0, "challenge_required" if needs_challenge else None)

    def claim_free_identity(self, identity_hash: str, user_id: str, cooldown_days: int = 31) -> bool:
        """Prevent deleting and immediately recreating an account to reset Free usage."""
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            claim = connection.execute(
                "SELECT * FROM free_identity_claims WHERE identity_hash = ?",
                (identity_hash,),
            ).fetchone()
            if claim is None:
                connection.execute(
                    """
                    INSERT INTO free_identity_claims (identity_hash, user_id, claimed_at, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (identity_hash, user_id, now.isoformat(), now.isoformat()),
                )
                return True
            if claim["user_id"] == user_id:
                connection.execute(
                    "UPDATE free_identity_claims SET last_seen_at = ? WHERE identity_hash = ?",
                    (now.isoformat(), identity_hash),
                )
                return True
            last_seen = datetime.fromisoformat(claim["last_seen_at"])
            if last_seen > now - timedelta(days=cooldown_days):
                return False
            connection.execute(
                """
                UPDATE free_identity_claims
                SET user_id = ?, claimed_at = ?, last_seen_at = ?
                WHERE identity_hash = ?
                """,
                (user_id, now.isoformat(), now.isoformat(), identity_hash),
            )
        return True

    def purge(self, retention_days: int = 35) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()
        with self._connect() as connection:
            events = connection.execute("DELETE FROM abuse_events WHERE created_at < ?", (cutoff,))
            claims = connection.execute("DELETE FROM free_identity_claims WHERE last_seen_at < ?", (cutoff,))
        return events.rowcount + claims.rowcount
