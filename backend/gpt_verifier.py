from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx

from .provider import post_json_with_retry

VERIFICATION_PROMPT = """You are the independent final verifier for a financial-document extraction system.
Read the receipt, invoice, or bill image yourself before comparing it with the candidate extraction. Do not trust the candidate's
self-reported confidence. Never invent obscured text.

Return one JSON object only:
{
  "document_type": "receipt"|"invoice"|"bill"|"other"|"unreadable",
  "verdict": "pass"|"corrected"|"review",
  "confidence": number,
  "independent": {
    "vendor_name": string|null, "issue_date": "YYYY-MM-DD"|null, "due_date": "YYYY-MM-DD"|null,
    "document_number": string|null, "currency": string|null,
    "subtotal": number|null, "tax": number|null, "tip": number|null, "total": number|null, "balance_due": number|null,
    "items": [{"description": string, "quantity": number, "unit_price": number|null, "amount": number}]
  },
  "discrepancies": [
    {"field": string, "candidate": string|number|null, "observed": string|number|null,
     "severity": "low"|"medium"|"high", "evidence": string|null}
  ],
  "notes": [string]
}

Rules:
- PASS only when the vendor, dates and number when visible, total or balance due, and every visible line item agree with the image.
- Never treat CASH, TENDERED, PAID, CHANGE, or card authorization amounts as the purchase total.
- Apply the candidate document type's reconciliation formula; do not apply a receipt tip formula to invoices or bills.
- Use REVIEW when the image is too blurred, cropped, redacted, or ambiguous to verify independently.
- A discrepancy in total or a missing purchased line item is high severity.
"""


class GptVerificationError(RuntimeError):
    pass


def _json_object(content: Any) -> dict[str, Any]:
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    if not isinstance(content, str):
        raise GptVerificationError("GPT verifier returned an unsupported response format.")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end <= start:
        raise GptVerificationError("GPT verifier did not return a JSON object.")
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as error:
        raise GptVerificationError("GPT verifier returned invalid JSON.") from error
    if not isinstance(parsed, dict):
        raise GptVerificationError("GPT verifier response is not a JSON object.")
    return parsed


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(str(value).replace(",", "").replace("$", "").strip()), 2)
    except (TypeError, ValueError):
        return None


def _call_verifier_model(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    images: list[bytes],
    extraction: dict[str, Any],
) -> dict[str, Any]:
    candidate = {
        "fields": {name: field.get("value") for name, field in extraction.get("fields", {}).items()},
        "items": [
            {key: item.get(key) for key in ("description", "quantity", "unit_price", "amount")}
            for item in extraction.get("items", [])
        ],
        "reconciliation": extraction.get("reconciliation"),
        "reconciliations": extraction.get("reconciliations"),
    }
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"{VERIFICATION_PROMPT}\nCandidate extraction:\n{json.dumps(candidate, ensure_ascii=False)}"}
    ]
    for image in images:
        encoded = base64.b64encode(image).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}})
    try:
        response = post_json_with_retry(
            client,
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-AtlasCloud-Request-Retention-Hours": "0",
            },
            payload={
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "temperature": 0,
                "max_tokens": 4096,
                "response_format": {"type": "json_object"},
            },
        )
        body = response.json()
        parsed = _json_object(body["choices"][0]["message"]["content"])
    except httpx.HTTPStatusError as error:
        raise GptVerificationError(f"GPT verification request failed with HTTP {error.response.status_code}.") from error
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise GptVerificationError("GPT verification request failed before a valid response was received.") from error
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    parsed["provider_request_id"] = body.get("id")
    parsed["usage"] = {
        "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "calls": 1,
    }
    return parsed


def _normalize_verification(payload: dict[str, Any], model: str) -> dict[str, Any]:
    independent = payload.get("independent") if isinstance(payload.get("independent"), dict) else {}
    raw_items = independent.get("items") if isinstance(independent.get("items"), list) else []
    items = []
    for raw in raw_items[:500]:
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description") or "").strip()
        amount = _number(raw.get("amount"))
        if not description or amount is None:
            continue
        items.append(
            {
                "description": description[:500],
                "quantity": _number(raw.get("quantity")) or 1.0,
                "unit_price": _number(raw.get("unit_price")),
                "amount": amount,
            }
        )
    normalized = {
        "model": model,
        "document_type": str(payload.get("document_type") or "unreadable").strip().lower(),
        "verdict": str(payload.get("verdict") or "review").strip().lower(),
        "confidence": max(0.0, min(1.0, float(payload.get("confidence") or 0))),
        "independent": {
            "vendor_name": independent.get("vendor_name") or independent.get("merchant"),
            "issue_date": independent.get("issue_date") or independent.get("date"),
            "merchant": independent.get("merchant") or independent.get("vendor_name"),
            "date": independent.get("date") or independent.get("issue_date"),
            "due_date": independent.get("due_date"),
            "document_number": independent.get("document_number"),
            "currency": independent.get("currency"),
            "subtotal": _number(independent.get("subtotal")),
            "tax": _number(independent.get("tax")),
            "tip": _number(independent.get("tip")),
            "total": _number(independent.get("total")),
            "balance_due": _number(independent.get("balance_due")),
            "items": items,
        },
        "discrepancies": payload.get("discrepancies") if isinstance(payload.get("discrepancies"), list) else [],
        "notes": payload.get("notes") if isinstance(payload.get("notes"), list) else [],
        "provider_request_id": payload.get("provider_request_id"),
        "usage": payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
    }
    if normalized["verdict"] not in {"pass", "corrected", "review"}:
        normalized["verdict"] = "review"
    return normalized


def verify_receipt_with_gpt(
    images: list[bytes],
    extraction: dict[str, Any],
    *,
    api_key: str,
    base_url: str,
    model: str = "openai/gpt-5.6-terra",
    timeout_seconds: float = 90,
    call_model: Callable[[httpx.Client, str, str, str, list[bytes], dict[str, Any]], dict[str, Any]] = _call_verifier_model,
) -> dict[str, Any]:
    if not api_key:
        raise GptVerificationError("Atlas Cloud API key is not configured.")
    if not images:
        raise GptVerificationError("At least one rendered receipt page is required.")
    with httpx.Client(timeout=timeout_seconds) as client:
        payload = call_model(client, base_url, api_key, model, images, extraction)
    return _normalize_verification(payload, model)
