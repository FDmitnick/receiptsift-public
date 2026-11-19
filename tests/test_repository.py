import sqlite3
from datetime import UTC, datetime, timedelta

from backend.repository import DocumentRepository


def test_legacy_documents_are_migrated_then_purged_without_deleting_usage(tmp_path):
    database_path = tmp_path / "clearledger.sqlite3"
    preview_dir = tmp_path / "previews"
    preview_dir.mkdir()
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE documents (
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
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "old.pdf", "sha", "ready", 1, "embedded_text", '{"status":"ready"}', now, now),
        )

    repository = DocumentRepository(database_path, preview_dir)
    user = repository.create_user("owner@example.com", "unused-test-hash", claim_legacy_documents=True)
    (preview_dir / "legacy.png").write_bytes(b"legacy preview")
    (preview_dir / "orphan.png").write_bytes(b"orphan preview")

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()}

    assert "user_id" in columns
    repository.record_usage(user["id"], "document_parsed", 1)
    assert repository.purge_all_documents() == 1
    assert repository.list(user["id"]) == []
    assert repository.get(user["id"], "legacy") is None
    assert repository.usage(user["id"])["documents_parsed"] == 1
    assert list(preview_dir.glob("*.png")) == []


def test_existing_account_is_migrated_as_verified(tmp_path):
    database_path = tmp_path / "clearledger.sqlite3"
    preview_dir = tmp_path / "previews"
    preview_dir.mkdir()
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("INSERT INTO users VALUES ('legacy-user', 'owner@example.com', 'hash', ?, ?)", (now, now))

    repository = DocumentRepository(database_path, preview_dir)
    user = repository.get_user("legacy-user")

    assert user["email_verified_at"] == now
    assert user["session_version"] == 0


def test_auth_tokens_are_single_use_and_reset_invalidates_sessions(tmp_path):
    repository = DocumentRepository(tmp_path / "clearledger.sqlite3", tmp_path / "previews")
    user = repository.create_user("owner@example.com", "old-hash")
    expires = datetime.now(UTC) + timedelta(minutes=30)

    assert repository.create_auth_token(user["id"], "verify_email", "verify-digest", expires) is True
    assert repository.verify_email_token("verify-digest")["email_verified_at"] is not None
    assert repository.verify_email_token("verify-digest") is None
    assert repository.create_auth_token(user["id"], "reset_password", "reset-digest", expires) is True
    reset_user = repository.reset_password_with_token("reset-digest", "new-hash")

    assert reset_user["password_hash"] == "new-hash"
    assert reset_user["session_version"] == 1
    assert repository.reset_password_with_token("reset-digest", "another-hash") is None
