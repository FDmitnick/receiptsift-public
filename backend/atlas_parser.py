from __future__ import annotations

import base64
import json
from collections.abc import Callable
from statistics import mean
from typing import Any

import httpx

from .document_schema import ALL_FIELD_NAMES, AMOUNT_FIELD_NAMES, finalize_document_result
from .parser import PdfParseError, validate_pdf_security
from .provider import post_json_with_retry
from .quality import apply_extraction_quality_gate

FIELD_NAMES = ALL_FIELD_NAMES

EXTRACTION_PROMPT = """You extract structured financial data from one page of a receipt, invoice, or bill.
Most production documents are from the United States, but identify the actual language and currency shown.
Return one JSON object only. Never guess text or amounts that are not visible.

Schema:
{
  "document_type": "receipt"|"invoice"|"bill",
  "document_subtype": string|null,
  "vendor_name": {"value": string|null, "confidence": number, "evidence": string|null},
  "vendor_address": {"value": string|null, "confidence": number, "evidence": string|null},
  "vendor_tax_id": {"value": string|null, "confidence": number, "evidence": string|null},
  "customer_name": {"value": string|null, "confidence": number, "evidence": string|null},
  "customer_address": {"value": string|null, "confidence": number, "evidence": string|null},
  "bill_to_name": {"value": string|null, "confidence": number, "evidence": string|null},
  "bill_to_address": {"value": string|null, "confidence": number, "evidence": string|null},
  "ship_to_name": {"value": string|null, "confidence": number, "evidence": string|null},
  "ship_to_address": {"value": string|null, "confidence": number, "evidence": string|null},
  "document_number": {"value": string|null, "confidence": number, "evidence": string|null},
  "original_invoice_number": {"value": string|null, "confidence": number, "evidence": string|null},
  "issue_date": {"value": "YYYY-MM-DD"|null, "confidence": number, "evidence": string|null},
  "due_date": {"value": "YYYY-MM-DD"|null, "confidence": number, "evidence": string|null},
  "currency": {"value": "USD"|other ISO-4217 code|null, "confidence": number, "evidence": string|null},
  "account_number": {"value": string|null, "confidence": number, "evidence": string|null},
  "purchase_order_number": {"value": string|null, "confidence": number, "evidence": string|null},
  "payment_terms": {"value": string|null, "confidence": number, "evidence": string|null},
  "service_period_start": {"value": "YYYY-MM-DD"|null, "confidence": number, "evidence": string|null},
  "service_period_end": {"value": "YYYY-MM-DD"|null, "confidence": number, "evidence": string|null},
  "autopay_date": {"value": "YYYY-MM-DD"|null, "confidence": number, "evidence": string|null},
  "card_last4": {"value": string|null, "confidence": number, "evidence": string|null},
  "gross_amount": {"value": number|null, "confidence": number, "evidence": string|null},
  "discount": {"value": number|null, "confidence": number, "evidence": string|null},
  "refund": {"value": number|null, "confidence": number, "evidence": string|null},
  "subtotal": {"value": number|null, "confidence": number, "evidence": string|null},
  "shipping": {"value": number|null, "confidence": number, "evidence": string|null},
  "fees": {"value": number|null, "confidence": number, "evidence": string|null},
  "tax": {"value": number|null, "confidence": number, "evidence": string|null},
  "tip": {"value": number|null, "confidence": number, "evidence": string|null},
  "total": {"value": number|null, "confidence": number, "evidence": string|null},
  "amount_paid": {"value": number|null, "confidence": number, "evidence": string|null},
  "balance_due": {"value": number|null, "confidence": number, "evidence": string|null},
  "previous_balance": {"value": number|null, "confidence": number, "evidence": string|null},
  "payments": {"value": number|null, "confidence": number, "evidence": string|null},
  "credits": {"value": number|null, "confidence": number, "evidence": string|null},
  "adjustments": {"value": number|null, "confidence": number, "evidence": string|null},
  "current_charges": {"value": number|null, "confidence": number, "evidence": string|null},
  "late_fee": {"value": number|null, "confidence": number, "evidence": string|null},
  "minimum_due": {"value": number|null, "confidence": number, "evidence": string|null},
  "payment_method": {"value": string|null, "confidence": number, "evidence": string|null},
  "items": [
    {"description": string, "sku": string|null, "quantity": number, "unit": string|null,
     "unit_price": number|null, "discount": number|null, "tax_rate": number|null,
     "tax_amount": number|null, "amount": number, "line_total": number|null,
     "confidence": number, "evidence": string|null}
  ],
  "raw_text": string
}

Rules:
- Confidence must be between 0 and 1 and reflect legibility, not optimism.
- Monetary values are JSON numbers without currency symbols.
- Interpret comma and dot separators using the receipt's locale and arithmetic. For example, 53,000 or 53.000
  on an IDR receipt usually means 53000, not 53.
- Never assume USD when no currency evidence is visible.
- Classify invoices only when the document presents itself as an invoice; classify recurring or statement-style amounts due as bills.
- vendor_name is the issuer, supplier, merchant, or biller. customer_name is the billed party when printed.
- Keep Bill To and Ship To separate. Copy Bill To into customer_name/customer_address for compatibility.
- For a credit note or credit memo, set document_type to invoice, document_subtype to credit_note, and capture the original invoice number.
- document_number is the receipt, invoice, bill, or statement number. Do not put an account number there.
- payment_method is the tender type or card brand only (for example VISA); put the final four card digits in card_last4.
- gross_amount is the sum before discounts and refunds. discount and refund are positive reduction amounts when separately printed.
- Include purchased or billed line items, not subtotal, tax, tips, tender, change, or totals.
- On statements, include explicitly labeled charge or balance components that make up the displayed gross amount.
- A returned purchased item may remain negative when it is printed as a negative line item; do not also duplicate it in refund.
- Use null for an absent tax; do not silently convert absence to zero.
- Put a printed gratuity or tip in the tip field, never in line items or tax.
- On bills and statements, AMOUNT DUE or BALANCE DUE is the total even when the word TOTAL is absent.
- Do not label AMOUNT DUE as subtotal. Prefer the final amount due when the same bill amount appears more than once.
- For invoices set balance_due separately when amount_paid is printed. For bills capture the prior balance, payments, credits,
  current charges, adjustments, fees, late fees, tax, and minimum due only when explicitly shown.
- For invoice line items preserve SKU, unit, quantity, unit price, line discount, tax rate as a decimal fraction,
  tax amount, amount before line tax, and line total when shown.
- raw_text is a compact transcription in reading order and may be empty when unreadable.
"""


