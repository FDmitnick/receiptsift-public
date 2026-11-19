from scripts.verify_batch_50 import run_verification


def test_fifty_synthetic_receipts_complete_without_worker_failures():
    result = run_verification(50)

    assert result["documents"] == 50
    assert result["processed"] == 50
    assert result["failed"] == 0
    assert result["ready"] + result["needs_review"] == 50
