from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - production requirements install this dependency
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]


_TRANSPORT_KEYS = {
    "id",
    "order_id",
    "filename",
    "created_at",
    "updated_at",
    "preview_url",
    "preview_data_url",
    "storage_mode",
    "history_expires_at",
    "ledger_entry_id",
}


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Remove response-only values before producing a stable extraction digest."""
    return _normalize_json_value({key: value for key, value in result.items() if key not in _TRANSPORT_KEYS})


def result_digest(result: dict[str, Any]) -> str:
    payload = json.dumps(
        canonical_result_payload(result),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


class DiagnosticRepository:
    def __init__(
        self,
        database_path: Path,
        evidence_dir: Path,
        encryption_key: str,
        retention_days: int = 14,
        history_retention_days: int = 7,
    ) -> None:
        self.database_path = database_path
        self.evidence_dir = evidence_dir
        self.retention_days = max(1, retention_days)
        self.history_retention_days = max(1, history_retention_days)
        self.history_dir = evidence_dir.parent / "recent-history"
        self.ledger_dir = evidence_dir.parent / "ledger"
        self._cipher = self._build_cipher(encryption_key)
        self._initialize()

    @staticmethod
    def _build_cipher(encryption_key: str):
        if not encryption_key or Fernet is None:
            return None
        try:
            return Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            return None

    @property
    def configured(self) -> bool:
        return self._cipher is not None

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
                CREATE TABLE IF NOT EXISTS parse_orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    parser_version TEXT NOT NULL,
                    extraction_method TEXT,
                    input_sha256 TEXT NOT NULL,
                    output_sha256 TEXT,
                    duration_ms INTEGER,
                    overall_confidence REAL,
                    warning_count INTEGER,
                    error_code TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_parse_orders_user_created ON parse_orders(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnostic_cases (
                    case_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE REFERENCES parse_orders(order_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    has_source_pdf INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    deleted_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_diagnostic_cases_user_created ON diagnostic_cases(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS recent_documents (
                    order_id TEXT PRIMARY KEY REFERENCES parse_orders(order_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    ledger_entry_id TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_recent_documents_user_created ON recent_documents(user_id, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    entry_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, source_type, source_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ledger_entries_user_created ON ledger_entries(user_id, created_at DESC)"
            )

    def _encrypt_json_file(self, path: Path, payload: dict[str, Any]) -> None:
        if self._cipher is None:
            raise RuntimeError("history_encryption_unavailable")
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(self._cipher.encrypt(encoded))
        temporary.replace(path)

    def _decrypt_json_file(self, path: Path) -> dict[str, Any]:
        return json.loads(self._decrypt_file(path))

    @staticmethod
    def _history_summary(result: dict[str, Any]) -> dict[str, Any]:
        fields = result.get("fields") if isinstance(result.get("fields"), dict) else {}

        def value(*names: str) -> Any:
            for name in names:
                field = fields.get(name)
                if isinstance(field, dict) and field.get("value") is not None:
                    return field.get("value")
            return None

        return {
            "id": result.get("id") or result.get("order_id"),
            "order_id": result.get("order_id") or result.get("id"),
            "filename": result.get("filename") or "document.pdf",
            "document_type": result.get("document_type") or "receipt",
            "status": result.get("status") or "completed",
            "page_count": int(result.get("page_count") or 0),
            "merchant": value("merchant", "vendor_name"),
            "date": value("date", "issue_date"),
            "currency": value("currency"),
            "total": value("total", "balance_due", "gross_amount"),
            "created_at": result.get("created_at"),
            "updated_at": result.get("updated_at"),
        }

    @staticmethod
    def _ledger_payload(result: dict[str, Any], source_type: str, source_id: str) -> dict[str, Any]:
        return {
            "source_type": source_type,
            "source_id": source_id,
            "document_type": result.get("document_type") or "receipt",
            "document_subtype": result.get("document_subtype"),
            "filename": result.get("filename") or "document.pdf",
            "fields": result.get("fields") if isinstance(result.get("fields"), dict) else {},
            "items": result.get("items") if isinstance(result.get("items"), list) else [],
            "reconciliation": result.get("reconciliation"),
            "reconciliations": result.get("reconciliations") if isinstance(result.get("reconciliations"), list) else [],
            "warnings": result.get("warnings") if isinstance(result.get("warnings"), list) else [],
            "status": result.get("status") or "completed",
            "parser_version": result.get("parser_version"),
            "extraction_method": result.get("extraction_method"),
            "reviewed_at": result.get("reviewed_at"),
        }

    def save_recent_document(
        self,
        user_id: str,
        order_id: str,
        source_pdf: bytes,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        if self._cipher is None:
            raise RuntimeError("history_encryption_unavailable")
        created = datetime.now(UTC)
        expires = created + timedelta(days=self.history_retention_days)
        result = dict(result)
        result["storage_mode"] = "recent_7d"
        result["history_expires_at"] = expires.isoformat()
        document_dir = self.history_dir / order_id
        try:
            self._encrypt_json_file(document_dir / "result.json.enc", result)
            (document_dir / "source.pdf.enc").write_bytes(self._cipher.encrypt(source_pdf))
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO recent_documents
                        (order_id, user_id, created_at, updated_at, expires_at, ledger_entry_id)
                    VALUES (?, ?, ?, ?, ?, COALESCE((SELECT ledger_entry_id FROM recent_documents WHERE order_id = ?), NULL))
                    """,
                    (order_id, user_id, created.isoformat(), created.isoformat(), expires.isoformat(), order_id),
                )
        except Exception:
            shutil.rmtree(document_dir, ignore_errors=True)
            raise
        return result

    def get_recent_document(self, user_id: str, order_id: str) -> dict[str, Any] | None:
        self.purge_recent_history()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM recent_documents WHERE user_id = ? AND order_id = ?",
                (user_id, order_id),
            ).fetchone()
        if row is None:
            return None
        result = self._decrypt_json_file(self.history_dir / order_id / "result.json.enc")
        result["history_expires_at"] = row["expires_at"]
        result["ledger_entry_id"] = row["ledger_entry_id"]
        result["storage_mode"] = "recent_7d"
        return result

    def list_recent_documents(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        self.purge_recent_history()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM recent_documents
                WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (user_id, max(1, limit), max(0, offset)),
            ).fetchall()
        documents: list[dict[str, Any]] = []
        for row in rows:
            try:
                result = self._decrypt_json_file(self.history_dir / row["order_id"] / "result.json.enc")
            except (ValueError, OSError):
                continue
            summary = self._history_summary(result)
            summary.update(
                {
                    "source_type": "single",
                    "history_expires_at": row["expires_at"],
                    "ledger_entry_id": row["ledger_entry_id"],
                }
            )
            documents.append(summary)
        return documents

    def update_recent_document(self, user_id: str, order_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_recent_document(user_id, order_id)
        if current is None:
            return None
        result = dict(result)
        result["storage_mode"] = "recent_7d"
        result["history_expires_at"] = current["history_expires_at"]
        self._encrypt_json_file(self.history_dir / order_id / "result.json.enc", result)
        with self._connect() as connection:
            connection.execute(
                "UPDATE recent_documents SET updated_at = ? WHERE user_id = ? AND order_id = ?",
                (datetime.now(UTC).isoformat(), user_id, order_id),
            )
        return result

    def read_recent_source_pdf(self, user_id: str, order_id: str) -> bytes:
        if self.get_recent_document(user_id, order_id) is None:
            raise LookupError("history_document_not_found")
        return self._decrypt_file(self.history_dir / order_id / "source.pdf.enc")

    def promote_to_ledger(
        self,
        user_id: str,
        source_type: str,
        source_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT entry_id FROM ledger_entries WHERE user_id = ? AND source_type = ? AND source_id = ?",
                (user_id, source_type, source_id),
            ).fetchone()
        entry_id = existing["entry_id"] if existing else uuid.uuid4().hex
        payload = self._ledger_payload(result, source_type, source_id)
        payload.update({"entry_id": entry_id, "created_at": now, "updated_at": now})
        self._encrypt_json_file(self.ledger_dir / entry_id / "entry.json.enc", payload)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ledger_entries (entry_id, user_id, source_type, source_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, source_type, source_id)
                DO UPDATE SET updated_at = excluded.updated_at
                """,
                (entry_id, user_id, source_type, source_id, now, now),
            )
            if source_type == "single":
                connection.execute(
                    "UPDATE recent_documents SET ledger_entry_id = ? WHERE user_id = ? AND order_id = ?",
                    (entry_id, user_id, source_id),
                )
        return self.get_ledger_entry(user_id, entry_id)  # type: ignore[return-value]

    def get_ledger_entry(self, user_id: str, entry_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_entries WHERE user_id = ? AND entry_id = ?",
                (user_id, entry_id),
            ).fetchone()
        if row is None:
            return None
        payload = self._decrypt_json_file(self.ledger_dir / entry_id / "entry.json.enc")
        payload["created_at"] = row["created_at"]
        payload["updated_at"] = row["updated_at"]
        return payload

    def list_ledger_entries(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, max(1, limit)),
            ).fetchall()
        entries: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = self._decrypt_json_file(self.ledger_dir / row["entry_id"] / "entry.json.enc")
            except (ValueError, OSError):
                continue
            summary = self._history_summary({**payload, "id": row["entry_id"], "order_id": payload.get("source_id")})
            summary.update(
                {
                    "entry_id": row["entry_id"],
                    "source_type": payload.get("source_type"),
                    "source_id": payload.get("source_id"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
            entries.append(summary)
        return entries

    def delete_recent_document(self, user_id: str, order_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM recent_documents WHERE user_id = ? AND order_id = ?",
                (user_id, order_id),
            )
        if cursor.rowcount:
            shutil.rmtree(self.history_dir / order_id, ignore_errors=True)
        return bool(cursor.rowcount)

    def delete_ledger_entry(self, user_id: str, entry_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ledger_entries WHERE user_id = ? AND entry_id = ?",
                (user_id, entry_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "UPDATE recent_documents SET ledger_entry_id = NULL WHERE user_id = ? AND ledger_entry_id = ?",
                    (user_id, entry_id),
                )
        if cursor.rowcount:
            shutil.rmtree(self.ledger_dir / entry_id, ignore_errors=True)
        return bool(cursor.rowcount)

    def delete_user_history(self, user_id: str) -> tuple[int, int]:
        recent = self.list_recent_documents(user_id, limit=10000)
        ledger = self.list_ledger_entries(user_id, limit=10000)
        for item in recent:
            self.delete_recent_document(user_id, str(item["id"]))
        for item in ledger:
            self.delete_ledger_entry(user_id, str(item["entry_id"]))
        return len(recent), len(ledger)

    def purge_recent_history(self) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT order_id, user_id FROM recent_documents WHERE expires_at <= ?",
                (now,),
            ).fetchall()
        for row in rows:
            self.delete_recent_document(row["user_id"], row["order_id"])
        return len(rows)

    @staticmethod
    def _parse_order(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _parse_case(row: sqlite3.Row) -> dict[str, Any]:
        case = dict(row)
        case["has_source_pdf"] = bool(case["has_source_pdf"])
        return case

    def create_parse_order(
        self,
        user_id: str,
        input_sha256: str,
        page_count: int,
        parser_version: str,
    ) -> str:
        order_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO parse_orders
                    (order_id, user_id, created_at, status, page_count, parser_version, input_sha256)
                VALUES (?, ?, ?, 'processing', ?, ?, ?)
                """,
                (order_id, user_id, datetime.now(UTC).isoformat(), page_count, parser_version, input_sha256),
            )
        return order_id

    def complete_parse_order(
        self,
        order_id: str,
        *,
        extraction_method: str,
        output_sha256: str,
        duration_ms: int,
        overall_confidence: float,
        warning_count: int,
        result_status: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE parse_orders
                SET completed_at = ?, status = ?, extraction_method = ?, output_sha256 = ?, duration_ms = ?,
                    overall_confidence = ?, warning_count = ?, error_code = NULL
                WHERE order_id = ?
                """,
                (
                    datetime.now(UTC).isoformat(),
                    result_status,
                    extraction_method,
                    output_sha256,
                    max(0, duration_ms),
                    max(0.0, min(1.0, overall_confidence)),
                    max(0, warning_count),
                    order_id,
                ),
            )

    def fail_parse_order(self, order_id: str, error_code: str, duration_ms: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE parse_orders
                SET completed_at = ?, status = 'failed', duration_ms = ?, error_code = ?
                WHERE order_id = ?
                """,
                (datetime.now(UTC).isoformat(), max(0, duration_ms), error_code[:80], order_id),
            )

    def get_parse_order(self, user_id: str, order_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM parse_orders WHERE user_id = ? AND order_id = ?",
                (user_id, order_id),
            ).fetchone()
        return self._parse_order(row) if row else None

    def list_parse_orders(self, user_id: str, limit: int | None = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if limit is None:
                rows = connection.execute(
                    "SELECT * FROM parse_orders WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM parse_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
        return [self._parse_order(row) for row in rows]

    def create_case(
        self,
        *,
        user_id: str,
        order_id: str,
        description: str,
        original_result: dict[str, Any],
        corrected_result: dict[str, Any],
        source_pdf: bytes | None,
    ) -> dict[str, Any]:
        if self._cipher is None:
            raise RuntimeError("diagnostic_encryption_unavailable")
        order = self.get_parse_order(user_id, order_id)
        if order is None:
            raise LookupError("parse_order_not_found")
        if order["status"] == "failed" or not order["output_sha256"]:
            raise ValueError("parse_order_not_complete")
        if result_digest(original_result) != order["output_sha256"]:
            raise ValueError("original_result_mismatch")
        if source_pdf is not None and sha256_bytes(source_pdf) != order["input_sha256"]:
            raise ValueError("source_pdf_mismatch")

        case_id = uuid.uuid4().hex
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(days=self.retention_days)
        case_dir = self.evidence_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=False)
        bundle = json.dumps(
            {
                "case_id": case_id,
                "order_id": order_id,
                "description": description,
                "original_result": canonical_result_payload(original_result),
                "corrected_result": canonical_result_payload(corrected_result),
                "consented_at": created_at.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            (case_dir / "report.json.enc").write_bytes(self._cipher.encrypt(bundle))
            if source_pdf is not None:
                (case_dir / "source.pdf.enc").write_bytes(self._cipher.encrypt(source_pdf))
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO diagnostic_cases
                        (case_id, order_id, user_id, has_source_pdf, status, created_at, expires_at, deleted_at)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, NULL)
                    """,
                    (
                        case_id,
                        order_id,
                        user_id,
                        int(source_pdf is not None),
                        created_at.isoformat(),
                        expires_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            shutil.rmtree(case_dir, ignore_errors=True)
            raise ValueError("diagnostic_case_exists") from error
        except Exception:
            shutil.rmtree(case_dir, ignore_errors=True)
            raise
        return self.get_case(user_id, case_id)  # type: ignore[return-value]

    def get_case(self, user_id: str, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM diagnostic_cases WHERE user_id = ? AND case_id = ? AND deleted_at IS NULL",
                (user_id, case_id),
            ).fetchone()
        return self._parse_case(row) if row else None

    def get_case_for_admin(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.*, u.email, o.extraction_method, o.parser_version, o.page_count,
                       o.overall_confidence, o.warning_count, o.duration_ms
                FROM diagnostic_cases c
                JOIN users u ON u.id = c.user_id
                JOIN parse_orders o ON o.order_id = c.order_id
                WHERE c.case_id = ? AND c.deleted_at IS NULL
                """,
                (case_id,),
            ).fetchone()
        return self._parse_case(row) if row else None

    def list_cases(self, user_id: str) -> list[dict[str, Any]]:
        self.purge_expired()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM diagnostic_cases
                WHERE user_id = ? AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._parse_case(row) for row in rows]

    def list_cases_for_admin(self, limit: int = 100) -> list[dict[str, Any]]:
        self.purge_expired()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, u.email, o.extraction_method, o.parser_version, o.page_count,
                       o.overall_confidence, o.warning_count, o.duration_ms
                FROM diagnostic_cases c
                JOIN users u ON u.id = c.user_id
                JOIN parse_orders o ON o.order_id = c.order_id
                WHERE c.deleted_at IS NULL
                ORDER BY c.created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._parse_case(row) for row in rows]

    def _decrypt_file(self, path: Path) -> bytes:
        if self._cipher is None:
            raise RuntimeError("diagnostic_encryption_unavailable")
        try:
            return self._cipher.decrypt(path.read_bytes())
        except (InvalidToken, OSError) as error:
            raise ValueError("diagnostic_evidence_unreadable") from error

    def read_case_bundle(self, case_id: str) -> dict[str, Any]:
        case = self.get_case_for_admin(case_id)
        if case is None:
            raise LookupError("diagnostic_case_not_found")
        return json.loads(self._decrypt_file(self.evidence_dir / case_id / "report.json.enc"))

    def read_source_pdf(self, case_id: str) -> bytes:
        case = self.get_case_for_admin(case_id)
        if case is None or not case["has_source_pdf"]:
            raise LookupError("diagnostic_source_not_found")
        return self._decrypt_file(self.evidence_dir / case_id / "source.pdf.enc")

    def delete_case(self, user_id: str, case_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM diagnostic_cases WHERE user_id = ? AND case_id = ?",
                (user_id, case_id),
            )
        if cursor.rowcount:
            shutil.rmtree(self.evidence_dir / case_id, ignore_errors=True)
        return bool(cursor.rowcount)

    def delete_case_for_admin(self, case_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM diagnostic_cases WHERE case_id = ?", (case_id,))
        if cursor.rowcount:
            shutil.rmtree(self.evidence_dir / case_id, ignore_errors=True)
        return bool(cursor.rowcount)

    def delete_user_cases(self, user_id: str) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id FROM diagnostic_cases WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        for row in rows:
            self.delete_case(user_id, row["case_id"])
        return len(rows)

    def purge_expired(self) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id FROM diagnostic_cases WHERE expires_at <= ?",
                (now,),
            ).fetchall()
        for row in rows:
            self.delete_case_for_admin(row["case_id"])
        return len(rows)
