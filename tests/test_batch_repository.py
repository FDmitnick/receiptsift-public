import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from backend.batch_repository import BatchRepository, BatchStorageError
from backend.repository import DocumentRepository


def _repository(tmp_path, *, source_days=30, result_days=90):
    database_path = tmp_path / "receiptsift.sqlite3"
    DocumentRepository(database_path, tmp_path / "previews")
    repository = BatchRepository(
        database_path,
        tmp_path / "batch-objects",
        Fernet.generate_key().decode("ascii"),
        source_retention_days=source_days,
        result_retention_days=result_days,
    )
    return database_path, repository


def test_batch_sources_are_encrypted_scoped_and_deduplicated(tmp_path):
    database_path, repository = _repository(tmp_path)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    stranger = accounts.create_user("stranger@example.com", "hash")
    batch = repository.create_batch(owner["id"], "March receipts")
    source = b"%PDF-1.7\nprivate receipt payload"

    document = repository.add_document(owner["id"], batch["id"], "../march.pdf", source)

    assert document["filename"] == "march.pdf"
    assert document["status"] == "staged"
    assert repository.get_batch(owner["id"], batch["id"])["staged_count"] == 1
    assert repository.read_source(owner["id"], document["id"]) == source
    with pytest.raises(BatchStorageError, match="document_not_found"):
        repository.read_source(stranger["id"], document["id"])
    with pytest.raises(BatchStorageError, match="duplicate_document"):
        repository.add_document(owner["id"], batch["id"], "duplicate.pdf", source)

    encrypted_files = list((tmp_path / "batch-objects").rglob("*.bin"))
    assert len(encrypted_files) == 1
    assert source not in encrypted_files[0].read_bytes()


def test_batch_processing_review_and_summary(tmp_path):
    database_path, repository = _repository(tmp_path)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    batch = repository.create_batch(owner["id"], "Client A")
    document = repository.add_document(owner["id"], batch["id"], "receipt.pdf", b"%PDF-1.4\nreceipt")

    assert repository.claim_next_document() is None
    assert repository.start_batch(owner["id"], batch["id"]) == 1
    claimed = repository.claim_next_document()
    assert claimed["id"] == document["id"]
    assert claimed["source_pdf"].startswith(b"%PDF-")
    assert claimed["attempt_count"] == 1
    assert claimed["queued_at"]

    result = {
        "status": "needs_review",
        "page_count": 1,
        "extraction_method": "embedded_text",
        "fields": {"total": {"value": 12.5}},
    }
    completed = repository.complete_document(owner["id"], document["id"], result)
    assert completed["status"] == "needs_review"
    assert repository.get_batch(owner["id"], batch["id"])["review_count"] == 1

    corrected = {**result, "status": "ready", "fields": {"total": {"value": 13.5}}}
    reviewed = repository.save_review(owner["id"], document["id"], {"total": 13.5}, corrected)
    assert reviewed["status"] == "ready"
    summary = repository.get_batch(owner["id"], batch["id"])
    assert summary["status"] == "ready"
    assert summary["ready_count"] == 1

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM receipt_review_changes").fetchone()[0] == 1


def test_staged_and_queued_documents_can_be_deleted_but_processing_cannot(tmp_path):
    database_path, repository = _repository(tmp_path)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    batch = repository.create_batch(owner["id"], "Editable queue")

    staged = repository.add_document(owner["id"], batch["id"], "staged.pdf", b"%PDF-1.4\nstaged")
    assert repository.delete_document(owner["id"], staged["id"]) is True
    assert repository.get_document(owner["id"], staged["id"]) is None
    assert list((tmp_path / "batch-objects").rglob("*.bin")) == []

    queued = repository.add_document(owner["id"], batch["id"], "queued.pdf", b"%PDF-1.4\nqueued")
    assert repository.start_batch(owner["id"], batch["id"]) == 1
    assert repository.delete_document(owner["id"], queued["id"]) is True
    assert repository.claim_next_document() is None

    processing = repository.add_document(owner["id"], batch["id"], "processing.pdf", b"%PDF-1.4\nprocessing")
    assert repository.start_batch(owner["id"], batch["id"]) == 1
    assert repository.claim_next_document()["id"] == processing["id"]
    with pytest.raises(BatchStorageError, match="document_processing"):
        repository.delete_document(owner["id"], processing["id"])
    assert repository.get_document(owner["id"], processing["id"])["status"] == "processing"


def test_bulk_delete_is_atomic_when_a_selected_document_is_processing(tmp_path):
    database_path, repository = _repository(tmp_path)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    batch = repository.create_batch(owner["id"], "Bulk cleanup")
    documents = [
        repository.add_document(
            owner["id"],
            batch["id"],
            f"document-{index}.pdf",
            f"%PDF-1.4\ndocument {index}".encode(),
        )
        for index in range(3)
    ]
    assert repository.start_batch(owner["id"], batch["id"]) == 3
    processing = repository.claim_next_document()
    assert processing["id"] == documents[0]["id"]

    document_ids = [document["id"] for document in documents]
    with pytest.raises(BatchStorageError, match="document_processing"):
        repository.delete_documents(owner["id"], batch["id"], document_ids)
    assert len(repository.list_documents(owner["id"], batch["id"])) == 3

    repository.fail_document(owner["id"], processing["id"], "test_complete")
    assert repository.delete_documents(owner["id"], batch["id"], document_ids) == 3
    assert repository.list_documents(owner["id"], batch["id"]) == []
    assert list((tmp_path / "batch-objects").rglob("*.bin")) == []


