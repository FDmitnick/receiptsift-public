from __future__ import annotations

import csv
import io
import json

import pymupdf

from backend.document_schema import classify_document_type, finalize_document_result
from backend.exports import line_items_csv, summary_csv
from backend.parser import parse_pdf


def _field(value):
    return {"value": value, "confidence": 0.95, "source": None}


def _pdf(lines: list[str]) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 24), line)
    payload = document.tobytes()
    document.close()
    return payload


def test_local_invoice_uses_versioned_schema_and_invoice_reconciliation():
    result, _ = parse_pdf(
        _pdf(
            [
                "ACME SERVICES LLC",
                "INVOICE No: INV-100",
                "Date: 2026-08-01",
                "Due Date: 2026-08-31",
                "Consulting 2 x 50.00 100.00",
                "Subtotal 100.00",
                "Shipping 5.00",
                "Tax 8.00",
                "Invoice Total USD 113.00",
                "Amount Paid 13.00",
                "Balance Due 100.00",
            ]
        )
    )

    assert result["schema_version"] == "1.0"
    assert result["document_type"] == "invoice"
    assert result["fields"]["document_number"]["value"] == "INV-100"
    assert result["fields"]["due_date"]["value"] == "2026-08-31"
    assert result["fields"]["total"]["value"] == 113.0
    assert result["fields"]["balance_due"]["value"] == 100.0
    assert {check["code"]: check["matched"] for check in result["reconciliations"]} == {
        "invoice_total": True,
        "invoice_balance": True,
    }


def test_local_invoice_extracts_inline_bill_to_tax_id_and_excludes_summary_rows():
    result, _ = parse_pdf(
        _pdf(
            [
                "Summit Office Supply LLC",
                "425 Market Street, Denver, CO 80202",
                "EIN 901-000001",
                "INVOICE",
                "Invoice No: INV-2020-1001",
                "Issue Date: 2020-04-08",
                "Due Date: 2020-04-23",
                "Payment Terms: Net 15",
                "Bill To: Pioneer Retail Group",
                "1200 Broadway, New York, NY 10001",
                "Ergonomic Chair 2 x 133.29 266.58",
                "Standing Desk 3 x 184.01 552.03",
                "Subtotal USD 818.61",
                "Discount USD 0.00",
                "Shipping USD 12.75",
                "Fees USD 0.00",
                "Tax USD 59.35",
                "Invoice Total USD 890.71",
                "Amount Paid USD 0.00",
                "Balance Due USD 890.71",
            ]
        )
    )

    assert result["fields"]["vendor_tax_id"]["value"] == "EIN 901-000001"
    assert result["fields"]["bill_to_name"]["value"] == "Pioneer Retail Group"
    assert result["fields"]["customer_name"]["value"] == "Pioneer Retail Group"
    assert result["fields"]["bill_to_address"]["value"] == "1200 Broadway, New York, NY 10001"
    assert result["fields"]["payment_method"]["value"] is None
    assert [item["description"] for item in result["items"]] == ["Ergonomic Chair", "Standing Desk"]
    assert result["items"][0]["discount"] == 0.0


def test_local_bill_uses_bill_balance_formula_without_requiring_line_items():
    result, _ = parse_pdf(
        _pdf(
            [
                "NORTH CITY ELECTRIC",
                "UTILITY STATEMENT",
                "Account Number: AC-7788",
                "Previous Balance 40.00",
                "Payments 40.00",
                "Current Charges 75.00",
                "Tax 5.00",
                "Amount Due USD 80.00",
                "Due Date: 2026-09-15",
            ]
        )
    )

    assert result["document_type"] == "bill"
    assert result["fields"]["account_number"]["value"] == "AC-7788"
    assert result["fields"]["balance_due"]["value"] == 80.0
    assert result["reconciliations"][0]["code"] == "bill_balance"
    assert result["reconciliations"][0]["matched"] is True
    assert "items_missing" not in {warning["code"] for warning in result["warnings"]}


def test_receipt_style_document_with_bill_title_is_classified_as_bill():
    text = """MetroWave Wireless
BILL PAGE 1/2
Receipt No: TEL-20210001
Monthly Plan $41.49
Subtotal $343.58
TOTAL USD $367.12
Balance Due: USD $367.12"""

    assert classify_document_type(text) == "bill"


def test_hotel_receipt_with_bill_page_heading_remains_a_receipt():
    text = """Liberty Plaza Hotel
BILL PAGE 1/2
Receipt No: HOTEL-20230001
Room Charge $76.53
Tip / Gratuity $37.54
TOTAL USD $259.10"""

    assert classify_document_type(text) == "receipt"


