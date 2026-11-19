from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

SCHEMA_VERSION = "1.0"
DOCUMENT_TYPES = {"receipt", "invoice", "bill"}

# The three legacy names remain in API responses so existing clients keep working.
# New integrations should prefer vendor_name, issue_date, and document_number.
FIELD_ALIASES = {
    "vendor_name": "merchant",
    "issue_date": "date",
    "document_number": "receipt_number",
}

COMMON_FIELD_NAMES = (
    "vendor_name",
    "vendor_address",
    "vendor_tax_id",
    "customer_name",
    "customer_address",
    "document_number",
    "issue_date",
    "due_date",
    "currency",
    "account_number",
    "purchase_order_number",
    "payment_terms",
    "card_last4",
    "payment_method",
)

INVOICE_FIELD_NAMES = (
    "bill_to_name",
    "bill_to_address",
    "ship_to_name",
    "ship_to_address",
    "original_invoice_number",
)

AMOUNT_FIELD_NAMES = (
    "gross_amount",
    "discount",
    "refund",
    "subtotal",
    "shipping",
    "fees",
    "tax",
    "tip",
    "total",
    "amount_paid",
    "balance_due",
    "previous_balance",
    "payments",
    "credits",
    "adjustments",
    "current_charges",
    "late_fee",
    "minimum_due",
)

BILL_FIELD_NAMES = (
    "service_period_start",
    "service_period_end",
    "autopay_date",
)

LEGACY_FIELD_NAMES = ("merchant", "date", "receipt_number")
ALL_FIELD_NAMES = COMMON_FIELD_NAMES + INVOICE_FIELD_NAMES + AMOUNT_FIELD_NAMES + BILL_FIELD_NAMES + LEGACY_FIELD_NAMES

LINE_ITEM_FIELD_NAMES = (
    "description",
    "sku",
    "quantity",
    "unit",
    "unit_price",
    "discount",
    "tax_rate",
    "tax_amount",
    "amount",
    "line_total",
)


def empty_field() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0, "source": None}


def _field_value(fields: dict[str, Any], name: str) -> Any:
    field = fields.get(name)
    return field.get("value") if isinstance(field, dict) else None


def _clone_field(field: Any) -> dict[str, Any]:
    if not isinstance(field, dict):
        return empty_field()
    return {
        "value": field.get("value"),
        "confidence": field.get("confidence", 0.0),
        "source": copy.deepcopy(field.get("source")),
        **({"corrected": True} if field.get("corrected") else {}),
    }


