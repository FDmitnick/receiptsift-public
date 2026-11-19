from __future__ import annotations

import io
import re
from typing import Any

import numpy as np
from PIL import Image, ImageStat


def _amount_supported(value: Any, evidence: str) -> bool:
    if value is None:
        return True
    try:
        target = float(value)
    except (TypeError, ValueError):
        return False

    candidates: set[float] = set()
    for match in re.findall(r"-?\d[\d,.]*", evidence):
        token = match.rstrip(".,")
        if not token:
            continue
        variants = {token.replace(",", "")}
        separators = [index for index, character in enumerate(token) if character in ",."]
        if separators:
            last_separator = separators[-1]
            integer = re.sub(r"[,.]", "", token[:last_separator]) or "0"
            fraction = re.sub(r"[,.]", "", token[last_separator + 1 :])
            variants.add(f"{integer}.{fraction}" if fraction else integer)
            variants.add(re.sub(r"[,.]", "", token))
        for variant in variants:
            try:
                candidates.add(float(variant))
            except ValueError:
                continue
    return any(abs(target - candidate) <= 0.01 for candidate in candidates)


def _words(value: Any) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value).casefold()) if len(token) > 1}


def _text_supported(value: Any, evidence: str) -> bool:
    expected = _words(value)
    observed = _words(evidence)
    return bool(expected) and len(expected & observed) / len(expected) >= 0.6


def assess_extraction_result(result: dict[str, Any]) -> list[dict[str, str]]:
    """Return deterministic contradictions; this is not a calibrated correctness probability."""
    issues: list[dict[str, str]] = []
    fields = result.get("fields") if isinstance(result.get("fields"), dict) else {}

    for name in ("merchant", "total"):
        field = fields.get(name) if isinstance(fields.get(name), dict) else {}
        value = field.get("value")
        source = field.get("source") if isinstance(field.get("source"), dict) else {}
        evidence = str(source.get("text") or "").strip()
        if value is not None and not evidence:
            issues.append(
                {
                    "code": f"{name}_evidence_missing",
                    "severity": "high",
                    "message": f"{name.title()} has a value but no visible evidence text.",
                }
            )
        elif value is not None:
            supported = _amount_supported(value, evidence) if name == "total" else _text_supported(value, evidence)
            if not supported:
                issues.append(
                    {
                        "code": f"{name}_evidence_mismatch",
                        "severity": "high",
                        "message": f"{name.title()} does not match its supplied evidence text.",
                    }
                )

    total_field = fields.get("total") if isinstance(fields.get("total"), dict) else {}
    total_source = total_field.get("source") if isinstance(total_field.get("source"), dict) else {}
    total_evidence = str(total_source.get("text") or "").casefold()
    tender_words = {"cash", "change", "tender", "paid"}
    total_words = {"total", "due", "balance", "amount"}
    if any(word in total_evidence for word in tender_words) and not any(word in total_evidence for word in total_words):
        issues.append(
            {
                "code": "total_may_be_tender",
                "severity": "high",
                "message": "The selected total evidence looks like tender, cash, paid, or change rather than an amount due.",
            }
        )

    for date_name in ("issue_date", "due_date", "service_period_start", "service_period_end", "autopay_date"):
        date = (fields.get(date_name) or {}).get("value") if isinstance(fields.get(date_name), dict) else None
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            issues.append(
                {
                    "code": f"{date_name}_format_invalid",
                    "severity": "medium",
                    "message": f"{date_name} is not normalized as YYYY-MM-DD.",
                }
            )

    items = result.get("items") if isinstance(result.get("items"), list) else []
    unsupported_items = 0
    for item in items:
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        evidence = str(source.get("text") or "")
        if not evidence or not _amount_supported(item.get("amount"), evidence):
            unsupported_items += 1
    if items and unsupported_items:
        issues.append(
            {
                "code": "item_evidence_incomplete",
                "severity": "medium" if unsupported_items < len(items) else "high",
                "message": f"{unsupported_items} of {len(items)} line items lack matching amount evidence.",
            }
        )

    gross_amount = (
        (fields.get("gross_amount") or {}).get("value") if isinstance(fields.get("gross_amount"), dict) else None
    )
    discount = (fields.get("discount") or {}).get("value") if isinstance(fields.get("discount"), dict) else None
    refund = (fields.get("refund") or {}).get("value") if isinstance(fields.get("refund"), dict) else None
    subtotal = (fields.get("subtotal") or {}).get("value") if isinstance(fields.get("subtotal"), dict) else None
    if items and result.get("document_type") != "bill":
        item_sum = round(sum(float(item.get("amount") or 0) for item in items), 2)
        expected_subtotal = item_sum - float(discount or 0) - float(refund or 0)
        gross_mismatch = gross_amount is not None and abs(float(gross_amount) - item_sum) > 0.02
        subtotal_mismatch = subtotal is not None and abs(float(subtotal) - expected_subtotal) > 0.02
        if gross_mismatch or subtotal_mismatch:
            issues.append(
                {
                    "code": "items_subtotal_mismatch",
                    "severity": "high",
                    "message": "Line items, discounts, and refunds do not reconcile with gross amount and subtotal.",
                }
            )
    return issues


def apply_extraction_quality_gate(result: dict[str, Any]) -> dict[str, Any]:
    issues = assess_extraction_result(result)
    existing = {warning.get("code") for warning in result.get("warnings", [])}
    for issue in issues:
        if issue["severity"] == "high" and issue["code"] not in existing:
            result.setdefault("warnings", []).append({"code": issue["code"], "message": issue["message"]})
    result["deterministic_checks"] = issues
    if result.get("warnings"):
        result["status"] = "needs_review"
    return result


def inspect_image_quality(image_bytes: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(image_bytes)) as image:
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        width, height = gray.size
        pixels = np.asarray(gray, dtype=np.float32)
        edge_energy = float(np.mean(np.abs(np.diff(pixels, axis=0)))) if height > 1 else 0.0
        brightness = round(float(stat.mean[0]), 2)
        contrast = round(float(stat.stddev[0]), 2)
    flags = []
    if min(width, height) < 400:
        flags.append("low_resolution")
    if contrast < 18:
        flags.append("low_contrast")
    if brightness < 35 or brightness > 235:
        flags.append("extreme_brightness")
    if edge_energy < 2.2:
        flags.append("likely_blurry")
    if max(width, height) / max(1, min(width, height)) > 5:
        flags.append("extreme_aspect_ratio")
    return {
        "width": width,
        "height": height,
        "brightness": brightness,
        "contrast": contrast,
        "edge_energy": round(edge_energy, 3),
        "risk_flags": flags,
    }
