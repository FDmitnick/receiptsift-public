from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from typing import Any

from .document_schema import (
    AMOUNT_FIELD_NAMES,
    BILL_FIELD_NAMES,
    COMMON_FIELD_NAMES,
    INVOICE_FIELD_NAMES,
    LINE_ITEM_FIELD_NAMES,
    clean_document_result,
    detailed_document_result,
    safe_export_cell,
)

SUMMARY_FIELD_NAMES = COMMON_FIELD_NAMES + INVOICE_FIELD_NAMES + AMOUNT_FIELD_NAMES + BILL_FIELD_NAMES
SUMMARY_HEADERS = ("filename", "status", "document_type", "document_subtype", "page_count", *SUMMARY_FIELD_NAMES, "error_code")
LINE_ITEM_HEADERS = (
    "filename",
    "status",
    "document_type",
    "document_number",
    "vendor_name",
    "issue_date",
    "due_date",
    "currency",
    *LINE_ITEM_FIELD_NAMES,
)


def _document_result(document: dict[str, Any]) -> dict[str, Any]:
    result = document.get("result")
    return result if isinstance(result, dict) else {}


def _field_value(result: dict[str, Any], name: str) -> Any:
    field = (result.get("fields") or {}).get(name)
    return field.get("value") if isinstance(field, dict) else None


def _csv_bytes(headers: tuple[str, ...], rows: Iterable[Iterable[Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(tuple(safe_export_cell(value) for value in row))
    return output.getvalue().encode("utf-8-sig")


def summary_csv(documents: Iterable[dict[str, Any]]) -> bytes:
    def rows():
        for document in documents:
            result = _document_result(document)
            yield (
                document.get("filename"),
                document.get("status") or result.get("status"),
                result.get("document_type"),
                result.get("document_subtype"),
                document.get("page_count") or result.get("page_count"),
                *(_field_value(result, name) for name in SUMMARY_FIELD_NAMES),
                document.get("error_code"),
            )

    return _csv_bytes(SUMMARY_HEADERS, rows())


def line_items_csv(documents: Iterable[dict[str, Any]]) -> bytes:
    def rows():
        for document in documents:
            result = _document_result(document)
            common = (
                document.get("filename"),
                document.get("status") or result.get("status"),
                result.get("document_type"),
                _field_value(result, "document_number"),
                _field_value(result, "vendor_name"),
                _field_value(result, "issue_date"),
                _field_value(result, "due_date"),
                _field_value(result, "currency"),
            )
            items = result.get("items") if isinstance(result.get("items"), list) else []
            if not items:
                yield (*common, *(None for _ in LINE_ITEM_FIELD_NAMES))
                continue
            for item in items:
                yield (*common, *(item.get(name) for name in LINE_ITEM_FIELD_NAMES))

    return _csv_bytes(LINE_ITEM_HEADERS, rows())


def documents_json(documents: Iterable[dict[str, Any]], *, mode: str = "clean") -> bytes:
    serializer = detailed_document_result if mode == "detailed" else clean_document_result
    payload = {
        "schema_version": "1.0",
        "mode": mode,
        "documents": [
            serializer(
                _document_result(document),
                filename=document.get("filename"),
                status=document.get("status"),
            )
            for document in documents
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