def normalize_document_type(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold().replace("statement", "bill")
    return normalized if normalized in DOCUMENT_TYPES else None


def classify_document_type(text: str, hints: Iterable[Any] = ()) -> str:
    votes = Counter(filter(None, (normalize_document_type(hint) for hint in hints)))
    if votes:
        top, count = votes.most_common(1)[0]
        if count >= 2 or sum(votes.values()) == 1:
            return top

    lowered = str(text or "").casefold()
    if any(anchor in lowered for anchor in ("credit note", "credit memo", "credit memorandum")):
        return "invoice"
    scores = {"receipt": 0, "invoice": 0, "bill": 0}
    weighted_anchors = {
        "receipt": {
            "receipt": 4,
            "cashier": 2,
            "change due": 2,
            "tender": 2,
            "thank you": 1,
        },
        "invoice": {
            "invoice": 5,
            "bill to": 3,
            "ship to": 2,
            "purchase order": 3,
            "payment terms": 3,
            "po number": 2,
        },
        "bill": {
            "statement": 4,
            "service period": 4,
            "previous balance": 4,
            "current charges": 4,
            "minimum due": 4,
            "autopay": 3,
            "account number": 2,
            "balance due": 2,
            "amount due": 1,
        },
    }
    for document_type, anchors in weighted_anchors.items():
        scores[document_type] = sum(weight for anchor, weight in anchors.items() if anchor in lowered)
    has_bill_title = re.search(r"(?im)^\s*bill(?:\s+page\s+\d+(?:/\d+)?)?\s*$", str(text or ""))
    bill_domain_anchors = (
        "utilities",
        "electric service",
        "water service",
        "wastewater",
        "energy adjustment",
        "monthly plan",
        "device payment",
        "data add-on",
        "wireless",
        "communications",
        "fiber",
    )
    if has_bill_title and any(anchor in lowered for anchor in bill_domain_anchors):
        scores["bill"] += 6
    winner = max(scores, key=scores.get)
    return winner if scores[winner] > 0 else "receipt"


def canonicalize_fields(fields: Any, document_type: str = "receipt") -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    source = fields if isinstance(fields, dict) else {}
    for name in ALL_FIELD_NAMES:
        normalized[name] = _clone_field(source.get(name))

    for canonical, legacy in FIELD_ALIASES.items():
        canonical_field = normalized[canonical]
        legacy_field = normalized[legacy]
        if canonical_field["value"] is None and legacy_field["value"] is not None:
            normalized[canonical] = _clone_field(legacy_field)
        elif legacy_field["value"] is None and canonical_field["value"] is not None:
            normalized[legacy] = _clone_field(canonical_field)

    for customer, bill_to in (("customer_name", "bill_to_name"), ("customer_address", "bill_to_address")):
        if normalized[customer]["value"] is None and normalized[bill_to]["value"] is not None:
            normalized[customer] = _clone_field(normalized[bill_to])
        elif normalized[bill_to]["value"] is None and normalized[customer]["value"] is not None:
            normalized[bill_to] = _clone_field(normalized[customer])

    # Invoice and bill totals are payable balances unless a separate balance is printed.
    if document_type in {"invoice", "bill"}:
        if normalized["balance_due"]["value"] is None and normalized["total"]["value"] is not None:
            normalized["balance_due"] = _clone_field(normalized["total"])
        elif normalized["total"]["value"] is None and normalized["balance_due"]["value"] is not None:
            normalized["total"] = _clone_field(normalized["balance_due"])
    return normalized


def _number(fields: dict[str, Any], name: str) -> float | None:
    value = _field_value(fields, name)
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check(code: str, formula: str, actual: float | None, expected: float | None) -> dict[str, Any]:
    difference = None if actual is None or expected is None else round(actual - expected, 2)
    return {
        "code": code,
        "formula": formula,
        "matched": None if difference is None else abs(difference) <= 0.02,
        "difference": difference,
    }


def build_reconciliations(
    fields: dict[str, Any], document_type: str, document_subtype: str | None = None
) -> list[dict[str, Any]]:
    subtotal = _number(fields, "subtotal")
    tax = _number(fields, "tax") or 0.0
    total = _number(fields, "total")
    checks: list[dict[str, Any]] = []

    if document_type == "invoice":
        expected_total = None
        if subtotal is not None:
            expected_total = (
                subtotal
                - (_number(fields, "discount") or 0.0)
                + (_number(fields, "shipping") or 0.0)
                + (_number(fields, "fees") or 0.0)
                + tax
            )
        is_credit_note = document_subtype == "credit_note"
        checks.append(
            _check(
                "credit_note_total" if is_credit_note else "invoice_total",
                (
                    "negative subtotal + negative tax = total credit"
                    if is_credit_note
                    else "subtotal - discount + shipping + fees + tax = total"
                ),
                total,
                expected_total,
            )
        )
        if is_credit_note:
            refund = _number(fields, "refund")
            if refund is not None and total is not None:
                checks.append(
                    _check(
                        "credit_note_refund",
                        "absolute(total credit) = refund",
                        refund,
                        abs(total),
                    )
                )
            return checks
        balance_due = _number(fields, "balance_due")
        amount_paid = _number(fields, "amount_paid")
        if balance_due is not None and total is not None and amount_paid is not None:
            checks.append(
                _check(
                    "invoice_balance",
                    "total - amount_paid = balance_due",
                    balance_due,
                    total - amount_paid,
                )
            )
    elif document_type == "bill":
        previous_balance = _number(fields, "previous_balance")
        current_charges = _number(fields, "current_charges")
        balance_due = _number(fields, "balance_due") or total
        if previous_balance is not None or current_charges is not None:
            expected_due = (
                (previous_balance or 0.0)
                - (_number(fields, "payments") or 0.0)
                - (_number(fields, "credits") or 0.0)
                + (current_charges or 0.0)
                + (_number(fields, "adjustments") or 0.0)
                + (_number(fields, "fees") or 0.0)
                + (_number(fields, "late_fee") or 0.0)
                + tax
            )
            checks.append(
                _check(
                    "bill_balance",
                    "previous_balance - payments - credits + current_charges + adjustments + fees + late_fee + tax = balance_due",
                    balance_due,
                    expected_due,
                )
            )
    else:
        tip = _number(fields, "tip") or 0.0
        checks.append(_check("receipt_total", "subtotal + tax + tip = total", total, None if subtotal is None else subtotal + tax + tip))

    return checks or [_check("amounts_unavailable", "insufficient values", None, None)]


def _subtype(text: str, document_type: str) -> str | None:
    lowered = str(text or "").casefold()
    if document_type == "invoice" and any(
        anchor in lowered for anchor in ("credit note", "credit memo", "credit memorandum")
    ):
        return "credit_note"
    if document_type == "bill":
        for anchor, subtype in (
            ("utility", "utility"),
            ("electric", "utility"),
            ("water service", "utility"),
            ("medical", "medical"),
            ("credit card", "credit_card_statement"),
            ("rent", "rent"),
        ):
            if anchor in lowered:
                return subtype
    return None


def finalize_document_result(
    result: dict[str, Any],
    *,
    text: str = "",
    document_type: Any = None,
    document_subtype: Any = None,
) -> dict[str, Any]:
    page_hints = [page.get("document_type") for page in result.get("pages", []) if isinstance(page, dict)]
    resolved_type = normalize_document_type(document_type or result.get("document_type"))
    resolved_type = resolved_type or classify_document_type(text, page_hints)
    result["schema_version"] = SCHEMA_VERSION
    result["document_type"] = resolved_type
    result["document_subtype"] = str(document_subtype or result.get("document_subtype") or "").strip() or _subtype(text, resolved_type)
    result["fields"] = canonicalize_fields(result.get("fields"), resolved_type)

    normalized_items: list[dict[str, Any]] = []
    for item in result.get("items", []) if isinstance(result.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        normalized = {name: item.get(name) for name in LINE_ITEM_FIELD_NAMES}
        normalized["description"] = str(normalized.get("description") or "").strip()
        normalized["quantity"] = normalized.get("quantity") if normalized.get("quantity") is not None else 1.0
        normalized["confidence"] = item.get("confidence", 0.0)
        normalized["source"] = copy.deepcopy(item.get("source"))
        if item.get("corrected"):
            normalized["corrected"] = True
        if normalized["description"]:
            normalized_items.append(normalized)
    result["items"] = normalized_items

    checks = build_reconciliations(result["fields"], resolved_type, result["document_subtype"])
    result["reconciliations"] = checks
    primary = next((check for check in checks if check["matched"] is not None), checks[0])
    result["reconciliation"] = {"matched": primary["matched"], "difference": primary["difference"]}

    mismatch_codes = {
        "totals_mismatch",
        "invoice_total_mismatch",
        "invoice_balance_mismatch",
        "credit_note_total_mismatch",
        "credit_note_refund_mismatch",
        "bill_balance_mismatch",
    }
    result["warnings"] = [
        warning for warning in result.get("warnings", []) if isinstance(warning, dict) and warning.get("code") not in mismatch_codes
    ]
    messages = {
        "receipt_total": ("totals_mismatch", "Subtotal plus tax and tip does not match the total."),
        "invoice_total": ("invoice_total_mismatch", "Invoice subtotal, adjustments, tax, and total do not reconcile."),
        "invoice_balance": ("invoice_balance_mismatch", "Invoice total, amount paid, and balance due do not reconcile."),
        "credit_note_total": ("credit_note_total_mismatch", "Credit note subtotal, adjustments, tax, and total credit do not reconcile."),
        "credit_note_refund": ("credit_note_refund_mismatch", "Credit note total does not match the refund amount."),
        "bill_balance": ("bill_balance_mismatch", "Bill balance components do not reconcile with the amount due."),
    }
    existing_codes = {warning.get("code") for warning in result["warnings"]}
    for check in checks:
        if check["matched"] is False and check["code"] in messages:
            code, message = messages[check["code"]]
            if code not in existing_codes:
                result["warnings"].append({"code": code, "message": message})
                existing_codes.add(code)
    if result["warnings"]:
        result["status"] = "needs_review"
    return result


def clean_document_result(result: dict[str, Any], *, filename: str | None = None, status: str | None = None) -> dict[str, Any]:
    document_type = normalize_document_type(result.get("document_type")) or "receipt"
    fields = canonicalize_fields(result.get("fields"), document_type)
    clean_fields = {
        name: _field_value(fields, name)
        for name in COMMON_FIELD_NAMES + INVOICE_FIELD_NAMES + AMOUNT_FIELD_NAMES + BILL_FIELD_NAMES
    }
    return {
        "schema_version": result.get("schema_version") or SCHEMA_VERSION,
        "document_type": document_type,
        "document_subtype": result.get("document_subtype"),
        "filename": filename or result.get("filename"),
        "status": status or result.get("status"),
        "fields": clean_fields,
        "line_items": [
            {name: item.get(name) for name in LINE_ITEM_FIELD_NAMES}
            for item in result.get("items", [])
            if isinstance(item, dict)
        ],
        "reconciliations": copy.deepcopy(result.get("reconciliations") or []),
    }


def detailed_document_result(result: dict[str, Any], *, filename: str | None = None, status: str | None = None) -> dict[str, Any]:
    detailed = copy.deepcopy(result)
    detailed.pop("preview_data_url", None)
    detailed["schema_version"] = detailed.get("schema_version") or SCHEMA_VERSION
    if filename is not None:
        detailed["filename"] = filename
    if status is not None:
        detailed["status"] = status
    return detailed


def safe_export_cell(value: Any) -> Any:
    if isinstance(value, str) and re.match(r"^[=+\-@]", value):
        return f"'{value}"
    return value
