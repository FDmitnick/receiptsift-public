from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

from backend.tax_workbook import schedule_c_workbook


def test_schedule_c_workbook_contains_reviewable_transactions_and_formulas():
    workbook = schedule_c_workbook(
        [
            {
                "id": "document-1",
                "filename": '=HYPERLINK("https://example.invalid","receipt.pdf")',
                "sha256": "abc123",
                "status": "ready",
                "source_available": True,
                "result": {
                    "status": "ready",
                    "document_type": "receipt",
                    "fields": {
                        "vendor_name": {"value": "Cedar & Finch"},
                        "issue_date": {"value": "2026-08-20"},
                        "currency": {"value": "USD"},
                        "subtotal": {"value": 25.0},
                        "tax": {"value": 2.06},
                        "total": {"value": 27.06},
                    },
                    "items": [{"description": "Client lunch", "quantity": 1, "amount": 25.0}],
                    "warnings": [],
                },
            }
        ],
        batch_name="August business documents",
    )

    assert workbook.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        for name in archive.namelist():
            if name.endswith(".xml"):
                ElementTree.fromstring(archive.read(name))

        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        instructions_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        transactions_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        summary_xml = archive.read("xl/worksheets/sheet3.xml").decode("utf-8")

    assert all(
        name in workbook_xml for name in ("Instructions", "Transactions", "Schedule C Summary", "Exceptions", "Line Items", "Categories")
    )
    assert 'activeTab="1"' in workbook_xml
    assert 'state="hidden"' in workbook_xml
    assert 't="inlineStr"' in transactions_xml
    assert "HYPERLINK" in transactions_xml
    assert "<f>HYPERLINK" not in transactions_xml
    assert "P6*Q6*R6" in transactions_xml
    assert "SUMIF(" in summary_xml
    assert "COUNTIFS(" in summary_xml
    assert "not a tax return" in instructions_xml


def test_schedule_c_workbook_handles_empty_batch():
    workbook = schedule_c_workbook([], batch_name="Empty batch")

    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        instructions_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        transactions_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert 'sqref="O6:O6"' in transactions_xml
    assert "Empty batch" in instructions_xml