def test_schema_preserves_legacy_aliases_and_negative_credit_items():
    result = {
        "status": "ready",
        "fields": {"merchant": _field("=UNTRUSTED"), "date": _field("2026-08-24"), "receipt_number": _field("R-1")},
        "items": [{"description": "Returned item", "quantity": 1, "unit_price": -10, "amount": -10}],
        "warnings": [],
        "pages": [],
    }
    finalize_document_result(result, text="RECEIPT")

    assert result["fields"]["vendor_name"]["value"] == "=UNTRUSTED"
    assert result["fields"]["issue_date"]["value"] == "2026-08-24"
    assert result["fields"]["document_number"]["value"] == "R-1"
    assert result["items"][0]["amount"] == -10

    document = {"filename": "return.pdf", "status": "ready", "page_count": 1, "error_code": None, "result": result}
    summary = list(csv.reader(io.StringIO(summary_csv([document]).decode("utf-8-sig"))))
    assert "vendor_name" in summary[0]
    assert summary[1][summary[0].index("vendor_name")] == "'=UNTRUSTED"
    items = list(csv.reader(io.StringIO(line_items_csv([document]).decode("utf-8-sig"))))
    assert items[1][items[0].index("amount")] == "-10"


def test_invoice_schema_keeps_bill_to_ship_to_and_customer_compatibility():
    result = {
        "status": "ready",
        "fields": {
            "bill_to_name": _field("Buyer LLC"),
            "bill_to_address": _field("1 Main St"),
            "ship_to_name": _field("Warehouse LLC"),
            "ship_to_address": _field("2 Dock Rd"),
            "original_invoice_number": _field("INV-99"),
        },
        "items": [],
        "warnings": [],
        "pages": [],
    }
    finalize_document_result(result, text="CREDIT NOTE", document_type="invoice")

    assert result["document_subtype"] == "credit_note"
    assert result["fields"]["customer_name"]["value"] == "Buyer LLC"
    assert result["fields"]["customer_address"]["value"] == "1 Main St"
    assert result["fields"]["ship_to_name"]["value"] == "Warehouse LLC"
    assert result["fields"]["original_invoice_number"]["value"] == "INV-99"


def test_credit_note_uses_signed_total_and_refund_reconciliations_only():
    result = {
        "status": "ready",
        "fields": {
            "subtotal": _field(-100.0),
            "discount": _field(0.0),
            "shipping": _field(0.0),
            "fees": _field(0.0),
            "tax": _field(-8.0),
            "total": _field(-108.0),
            "refund": _field(108.0),
            "amount_paid": _field(0.0),
            "balance_due": _field(0.0),
        },
        "items": [],
        "warnings": [],
        "pages": [],
    }
    finalize_document_result(result, text="CREDIT NOTE", document_type="invoice")

    assert {check["code"]: check["matched"] for check in result["reconciliations"]} == {
        "credit_note_total": True,
        "credit_note_refund": True,
    }
    assert "invoice_balance" not in {check["code"] for check in result["reconciliations"]}


def test_local_credit_note_extracts_original_invoice_and_signed_amounts():
    result, _ = parse_pdf(
        _pdf(
            [
                "SUMMIT OFFICE SUPPLY LLC",
                "CREDIT NOTE",
                "No. CN-2026-3021",
                "Original Invoice: INV-2026-2021",
                "Subtotal USD -100.00",
                "Tax USD -8.00",
                "Total credit USD -108.00",
                "Refund amount USD 108.00",
                "Balance due USD 0.00",
            ]
        )
    )

    assert result["document_type"] == "invoice"
    assert result["document_subtype"] == "credit_note"
    assert result["fields"]["document_number"]["value"] == "CN-2026-3021"
    assert result["fields"]["original_invoice_number"]["value"] == "INV-2026-2021"
    assert result["fields"]["total"]["value"] == -108.0
    assert result["fields"]["refund"]["value"] == 108.0


def test_clean_batch_json_omits_evidence_and_preview():
    # The endpoint behavior is covered in API tests; this assertion documents the JSON contract itself.
    result = {
        "schema_version": "1.0",
        "document_type": "receipt",
        "status": "ready",
        "preview_data_url": "data:image/png;base64,secret",
        "fields": {"merchant": _field("Cafe")},
        "items": [],
        "warnings": [],
        "pages": [],
    }
    finalize_document_result(result, text="RECEIPT")
    document = {"filename": "cafe.pdf", "status": "ready", "result": result}
    from backend.exports import documents_json

    payload = json.loads(documents_json([document], mode="clean"))
    assert payload["schema_version"] == "1.0"
    assert payload["documents"][0]["fields"]["vendor_name"] == "Cafe"
    assert "preview_data_url" not in payload["documents"][0]
