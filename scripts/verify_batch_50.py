from __future__ import annotations

import gc
import json
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

from backend.batch_repository import BatchRepository
from backend.batch_worker import BatchWorker
from backend.parser import parse_pdf
from backend.repository import DocumentRepository


def synthetic_receipt(index: int) -> bytes:
    import pymupdf

    subtotal = 20 + index / 10
    tax = round(subtotal * 0.0825, 2)
    total = round(subtotal + tax, 2)
    lines = [
        f"NORTHSTAR MARKET #{index + 1:03d}",
        "101 Main Street, Austin, TX",
        f"Receipt No: NS-{20260800 + index + 1}",
        f"Date: 2026-08-{(index % 28) + 1:02d} 12:30",
        f"Office supplies 1 x {subtotal:.2f} {subtotal:.2f}",
        f"Subtotal {subtotal:.2f}",
        f"Tax {tax:.2f}",
        f"Total USD {total:.2f}",
        "Payment: VISA",
    ]
    document = pymupdf.open()
    page = document.new_page(width=340, height=500)
    y = 48
    for line_index, line in enumerate(lines):
        page.insert_text((28, y), line, fontsize=12 if line_index == 0 else 10, fontname="cour")
        y += 34 if line_index == 0 else 30
    payload = document.tobytes(deflate=True)
    document.close()
    return payload


def run_verification(count: int = 50) -> dict[str, int | str]:
    with tempfile.TemporaryDirectory(prefix="receiptsift-batch-") as temporary:
        root = Path(temporary)
        database_path = root / "receiptsift.sqlite3"
        accounts = DocumentRepository(database_path, root / "previews")
        user = accounts.create_user("batch-verification@example.com", "test-hash")
        batches = BatchRepository(
            database_path,
            root / "private-objects",
            Fernet.generate_key().decode("ascii"),
        )
        batch = batches.create_batch(user["id"], f"Synthetic {count} receipt verification")
        for index in range(count):
            batches.add_document(
                user["id"],
                batch["id"],
                f"northstar-{index + 1:03d}.pdf",
                synthetic_receipt(index),
            )
        assert batches.start_batch(user["id"], batch["id"]) == count

        def process(_user_id: str, payload: bytes, _filename: str, _progress):
            result, _preview = parse_pdf(payload, max_pages=30)
            return result

        worker = BatchWorker(batches, process, poll_seconds=0.01)
        processed = 0
        while worker.process_one():
            processed += 1
        summary = batches.get_batch(user["id"], batch["id"])
        assert summary is not None
        assert processed == count
        assert summary["document_count"] == count
        assert summary["queued_count"] == 0
        assert summary["processing_count"] == 0
        assert summary["failed_count"] == 0
        assert summary["ready_count"] + summary["review_count"] == count
        result = {
            "batch_id": batch["id"],
            "documents": summary["document_count"],
            "ready": summary["ready_count"],
            "needs_review": summary["review_count"],
            "failed": summary["failed_count"],
            "processed": processed,
        }
        # sqlite's context manager commits but does not close the connection.
        # Release any final cursor/connection cycles before Windows removes the
        # temporary database, otherwise cleanup can fail with WinError 32.
        del worker, batches, accounts
        gc.collect()
        return result


def main() -> None:
    print(json.dumps(run_verification(), indent=2))


if __name__ == "__main__":
    main()
