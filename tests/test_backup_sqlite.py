import sqlite3

import pytest

from scripts.backup_sqlite import backup_database


def test_backup_script_creates_verified_copy_without_changing_schema(tmp_path):
    source = tmp_path / "receiptsift.sqlite3"
    destination = tmp_path / "backups" / "snapshot.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL)")
        connection.execute("INSERT INTO users (id, email) VALUES ('1', 'owner@example.com')")

    result = backup_database(source, destination)

    assert result["status"] == "ok"
    assert result["table_count"] == 1
    assert result["receipt_content_inspection_performed"] == 0
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT email FROM users").fetchone()[0] == "owner@example.com"

    with pytest.raises(FileExistsError):
        backup_database(source, destination)