class AtlasParseError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(str(value).replace(",", "").replace("$", "").strip()), 2)
    except (TypeError, ValueError):
        return None


def _confidence(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 3)
    except (TypeError, ValueError):
        return 0.0


def _json_object(content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    if not isinstance(content, str):
        raise AtlasParseError("Atlas Cloud returned an unsupported response format.")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise AtlasParseError("Atlas Cloud did not return a JSON object.")
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as error:
        raise AtlasParseError("Atlas Cloud returned invalid JSON.") from error
    if not isinstance(parsed, dict):
        raise AtlasParseError("Atlas Cloud response is not a JSON object.")
    return parsed


def _call_model(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    image_bytes: bytes,
) -> dict[str, Any]:
    image_data = base64.b64encode(image_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-AtlasCloud-Request-Retention-Hours": "0",
        }
        try:
            response = post_json_with_retry(
                client,
                f"{base_url}/chat/completions",
                headers=headers,
                payload=payload,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 400:
                raise
            compatibility_payload = {key: value for key, value in payload.items() if key != "response_format"}
            response = post_json_with_retry(
                client,
                f"{base_url}/chat/completions",
                headers=headers,
                payload=compatibility_payload,
            )
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as error:
        raise AtlasParseError(f"Atlas Cloud request failed with HTTP {error.response.status_code}.") from error
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise AtlasParseError("Atlas Cloud request failed before a valid response was received.") from error
    parsed = _json_object(content)
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    parsed["__receiptsift_meta"] = {
        "request_id": body.get("id"),
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
    }
    return parsed


def _source(page_number: int, evidence: Any) -> dict[str, Any] | None:
    if evidence is None:
        return None
    text = str(evidence).strip()
    return {"page": page_number, "bbox": None, "text": text} if text else None


def _normalize_page(payload: dict[str, Any], page_number: int, model: str) -> dict[str, Any]:
    meta = payload.get("__receiptsift_meta") if isinstance(payload.get("__receiptsift_meta"), dict) else {}
    usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
    fields: dict[str, dict[str, Any]] = {}
    for name in FIELD_NAMES:
        raw = payload.get(name) if isinstance(payload.get(name), dict) else {}
        value = raw.get("value")
        if name in AMOUNT_FIELD_NAMES:
            value = _number(value)
        elif value is not None:
            value = str(value).strip() or None
        if name == "currency" and value is not None:
            value = str(value).upper()[:3]
        fields[name] = {
            "value": value,
            "confidence": _confidence(raw.get("confidence")) if value is not None else 0.0,
            "source": _source(page_number, raw.get("evidence")),
        }

    items: list[dict[str, Any]] = []
    raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for raw_item in raw_items[:500]:
        if not isinstance(raw_item, dict):
            continue
        description = str(raw_item.get("description", "")).strip()
        amount = _number(raw_item.get("amount"))
        if not description or amount is None:
            continue
        quantity = _number(raw_item.get("quantity"))
        items.append(
            {
                "description": description[:500],
                "sku": str(raw_item.get("sku") or "").strip()[:128] or None,
                "quantity": quantity if quantity is not None else 1.0,
                "unit": str(raw_item.get("unit") or "").strip()[:64] or None,
                "unit_price": _number(raw_item.get("unit_price")),
                "discount": _number(raw_item.get("discount")),
                "tax_rate": _number(raw_item.get("tax_rate")),
                "tax_amount": _number(raw_item.get("tax_amount")),
                "amount": amount,
                "line_total": _number(raw_item.get("line_total")),
                "confidence": _confidence(raw_item.get("confidence")),
                "source": _source(page_number, raw_item.get("evidence")),
            }
        )
    return {
        "page": page_number,
        "model": model,
        "document_type": payload.get("document_type"),
        "document_subtype": payload.get("document_subtype"),
        "fields": fields,
        "items": items,
        "text": str(payload.get("raw_text", "")).strip(),
        "provider_request_id": meta.get("request_id"),
        "usage": {
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
    }


def _assemble(pages: list[dict[str, Any]], page_count: int, model: str) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}
    for name in FIELD_NAMES:
        candidates = [page["fields"][name] for page in pages if page["fields"][name]["value"] is not None]
        fields[name] = max(candidates, key=lambda item: item["confidence"]) if candidates else {
            "value": None,
            "confidence": 0.0,
            "source": None,
        }

    items: list[dict[str, Any]] = []
    seen: set[tuple[int, str, float]] = set()
    for page in pages:
        for item in page["items"]:
            key = (page["page"], item["description"].casefold(), item["amount"])
            if key not in seen:
                seen.add(key)
                items.append(item)

    provider_usage = {
        "input_tokens": sum(page["usage"]["input_tokens"] for page in pages),
        "output_tokens": sum(page["usage"]["output_tokens"] for page in pages),
        "total_tokens": sum(page["usage"]["total_tokens"] for page in pages),
        "calls": len(pages),
    }
    result = {
        "status": "ready",
        "page_count": page_count,
        "extraction_method": "atlas_qwen3_vl",
        "extraction_model": model,
        "overall_confidence": 0.0,
        "fields": fields,
        "items": items,
        "warnings": [],
        "provider_usage": provider_usage,
        "pages": [
            {
                "page": page["page"],
                "text": page["text"],
                "method": "atlas_qwen3_vl",
                "model": page["model"],
                "provider_request_id": page["provider_request_id"],
                "document_type": page.get("document_type"),
            }
            for page in pages
        ],
    }
    text = "\n".join(page["text"] for page in pages)
    subtype = next((page.get("document_subtype") for page in pages if page.get("document_subtype")), None)
    finalize_document_result(result, text=text, document_subtype=subtype)
    fields = result["fields"]
    if result["document_type"] in {"receipt", "invoice"}:
        gross_amount = fields["gross_amount"]["value"]
        if gross_amount is None and items:
            gross_amount = round(sum(item["amount"] for item in items), 2)
            fields["gross_amount"] = {"value": gross_amount, "confidence": 0.65, "source": None}
        if fields["subtotal"]["value"] is None and gross_amount is not None:
            subtotal = round(gross_amount - (fields["discount"]["value"] or 0.0) - (fields["refund"]["value"] or 0.0), 2)
            fields["subtotal"] = {"value": subtotal, "confidence": 0.65, "source": None}
    finalize_document_result(result, text=text, document_subtype=subtype)

    warnings = result["warnings"]
    if result["fields"]["vendor_name"]["value"] is None:
        warnings.append({"code": "merchant_missing", "message": "Vendor, merchant, or biller could not be identified."})
    if result["fields"]["total"]["value"] is None:
        warnings.append({"code": "total_missing", "message": "Total or amount due could not be identified."})
    if not items and result["document_type"] in {"receipt", "invoice"}:
        warnings.append({"code": "items_missing", "message": "No line items were identified."})

    confidences = [field["confidence"] for field in result["fields"].values() if field["value"] is not None]
    confidences.extend(item["confidence"] for item in items)
    result["overall_confidence"] = round(mean(confidences), 3) if confidences else 0.0
    result["status"] = "needs_review" if warnings or result["overall_confidence"] < 0.85 else "ready"
    return result


def _fallback_reasons(result: dict[str, Any], min_confidence: float) -> list[str]:
    warning_codes = {warning.get("code") for warning in result.get("warnings", [])}
    reasons = sorted(str(code) for code in warning_codes if code)
    if result.get("overall_confidence", 0.0) < min_confidence:
        reasons.append("low_confidence")
    return reasons


def _with_attempts(
    selected: dict[str, Any],
    attempts: list[tuple[str, dict[str, Any] | None, str | None]],
    *,
    fallback_reasons: list[str],
) -> dict[str, Any]:
    summaries = []
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0}
    for model, result, error in attempts:
        attempt_usage = result.get("provider_usage", {}) if result else {}
        for key in usage:
            usage[key] += int(attempt_usage.get(key) or 0)
        summaries.append(
            {
                "model": model,
                "status": result.get("status") if result else "error",
                "confidence": result.get("overall_confidence") if result else None,
                "warnings": [warning.get("code") for warning in result.get("warnings", [])] if result else [],
                "usage": attempt_usage,
                "error": error,
            }
        )
    selected["provider_usage"] = usage
    selected["model_attempts"] = summaries
    selected["quality_gate"] = {
        "fallback_triggered": len(attempts) > 1,
        "fallback_reasons": fallback_reasons,
        "decision": "accept" if not fallback_reasons else "verify",
        "selected_model": selected.get("extraction_model"),
    }
    return selected


def parse_pdf_with_atlas(
    pdf_bytes: bytes,
    *,
    api_key: str,
    base_url: str,
    primary_model: str,
    fallback_model: str,
    max_pages: int,
    timeout_seconds: float = 90,
    min_confidence: float = 0.85,
    render_scale: float = 2.0,
    max_render_dimension: int = 3000,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
    call_model: Callable[[httpx.Client, str, str, str, bytes], dict[str, Any]] = _call_model,
) -> tuple[dict[str, Any], bytes | None]:
    if not api_key:
        raise AtlasParseError("Atlas Cloud API key is not configured.")
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("PyMuPDF is required. Install the packages in requirements.txt.") from error

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise PdfParseError("invalid_pdf", "The uploaded file is not a readable PDF.") from error

    try:
        if document.needs_pass:
            raise PdfParseError("encrypted_pdf", "Password-protected PDFs are not supported.")
        if document.page_count < 1:
            raise PdfParseError("empty_pdf", "The PDF does not contain any pages.")
        if document.page_count > max_pages:
            raise PdfParseError("too_many_pages", f"The PDF has {document.page_count} pages; the limit is {max_pages}.")
        validate_pdf_security(
            document,
            max_xref_objects=max_xref_objects,
            max_page_dimension=max_page_dimension,
        )

        rendered_pages: list[bytes] = []
        preview: bytes | None = None
        for index, page in enumerate(document):
            longest_side = max(float(page.rect.width), float(page.rect.height), 1.0)
            page_scale = min(render_scale, max_render_dimension / longest_side)
            matrix = pymupdf.Matrix(page_scale, page_scale)
            png = page.get_pixmap(matrix=matrix, alpha=False).tobytes("png")
            rendered_pages.append(png)
            if index == 0:
                preview = png
    finally:
        document.close()

    def run_model(client: httpx.Client, model: str) -> dict[str, Any]:
        pages = [
            _normalize_page(call_model(client, base_url, api_key, model, image, ), index + 1, model)
            for index, image in enumerate(rendered_pages)
        ]
        return apply_extraction_quality_gate(_assemble(pages, len(rendered_pages), model))

    with httpx.Client(timeout=timeout_seconds) as client:
        try:
            primary = run_model(client, primary_model)
        except AtlasParseError as error:
            fallback = run_model(client, fallback_model)
            return (
                _with_attempts(
                    fallback,
                    [(primary_model, None, str(error)), (fallback_model, fallback, None)],
                    fallback_reasons=["primary_request_error"],
                ),
                preview,
            )
        reasons = _fallback_reasons(primary, min_confidence)
        return _with_attempts(primary, [(primary_model, primary, None)], fallback_reasons=reasons), preview
