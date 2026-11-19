from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .object_store import LocalObjectStore, ObjectStore, ObjectStoreError

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - production requirements install this dependency
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - installed by production requirements
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


class _Connection:
    def __init__(self, connection: Any, postgres: bool) -> None:
        self.connection = connection
        self.postgres = postgres

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        try:
            return self.connection.__exit__(*args)
        finally:
            if not self.postgres:
                self.connection.close()

    def execute(self, query: str, params: tuple[Any, ...] = ()):
        if self.postgres:
            query = "BEGIN" if query == "BEGIN IMMEDIATE" else query.replace("?", "%s")
        return self.connection.execute(query, params)


class BatchStorageError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class BatchRepository:
    """Persistent, user-scoped receipt batches with encrypted source storage.

    The repository is intentionally not connected to public routes yet. It is the
    storage boundary for the upcoming asynchronous batch workspace.
    """

    def __init__(
        self,
        database_path: Path | str,
        object_dir: Path | ObjectStore,
        encryption_key: str,
        source_retention_days: int = 30,
        result_retention_days: int = 90,
    ) -> None:
        database_value = str(database_path)
        self.database_url = database_value if database_value.startswith(("postgres://", "postgresql://")) else ""
        self.database_path = None if self.database_url else Path(database_value)
        self.object_store = LocalObjectStore(object_dir) if isinstance(object_dir, Path) else object_dir
        self.source_retention_days = max(1, source_retention_days)
        self.result_retention_days = max(self.source_retention_days, result_retention_days)
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

    def _connect(self) -> _Connection:
        if self.database_url:
            if psycopg is None:
                raise BatchStorageError("psycopg_not_installed")
            return _Connection(psycopg.connect(self.database_url, row_factory=dict_row), True)
        if self.database_path is None:  # pragma: no cover - guarded by constructor
            raise BatchStorageError("database_not_configured")
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return _Connection(connection, False)

    def _initialize(self) -> None:
        if self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            user_reference = "" if connection.postgres else " REFERENCES users(id) ON DELETE CASCADE"
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS receipt_batches (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL{user_reference},
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_expires_at TEXT NOT NULL,
                    result_expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_receipt_batches_user_created "
                "ON receipt_batches(user_id, created_at DESC)"
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS receipt_batch_documents (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES receipt_batches(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL{user_reference},
                    filename TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    storage_key TEXT,
                    status TEXT NOT NULL,
                    page_count INTEGER,
                    extraction_method TEXT,
                    result_json TEXT,
                    error_code TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    progress_stage TEXT,
                    progress_percent INTEGER NOT NULL DEFAULT 0,
                    progress_detail TEXT,
                    queued_at TEXT,
                    processing_started_at TEXT,
                    source_deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(batch_id, source_sha256)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_receipt_batch_documents_queue "
                "ON receipt_batch_documents(status, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_receipt_batch_documents_user "
                "ON receipt_batch_documents(user_id, batch_id, created_at)"
            )
            progress_columns = {
                "progress_stage": "TEXT",
                "progress_percent": "INTEGER NOT NULL DEFAULT 0",
                "progress_detail": "TEXT",
                "queued_at": "TEXT",
                "processing_started_at": "TEXT",
            }
            if connection.postgres:
                for column, definition in progress_columns.items():
                    connection.execute(
                        f"ALTER TABLE receipt_batch_documents ADD COLUMN IF NOT EXISTS {column} {definition}"
                    )
            else:
                existing_columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(receipt_batch_documents)").fetchall()
                }
                for column, definition in progress_columns.items():
                    if column not in existing_columns:
                        connection.execute(f"ALTER TABLE receipt_batch_documents ADD COLUMN {column} {definition}")
            connection.execute(
                """
                UPDATE receipt_batch_documents
                SET progress_stage = CASE status
                        WHEN 'staged' THEN 'staged'
                        WHEN 'queued' THEN 'queued'
                        WHEN 'processing' THEN 'processing'
                        WHEN 'ready' THEN 'complete'
                        WHEN 'needs_review' THEN 'complete'
                        WHEN 'failed' THEN 'failed'
                        ELSE status
                    END,
                    progress_percent = CASE
                        WHEN status IN ('ready', 'needs_review') THEN 100
                        WHEN status = 'processing' AND progress_percent = 0 THEN 5
                        ELSE progress_percent
                    END,
                    queued_at = CASE WHEN status = 'queued' THEN COALESCE(queued_at, updated_at) ELSE queued_at END,
                    processing_started_at = CASE
                        WHEN status = 'processing' THEN COALESCE(processing_started_at, updated_at)
                        ELSE processing_started_at
                    END
                WHERE progress_stage IS NULL
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS receipt_review_changes (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES receipt_batch_documents(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL{user_reference},
                    patch_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_receipt_review_changes_document "
                "ON receipt_review_changes(document_id, created_at)"
            )

    @staticmethod
    def _now(value: datetime | None = None) -> datetime:
        now = value or datetime.now(UTC)
        return now if now.tzinfo is not None else now.replace(tzinfo=UTC)

    def create_batch(self, user_id: str, name: str, now: datetime | None = None) -> dict[str, Any]:
        created = self._now(now)
        batch_id = uuid.uuid4().hex
        clean_name = name.strip()[:160] or f"Receipt batch {created.date().isoformat()}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO receipt_batches
                    (id, user_id, name, status, source_expires_at, result_expires_at, created_at, updated_at)
                VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    user_id,
                    clean_name,
                    (created + timedelta(days=self.source_retention_days)).isoformat(),
                    (created + timedelta(days=self.result_retention_days)).isoformat(),
                    created.isoformat(),
                    created.isoformat(),
                ),
            )
        return self.get_batch(user_id, batch_id)  # type: ignore[return-value]

    @staticmethod
    def _batch_status(counts: dict[str, int]) -> str:
        total = counts["document_count"]
        if total == 0:
            return "draft"
        if counts["queued_count"] or counts["processing_count"]:
            return "processing"
        if counts["staged_count"]:
            return "staged"
        if counts["review_count"]:
            return "needs_review"
        if counts["ready_count"]:
            return "ready"
        return "failed"

    def _batch_row(self, connection: _Connection, user_id: str, batch_id: str) -> Any | None:
        return connection.execute(
            """
            SELECT b.*,
                COUNT(d.id) AS document_count,
                COALESCE(SUM(CASE WHEN d.status = 'staged' THEN 1 ELSE 0 END), 0) AS staged_count,
                COALESCE(SUM(CASE WHEN d.status = 'queued' THEN 1 ELSE 0 END), 0) AS queued_count,
                COALESCE(SUM(CASE WHEN d.status = 'processing' THEN 1 ELSE 0 END), 0) AS processing_count,
                COALESCE(SUM(CASE WHEN d.status = 'ready' THEN 1 ELSE 0 END), 0) AS ready_count,
                COALESCE(SUM(CASE WHEN d.status = 'needs_review' THEN 1 ELSE 0 END), 0) AS review_count,
                COALESCE(SUM(CASE WHEN d.status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count
            FROM receipt_batches b
            LEFT JOIN receipt_batch_documents d ON d.batch_id = b.id
            WHERE b.id = ? AND b.user_id = ?
            GROUP BY b.id
            """,
            (batch_id, user_id),
        ).fetchone()

    def get_batch(self, user_id: str, batch_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = self._batch_row(connection, user_id, batch_id)
        if row is None:
            return None
        counts = {
            key: int(row[key])
            for key in (
                "document_count",
                "staged_count",
                "queued_count",
                "processing_count",
                "ready_count",
                "review_count",
                "failed_count",
            )
        }
        return {
            "id": row["id"],
            "name": row["name"],
            "status": self._batch_status(counts),
            **counts,
            "source_expires_at": row["source_expires_at"],
            "result_expires_at": row["result_expires_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_batches(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            ids = connection.execute(
                "SELECT id FROM receipt_batches WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, max(1, min(limit, 100)), max(0, offset)),
            ).fetchall()
        return [batch for row in ids if (batch := self.get_batch(user_id, row["id"])) is not None]

    def _write_source(self, storage_key: str, source_pdf: bytes) -> None:
        if self._cipher is None:
            raise BatchStorageError("batch_storage_not_configured")
        try:
            self.object_store.put(storage_key, self._cipher.encrypt(source_pdf))
        except ObjectStoreError as error:
            raise BatchStorageError(str(error)) from error

    def _read_source(self, storage_key: str) -> bytes:
        if self._cipher is None:
            raise BatchStorageError("batch_storage_not_configured")
        try:
            return self._cipher.decrypt(self.object_store.get(storage_key))
        except ObjectStoreError as error:
            raise BatchStorageError(str(error)) from error
        except InvalidToken as error:
            raise BatchStorageError("source_decryption_failed") from error

    def add_document(
        self,
        user_id: str,
        batch_id: str,
        filename: str,
        source_pdf: bytes,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if self._cipher is None:
            raise BatchStorageError("batch_storage_not_configured")
        if not source_pdf.startswith(b"%PDF-"):
            raise BatchStorageError("not_pdf")
        if self.get_batch(user_id, batch_id) is None:
            raise BatchStorageError("batch_not_found")

        created = self._now(now)
        document_id = uuid.uuid4().hex
        storage_key = uuid.uuid4().hex
        clean_filename = Path(filename).name.strip()[:255] or "receipt.pdf"
        source_sha256 = hashlib.sha256(source_pdf).hexdigest()
        self._write_source(storage_key, source_pdf)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO receipt_batch_documents
                        (id, batch_id, user_id, filename, source_sha256, storage_key, status,
                         progress_stage, progress_percent, progress_detail, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'staged', 'staged', 0, 'Waiting for confirmation', ?, ?)
                    """,
                    (
                        document_id,
                        batch_id,
                        user_id,
                        clean_filename,
                        source_sha256,
                        storage_key,
                        created.isoformat(),
                        created.isoformat(),
                    ),
                )
                connection.execute(
                    "UPDATE receipt_batches SET status = 'staged', updated_at = ? WHERE id = ? AND user_id = ?",
                    (created.isoformat(), batch_id, user_id),
                )
        except Exception as error:
            is_integrity_error = isinstance(error, sqlite3.IntegrityError) or (
                psycopg is not None and isinstance(error, psycopg.IntegrityError)
            )
            if not is_integrity_error:
                self.object_store.delete(storage_key)
                raise
            self.object_store.delete(storage_key)
            raise BatchStorageError("duplicate_document") from error
        return self.get_document(user_id, document_id)  # type: ignore[return-value]

    def start_batch(
        self,
        user_id: str,
        batch_id: str,
        now: datetime | None = None,
    ) -> int | None:
        """Atomically release every staged document in an owned batch to the worker queue."""
        started = self._now(now).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE" if connection.postgres else ""
            batch = connection.execute(
                f"SELECT id FROM receipt_batches WHERE id = ? AND user_id = ?{lock_clause}",
                (batch_id, user_id),
            ).fetchone()
            if batch is None:
                return None
            cursor = connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'queued', error_code = NULL, progress_stage = 'queued', progress_percent = 0,
                    progress_detail = 'Waiting for a worker', queued_at = ?, processing_started_at = NULL,
                    updated_at = ?
                WHERE batch_id = ? AND user_id = ? AND status = 'staged'
                    AND storage_key IS NOT NULL
                """,
                (started, started, batch_id, user_id),
            )
            if cursor.rowcount:
                connection.execute(
                    "UPDATE receipt_batches SET status = 'processing', updated_at = ? WHERE id = ? AND user_id = ?",
                    (started, batch_id, user_id),
                )
        return int(cursor.rowcount)

    @staticmethod
    def _document_payload(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "batch_id": row["batch_id"],
            "filename": row["filename"],
            "sha256": row["source_sha256"],
            "status": row["status"],
            "page_count": row["page_count"],
            "extraction_method": row["extraction_method"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error_code": row["error_code"],
            "attempt_count": row["attempt_count"],
            "progress_stage": row["progress_stage"],
            "progress_percent": int(row["progress_percent"] or 0),
            "progress_detail": row["progress_detail"],
            "queued_at": row["queued_at"],
            "processing_started_at": row["processing_started_at"],
            "source_available": bool(row["storage_key"] and not row["source_deleted_at"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_document(self, user_id: str, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM receipt_batch_documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            ).fetchone()
        return self._document_payload(row) if row else None

    def list_documents(self, user_id: str, batch_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM receipt_batch_documents WHERE batch_id = ? AND user_id = ? ORDER BY created_at",
                (batch_id, user_id),
            ).fetchall()
            documents = [self._document_payload(row) for row in rows]
            self._attach_progress_estimates(connection, documents)
        return documents

    @staticmethod
    def _elapsed_seconds(started_at: str | None, ended_at: str | None = None) -> float | None:
        if not started_at:
            return None
        try:
            started = datetime.fromisoformat(started_at)
            ended = datetime.fromisoformat(ended_at) if ended_at else datetime.now(UTC)
            started = started if started.tzinfo is not None else started.replace(tzinfo=UTC)
            ended = ended if ended.tzinfo is not None else ended.replace(tzinfo=UTC)
            return max(0.0, (ended - started).total_seconds())
        except (TypeError, ValueError):
            return None

    def _attach_progress_estimates(self, connection: _Connection, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        history = connection.execute(
            """
            SELECT processing_started_at, updated_at
            FROM receipt_batch_documents
            WHERE status IN ('ready', 'needs_review', 'failed') AND processing_started_at IS NOT NULL
            ORDER BY updated_at DESC LIMIT 50
            """
        ).fetchall()
        durations = [
            duration
            for row in history
            if (duration := self._elapsed_seconds(row["processing_started_at"], row["updated_at"])) is not None
            and 0.5 <= duration <= 900
        ]
        average_seconds = sum(durations) / len(durations) if durations else None
        active_rows = connection.execute(
            """
            SELECT id, processing_started_at, progress_percent, updated_at
            FROM receipt_batch_documents WHERE status = 'processing'
            """
        ).fetchall()

        active_remaining: dict[str, float | None] = {}
        inferred_totals: list[float] = []
        for row in active_rows:
            elapsed = self._elapsed_seconds(row["processing_started_at"])
            percent = max(0, min(int(row["progress_percent"] or 0), 99))
            total = None if elapsed is not None and elapsed >= 600 else average_seconds
            if elapsed is not None and 5 <= elapsed < 600 and percent >= 10:
                live_total = max(15.0, min(600.0, elapsed / (percent / 100)))
                total = max(total or 0.0, live_total)
                inferred_totals.append(live_total)
            active_remaining[row["id"]] = None if elapsed is None or total is None else max(0.0, total - elapsed)

        service_seconds = average_seconds or (sum(inferred_totals) / len(inferred_totals) if inferred_totals else None)
        queued_rows = connection.execute(
            """
            SELECT id FROM receipt_batch_documents
            WHERE status = 'queued' ORDER BY queued_at, created_at, id
            """
        ).fetchall()
        queue_positions = {row["id"]: index + 1 for index, row in enumerate(queued_rows)}
        active_waits = list(active_remaining.values())
        known_active_wait = sum(value for value in active_waits if value is not None)
        active_wait_known = all(value is not None for value in active_waits)
        now = datetime.now(UTC)

        for document in documents:
            document["queue_position"] = None
            document["elapsed_seconds"] = None
            document["estimated_start_seconds"] = None
            document["estimated_remaining_seconds"] = None
            document["progress_stale"] = False
            if document["status"] == "processing":
                elapsed = self._elapsed_seconds(document.get("processing_started_at"))
                document["elapsed_seconds"] = round(elapsed) if elapsed is not None else None
                remaining = active_remaining.get(document["id"])
                document["estimated_remaining_seconds"] = round(remaining) if remaining is not None else None
                try:
                    progress_updated = datetime.fromisoformat(document["updated_at"])
                    progress_updated = (
                        progress_updated if progress_updated.tzinfo is not None else progress_updated.replace(tzinfo=UTC)
                    )
                    stale_after = max(30.0, min(120.0, (average_seconds or 60.0) * 0.75))
                    document["progress_stale"] = (now - progress_updated).total_seconds() >= stale_after
                except (TypeError, ValueError):
                    pass
            elif document["status"] == "queued":
                position = queue_positions.get(document["id"])
                document["queue_position"] = position
                if position == 1 and not active_rows:
                    document["estimated_start_seconds"] = 0
                elif position is not None and active_wait_known and service_seconds is not None:
                    document["estimated_start_seconds"] = round(known_active_wait + (position - 1) * service_seconds)

    def read_source(self, user_id: str, document_id: str) -> bytes:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT storage_key, source_deleted_at FROM receipt_batch_documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            ).fetchone()
        if row is None:
            raise BatchStorageError("document_not_found")
        if not row["storage_key"] or row["source_deleted_at"]:
            raise BatchStorageError("source_expired")
        return self._read_source(row["storage_key"])

    def claim_next_document(self, now: datetime | None = None) -> dict[str, Any] | None:
        claimed = self._now(now).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE SKIP LOCKED" if connection.postgres else ""
            row = connection.execute(
                f"""
                SELECT * FROM receipt_batch_documents
                WHERE status = 'queued' AND storage_key IS NOT NULL
                ORDER BY queued_at, created_at, id LIMIT 1{lock_clause}
                """
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'processing', attempt_count = attempt_count + 1,
                    progress_stage = 'security_check', progress_percent = 5,
                    progress_detail = 'Checking PDF safety', processing_started_at = ?, updated_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (claimed, claimed, row["id"]),
            )
        document = self.get_document(row["user_id"], row["id"])
        if document is None:
            return None
        document["user_id"] = row["user_id"]
        document["queued_at"] = row["updated_at"]
        try:
            document["source_pdf"] = self._read_source(row["storage_key"])
        except BatchStorageError as error:
            self.fail_document(row["user_id"], row["id"], error.code)
            raise
        return document

    def retry_document(
        self,
        user_id: str,
        document_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        retried = self._now(now).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'queued', error_code = NULL, progress_stage = 'queued', progress_percent = 0,
                    progress_detail = 'Waiting for a worker', queued_at = ?, processing_started_at = NULL,
                    updated_at = ?
                WHERE id = ? AND user_id = ? AND status IN ('failed', 'needs_review')
                    AND storage_key IS NOT NULL
                """,
                (retried, retried, document_id, user_id),
            )
        return self.get_document(user_id, document_id) if cursor.rowcount else None

    def requeue_stale_processing(
        self,
        older_than: datetime,
        now: datetime | None = None,
    ) -> int:
        cutoff = self._now(older_than).isoformat()
        updated = self._now(now).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'queued', error_code = 'worker_interrupted', progress_stage = 'queued',
                    progress_percent = 0, progress_detail = 'Waiting after worker restart', queued_at = ?,
                    processing_started_at = NULL, updated_at = ?
                WHERE status = 'processing' AND updated_at < ? AND storage_key IS NOT NULL
                """,
                (updated, updated, cutoff),
            )
        return int(cursor.rowcount)

    def update_progress(
        self,
        user_id: str,
        document_id: str,
        stage: str,
        percent: int,
        detail: str,
        now: datetime | None = None,
    ) -> bool:
        updated = self._now(now).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE receipt_batch_documents
                SET progress_stage = ?, progress_percent = ?, progress_detail = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'processing'
                """,
                (stage[:80], max(0, min(int(percent), 99)), detail[:240], updated, document_id, user_id),
            )
        return bool(cursor.rowcount)

    def complete_document(
        self,
        user_id: str,
        document_id: str,
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        completed = self._now(now).isoformat()
        document_status = "needs_review" if result.get("status") == "needs_review" else "ready"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT batch_id FROM receipt_batch_documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = ?, page_count = ?, extraction_method = ?, result_json = ?,
                    error_code = NULL, progress_stage = 'complete', progress_percent = 100,
                    progress_detail = 'Processing complete', updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    document_status,
                    int(result.get("page_count") or 0),
                    str(result.get("extraction_method") or "unknown"),
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    completed,
                    document_id,
                    user_id,
                ),
            )
            connection.execute(
                "UPDATE receipt_batches SET updated_at = ? WHERE id = ? AND user_id = ?",
                (completed, row["batch_id"], user_id),
            )
        return self.get_document(user_id, document_id)

    def fail_document(
        self,
        user_id: str,
        document_id: str,
        error_code: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        failed = self._now(now).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'failed', error_code = ?, progress_stage = 'failed',
                    progress_detail = 'Processing failed', updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (error_code[:120], failed, document_id, user_id),
            )
        return self.get_document(user_id, document_id) if cursor.rowcount else None

    def save_review(
        self,
        user_id: str,
        document_id: str,
        patch: dict[str, Any],
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        reviewed = self._now(now).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM receipt_batch_documents WHERE id = ? AND user_id = ? AND result_json IS NOT NULL",
                (document_id, user_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                INSERT INTO receipt_review_changes (id, document_id, user_id, patch_json, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    document_id,
                    user_id,
                    json.dumps(patch, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    reviewed,
                ),
            )
            connection.execute(
                """
                UPDATE receipt_batch_documents
                SET status = 'ready', result_json = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (json.dumps(result, ensure_ascii=False, separators=(",", ":")), reviewed, document_id, user_id),
            )
        return self.get_document(user_id, document_id)

    def delete_document(self, user_id: str, document_id: str, now: datetime | None = None) -> bool:
        """Delete one document unless a worker already owns it.

        The row lock makes deleting a queued document race safely with worker
        claiming: either deletion wins, or the caller receives a processing
        conflict without removing a source the worker is currently reading.
        """
        deleted = self._now(now).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE" if connection.postgres else ""
            row = connection.execute(
                f"""
                SELECT batch_id, storage_key, status
                FROM receipt_batch_documents
                WHERE id = ? AND user_id = ?{lock_clause}
                """,
                (document_id, user_id),
            ).fetchone()
            if row is None:
                return False
            if row["status"] == "processing":
                raise BatchStorageError("document_processing")
            cursor = connection.execute(
                "DELETE FROM receipt_batch_documents WHERE id = ? AND user_id = ? AND status <> 'processing'",
                (document_id, user_id),
            )
            if not cursor.rowcount:
                raise BatchStorageError("document_processing")
            connection.execute(
                "UPDATE receipt_batches SET updated_at = ? WHERE id = ? AND user_id = ?",
                (deleted, row["batch_id"], user_id),
            )
        if row["storage_key"]:
            try:
                self.object_store.delete(row["storage_key"])
            except ObjectStoreError as error:
                raise BatchStorageError(str(error)) from error
        return True

    def delete_documents(
        self,
        user_id: str,
        batch_id: str,
        document_ids: list[str],
        now: datetime | None = None,
    ) -> int:
        """Delete selected rows in one transaction unless a worker already owns one."""
        unique_ids = list(dict.fromkeys(document_ids))
        if not unique_ids:
            return 0

        deleted = self._now(now).isoformat()
        placeholders = ", ".join("?" for _ in unique_ids)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE" if connection.postgres else ""
            batch = connection.execute(
                f"SELECT id FROM receipt_batches WHERE id = ? AND user_id = ?{lock_clause}",
                (batch_id, user_id),
            ).fetchone()
            if batch is None:
                raise BatchStorageError("batch_not_found")
            rows = connection.execute(
                f"""
                SELECT id, storage_key, status
                FROM receipt_batch_documents
                WHERE batch_id = ? AND user_id = ? AND id IN ({placeholders}){lock_clause}
                """,
                (batch_id, user_id, *unique_ids),
            ).fetchall()
            if len(rows) != len(unique_ids):
                raise BatchStorageError("document_not_found")
            if any(row["status"] == "processing" for row in rows):
                raise BatchStorageError("document_processing")
            cursor = connection.execute(
                f"""
                DELETE FROM receipt_batch_documents
                WHERE batch_id = ? AND user_id = ? AND id IN ({placeholders}) AND status <> 'processing'
                """,
                (batch_id, user_id, *unique_ids),
            )
            if cursor.rowcount != len(unique_ids):
                raise BatchStorageError("document_processing")
            connection.execute(
                "UPDATE receipt_batches SET updated_at = ? WHERE id = ? AND user_id = ?",
                (deleted, batch_id, user_id),
            )

        object_error = None
        for row in rows:
            if not row["storage_key"]:
                continue
            try:
                self.object_store.delete(row["storage_key"])
            except ObjectStoreError as error:
                object_error = object_error or error
        if object_error is not None:
            raise BatchStorageError(str(object_error)) from object_error
        return len(unique_ids)

    def delete_batch(self, user_id: str, batch_id: str) -> bool:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT storage_key FROM receipt_batch_documents WHERE batch_id = ? AND user_id = ?",
                (batch_id, user_id),
            ).fetchall()
            cursor = connection.execute(
                "DELETE FROM receipt_batches WHERE id = ? AND user_id = ?",
                (batch_id, user_id),
            )
        if cursor.rowcount:
            for row in rows:
                if row["storage_key"]:
                    self.object_store.delete(row["storage_key"])
        return bool(cursor.rowcount)

    def delete_user_batches(self, user_id: str) -> int:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM receipt_batches WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            self.delete_batch(user_id, row["id"])
        return len(rows)

    def purge_expired(self, now: datetime | None = None) -> dict[str, int]:
        cutoff = self._now(now).isoformat()
        source_deleted = 0
        batches_deleted = 0
        with self._connect() as connection:
            source_rows = connection.execute(
                """
                SELECT d.id, d.storage_key
                FROM receipt_batch_documents d
                JOIN receipt_batches b ON b.id = d.batch_id
                WHERE b.source_expires_at <= ? AND d.storage_key IS NOT NULL
                """,
                (cutoff,),
            ).fetchall()
            expired_batches = connection.execute(
                "SELECT id, user_id FROM receipt_batches WHERE result_expires_at <= ?",
                (cutoff,),
            ).fetchall()

        for row in source_rows:
            self.object_store.delete(row["storage_key"])
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE receipt_batch_documents
                    SET storage_key = NULL, source_deleted_at = ?, updated_at = ?
                    WHERE id = ? AND storage_key = ?
                    """,
                    (cutoff, cutoff, row["id"], row["storage_key"]),
                )
            source_deleted += int(bool(cursor.rowcount))

        for row in expired_batches:
            batches_deleted += int(self.delete_batch(row["user_id"], row["id"]))
        return {"sources_deleted": source_deleted, "batches_deleted": batches_deleted}
