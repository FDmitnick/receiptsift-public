from backend.quality import apply_extraction_quality_gate, inspect_image_quality
from backend.sample import create_sample_pdf


def test_quality_gate_rejects_cash_as_total_evidence():
    result = {
        "status": "ready",
        "fields": {
            "merchant": {"value": "CAFE", "source": {"text": "CAFE"}},
            "date": {"value": "2026-08-21", "source": {"text": "2026-08-21"}},
            "subtotal": {"value": 10.0, "source": {"text": "Subtotal 10.00"}},
            "total": {"value": 20.0, "source": {"text": "CASH 20.00"}},
        },
        "items": [
            {"description": "Coffee", "amount": 10.0, "source": {"text": "Coffee 10.00"}},
        ],
        "warnings": [],
    }

    checked = apply_extraction_quality_gate(result)

    assert checked["status"] == "needs_review"
    assert "total_may_be_tender" in {warning["code"] for warning in checked["warnings"]}


def test_image_quality_returns_auditable_metrics():
    import pymupdf

    document = pymupdf.open(stream=create_sample_pdf(), filetype="pdf")
    try:
        image = document[0].get_pixmap().tobytes("png")
    finally:
        document.close()

    quality = inspect_image_quality(image)

    assert quality["width"] > 0
    assert quality["height"] > 0
    assert isinstance(quality["risk_flags"], list)


def test_quality_gate_accounts_for_discount_and_refund_reductions():
    result = {
        "status": "ready",
        "fields": {
            "merchant": {"value": "TEST STORE", "source": {"text": "TEST STORE"}},
            "gross_amount": {"value": 100.0, "source": {"text": "Gross 100.00"}},
            "discount": {"value": 10.0, "source": {"text": "Discount 10.00"}},
            "refund": {"value": 5.0, "source": {"text": "Refund 5.00"}},
            "subtotal": {"value": 85.0, "source": {"text": "Subtotal 85.00"}},
            "total": {"value": 85.0, "source": {"text": "Total 85.00"}},
        },
        "items": [
            {"description": "Item A", "amount": 60.0, "source": {"text": "Item A 60.00"}},
            {"description": "Item B", "amount": 40.0, "source": {"text": "Item B 40.00"}},
        ],
        "warnings": [],
    }

    checked = apply_extraction_quality_gate(result)

    assert "items_subtotal_mismatch" not in {issue["code"] for issue in checked["deterministic_checks"]}