def test_batch_progress_reports_real_stage_queue_position_and_dynamic_eta(tmp_path):
    database_path, repository = _repository(tmp_path)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    now = datetime.now(UTC)
    batch = repository.create_batch(owner["id"], "Progress", now=now - timedelta(minutes=1))
    documents = [
        repository.add_document(
            owner["id"],
            batch["id"],
            f"receipt-{index}.pdf",
            f"%PDF-1.4\nreceipt {index}".encode(),
            now=now - timedelta(seconds=50 - index),
        )
        for index in range(3)
    ]
    assert repository.start_batch(owner["id"], batch["id"], now=now - timedelta(seconds=20)) == 3
    claimed = repository.claim_next_document(now=now - timedelta(seconds=20))
    assert claimed["id"] == documents[0]["id"]
    assert repository.update_progress(
        owner["id"],
        claimed["id"],
        "model_extraction",
        50,
        "Running model",
        now=now - timedelta(seconds=10),
    )

    listed = repository.list_documents(owner["id"], batch["id"])
    assert listed[0]["progress_stage"] == "model_extraction"
    assert listed[0]["progress_percent"] == 50
    assert listed[0]["elapsed_seconds"] >= 19
    assert listed[0]["estimated_remaining_seconds"] >= 19
    assert listed[0]["progress_stale"] is False
    assert listed[1]["queue_position"] == 1
    assert listed[1]["estimated_start_seconds"] >= 19
    assert listed[2]["queue_position"] == 2
    assert listed[2]["estimated_start_seconds"] > listed[1]["estimated_start_seconds"]


def test_existing_sqlite_batch_documents_are_migrated_with_progress_defaults(tmp_path):
    database_path = tmp_path / "receiptsift.sqlite3"
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    timestamp = datetime(2026, 8, 25, tzinfo=UTC).isoformat()

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE receipt_batches (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                source_expires_at TEXT NOT NULL,
                result_expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE receipt_batch_documents (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES receipt_batches(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                storage_key TEXT,
                status TEXT NOT NULL,
                page_count INTEGER,
                extraction_method TEXT,
                result_json TEXT,
                error_code TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                source_deleted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(batch_id, source_sha256)
            );
            """
        )
        connection.execute(
            "INSERT INTO receipt_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-batch", owner["id"], "Legacy", "processing", timestamp, timestamp, timestamp, timestamp),
        )
        for index, status in enumerate(("queued", "processing", "ready")):
            connection.execute(
                """
                INSERT INTO receipt_batch_documents
                    (id, batch_id, user_id, filename, source_sha256, status, result_json, created_at, updated_at)
                VALUES (?, 'legacy-batch', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"legacy-{status}",
                    owner["id"],
                    f"{status}.pdf",
                    f"hash-{index}",
                    status,
                    "{}" if status == "ready" else None,
                    timestamp,
                    timestamp,
                ),
            )

    repository = BatchRepository(
        database_path,
        tmp_path / "batch-objects",
        Fernet.generate_key().decode("ascii"),
    )

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(receipt_batch_documents)")}
    assert {
        "progress_stage",
        "progress_percent",
        "progress_detail",
        "queued_at",
        "processing_started_at",
    } <= columns

    documents = {document["filename"]: document for document in repository.list_documents(owner["id"], "legacy-batch")}
    assert documents["queued.pdf"]["progress_stage"] == "queued"
    assert documents["queued.pdf"]["queued_at"] == timestamp
    assert documents["processing.pdf"]["progress_stage"] == "processing"
    assert documents["processing.pdf"]["progress_percent"] == 5
    assert documents["processing.pdf"]["processing_started_at"] == timestamp
    assert documents["ready.pdf"]["progress_stage"] == "complete"
    assert documents["ready.pdf"]["progress_percent"] == 100


def test_retention_removes_sources_before_results(tmp_path):
    database_path, repository = _repository(tmp_path, source_days=2, result_days=5)
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    created = datetime(2026, 8, 1, tzinfo=UTC)
    batch = repository.create_batch(owner["id"], "Expiring", now=created)
    document = repository.add_document(owner["id"], batch["id"], "receipt.pdf", b"%PDF-1.4\nreceipt", now=created)
    repository.claim_next_document(now=created)
    repository.complete_document(
        owner["id"],
        document["id"],
        {"status": "ready", "page_count": 1, "extraction_method": "embedded_text"},
        now=created,
    )

    first = repository.purge_expired(now=created + timedelta(days=3))
    assert first == {"sources_deleted": 1, "batches_deleted": 0}
    assert repository.get_document(owner["id"], document["id"])["result"] is not None
    with pytest.raises(BatchStorageError, match="source_expired"):
        repository.read_source(owner["id"], document["id"])

    second = repository.purge_expired(now=created + timedelta(days=6))
    assert second == {"sources_deleted": 0, "batches_deleted": 1}
    assert repository.get_batch(owner["id"], batch["id"]) is None


def test_batch_storage_fails_closed_without_valid_encryption_key(tmp_path):
    database_path = tmp_path / "receiptsift.sqlite3"
    accounts = DocumentRepository(database_path, tmp_path / "previews")
    owner = accounts.create_user("owner@example.com", "hash")
    repository = BatchRepository(database_path, tmp_path / "batch-objects", "not-a-fernet-key")
    batch = repository.create_batch(owner["id"], "Blocked")

    assert repository.configured is False
    with pytest.raises(BatchStorageError, match="batch_storage_not_configured"):
        repository.add_document(owner["id"], batch["id"], "receipt.pdf", b"%PDF-1.4\nreceipt")
    assert list((tmp_path / "batch-objects").rglob("*.bin")) == []
