from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def backup_database(source: Path, destination: Path) -> dict[str, str | int]:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Database not found: {source}")
    if source == destination:
        raise ValueError("Backup destination must differ from the live database.")
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(source) as live, sqlite3.connect(destination) as backup:
            live.backup(backup)
        with sqlite3.connect(destination) as verification:
            result = verification.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError("SQLite quick_check did not return ok.")
            table_count = int(
                verification.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone()[0]
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {
        "status": "ok",
        "source": str(source),
        "destination": str(destination),
        "bytes": destination.stat().st_size,
        "table_count": table_count,
        "receipt_content_inspection_performed": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and verify a consistent ReceiptSift SQLite backup.")
    parser.add_argument("--source", type=Path, default=Path("data/receiptsift.sqlite3"))
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    destination = args.destination or (
        args.source.parent
        / "backups"
        / f"receiptsift-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    )
    print(json.dumps(backup_database(args.source, destination), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
