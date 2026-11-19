from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class DocumentRepository:
    def __init__(self, database_path: Path, preview_dir: Path) -> None:
        self.database_path = database_path
        self.preview_dir = preview_dir
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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    email_verified_at TEXT,
                    session_version INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
            if "email_verified_at" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
                connection.execute("UPDATE users SET email_verified_at = created_at")
            if "session_version" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    extraction_method TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)").fetchall()}
            if "user_id" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN user_id TEXT REFERENCES users(id) ON DELETE CASCADE")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_user_created_at ON documents(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    document_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_usage_user_created_at ON usage_events(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_digest TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    purpose TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_purpose ON auth_tokens(user_id, purpose, created_at DESC)"
            )

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> dict[str, Any]:
        document = json.loads(row["result_json"])
        document.update(
            {
                "id": row["id"],
                "filename": row["filename"],
                "status": row["status"],
                "page_count": row["page_count"],
                "extraction_method": row["extraction_method"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return document

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "email_verified_at": row["email_verified_at"],
            "session_version": row["session_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_user(self, email: str, password_hash: str, claim_legacy_documents: bool = False) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        user_id = uuid.uuid4().hex
        try:
            with self._connect() as connection:
                existing_users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
                connection.execute(
                    """
                    INSERT INTO users
                        (id, email, password_hash, email_verified_at, session_version, created_at, updated_at)
                    VALUES (?, ?, ?, NULL, 0, ?, ?)
                    """,
                    (user_id, email, password_hash, now, now),
                )
                if claim_legacy_documents and existing_users == 0:
                    connection.execute("UPDATE documents SET user_id = ? WHERE user_id IS NULL", (user_id,))
        except sqlite3.IntegrityError as error:
            raise ValueError("email_exists") from error
        return self.get_user(user_id)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        return self._row_to_user(row) if row else None

    def create_auth_token(
        self,
        user_id: str,
        purpose: str,
        token_digest: str,
        expires_at: datetime,
        cooldown_seconds: int = 60,
    ) -> bool:
        now = datetime.now(UTC)
        with self._connect() as connection:
            latest = connection.execute(
                "SELECT created_at FROM auth_tokens WHERE user_id = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1",
                (user_id, purpose),
            ).fetchone()
            if latest and datetime.fromisoformat(latest["created_at"]) > now - timedelta(seconds=cooldown_seconds):
                return False
            connection.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND purpose = ? AND used_at IS NULL",
                (now.isoformat(), user_id, purpose),
            )
            connection.execute(
                """
                INSERT INTO auth_tokens (token_digest, user_id, purpose, created_at, expires_at, used_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (token_digest, user_id, purpose, now.isoformat(), expires_at.isoformat()),
            )
        return True

    def verify_email_token(self, token_digest: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            token = connection.execute(
                """
                SELECT user_id FROM auth_tokens
                WHERE token_digest = ? AND purpose = 'verify_email' AND used_at IS NULL AND expires_at > ?
                """,
                (token_digest, now),
            ).fetchone()
            if token is None:
                return None
            connection.execute(
                "UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?), updated_at = ? WHERE id = ?",
                (now, now, token["user_id"]),
            )
            connection.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND purpose = 'verify_email' AND used_at IS NULL",
                (now, token["user_id"]),
            )
        return self.get_user(token["user_id"])

    def reset_password_with_token(self, token_digest: str, password_hash: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            token = connection.execute(
                """
                SELECT user_id FROM auth_tokens
                WHERE token_digest = ? AND purpose = 'reset_password' AND used_at IS NULL AND expires_at > ?
                """,
                (token_digest, now),
            ).fetchone()
            if token is None:
                return None
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, email_verified_at = COALESCE(email_verified_at, ?),
                    session_version = session_version + 1, updated_at = ?
                WHERE id = ?
                """,
                (password_hash, now, now, token["user_id"]),
            )
            connection.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
                (now, token["user_id"]),
            )
        return self.get_user(token["user_id"])

    def create(self, user_id: str, document_id: str, filename: str, sha256: str, result: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents
                    (id, user_id, filename, sha256, status, page_count, extraction_method, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    user_id,
                    filename,
                    sha256,
                    result["status"],
                    result["page_count"],
                    result["extraction_method"],
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                ),
            )
        self.record_usage(user_id, "document_parsed", result["page_count"], document_id)
        return self.get(user_id, document_id)  # type: ignore[return-value]

    def get(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            ).fetchone()
        return self._row_to_document(row) if row else None

    def list(self, user_id: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def update_result(self, user_id: str, document_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE documents SET status = ?, result_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (result["status"], json.dumps(result, ensure_ascii=False, separators=(",", ":")), now, document_id, user_id),
            )
        return self.get(user_id, document_id) if cursor.rowcount else None

    def delete(self, user_id: str, document_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        if cursor.rowcount:
            preview = self.preview_dir / f"{document_id}.png"
            preview.unlink(missing_ok=True)
        return bool(cursor.rowcount)

    def record_usage(self, user_id: str, event_type: str, quantity: int = 1, document_id: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO usage_events (user_id, event_type, quantity, document_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, event_type, quantity, document_id, datetime.now(UTC).isoformat()),
            )

    def usage(self, user_id: str) -> dict[str, Any]:
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._connect() as connection:
            monthly = connection.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN event_type = 'document_parsed' THEN 1 ELSE 0 END), 0) AS documents,
                    COALESCE(SUM(CASE WHEN event_type = 'document_parsed' THEN quantity ELSE 0 END), 0) AS pages,
                    COALESCE(SUM(CASE WHEN event_type = 'csv_exported' THEN 1 ELSE 0 END), 0) AS exports
                FROM usage_events WHERE user_id = ? AND created_at >= ?
                """,
                (user_id, month_start),
            ).fetchone()
        return {
            "month": month_start[:7],
            "documents_parsed": monthly["documents"],
            "pages_processed": monthly["pages"],
            "csv_exports": monthly["exports"],
            "saved_documents": 0,
            "saved_pages": 0,
            "document_storage_enabled": False,
        }

    def export_user_data(self, user_id: str) -> dict[str, Any] | None:
        user = self.get_user(user_id)
        if user is None:
            return None
        public_user = {
            key: value for key, value in user.items() if key not in {"password_hash", "session_version"}
        }
        return {
            "exported_at": datetime.now(UTC).isoformat(),
            "account": public_user,
            "usage": self.usage(user_id),
        }

    def delete_user(self, user_id: str) -> bool:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM documents WHERE user_id = ?", (user_id,)).fetchall()
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if cursor.rowcount:
            for row in rows:
                (self.preview_dir / f"{row['id']}.png").unlink(missing_ok=True)
        return bool(cursor.rowcount)

    def purge_older_than(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            rows = connection.execute("SELECT id, user_id FROM documents WHERE created_at < ?", (cutoff,)).fetchall()
        for row in rows:
            if row["user_id"]:
                self.delete(row["user_id"], row["id"])
            else:
                with self._connect() as connection:
                    connection.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
                (self.preview_dir / f"{row['id']}.png").unlink(missing_ok=True)
        return len(rows)

    def purge_all_documents(self) -> int:
        """Remove legacy receipt results and previews while preserving accounts and aggregate usage."""
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM documents").fetchall()
            connection.execute("DELETE FROM documents")
        if self.preview_dir.is_dir():
            for preview in self.preview_dir.iterdir():
                if preview.is_file() and preview.suffix.casefold() == ".png":
                    preview.unlink(missing_ok=True)
        return len(rows)
