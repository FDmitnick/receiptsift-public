from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock
from typing import Any

import httpx
import pymupdf

from backend.atlas_parser import parse_pdf_with_atlas
from backend.config import Settings
from backend.gpt_verifier import verify_receipt_with_gpt
from backend.quality import inspect_image_quality

REPORT_LOCK = Lock()


def _prices_from_models(models: list[dict[str, Any]], defaults: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    prices = dict(defaults)
    for model in models:
        model_id = model.get("id")
        pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
        if model_id not in prices:
            continue
        try:
            prices[model_id] = (float(pricing["prompt"]) * 1_000_000, float(pricing["completion"]) * 1_000_000)
        except (KeyError, TypeError, ValueError):
            continue
    return prices


def _provider_prices(settings: Settings, verifier_model: str) -> tuple[dict[str, tuple[float, float]], str]:
    defaults = {
        settings.atlas_primary_model: (0.225, 1.8),
        settings.atlas_fallback_model: (0.5, 2.5),
        verifier_model: (2.5, 15.0),
    }
    try:
        response = httpx.get(
            f"{settings.atlas_base_url}/models",
            headers={"Authorization": f"Bearer {settings.atlas_api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        models = body.get("data") if isinstance(body.get("data"), list) else []
        return _prices_from_models(models, defaults), "atlas_models_api"
    except (httpx.HTTPError, TypeError, ValueError):
        return defaults, "documented_fallback"


def _money(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = re.sub(r"[^0-9,.-]", "", str(value)).strip()
    if re.fullmatch(r"-?\d{1,3}([,.]\d{3})+", text):
        text = text.replace(",", "").replace(".", "")
    elif "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".") if len(text.rsplit(",", 1)[-1]) <= 2 else text.replace(",", "")
    try:
        return round(float(text), 2)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _image_to_pdf(image_bytes: bytes) -> bytes:
    image = pymupdf.open(stream=image_bytes)
    try:
        pix = image[0].get_pixmap()
        width, height = pix.width, pix.height
    finally:
        image.close()
    document = pymupdf.open()
    try:
        page = document.new_page(width=width, height=height)
        page.insert_image(page.rect, stream=image_bytes, keep_proportion=True)
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def _ground_truth(annotation_path: Path) -> dict[str, Any]:
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    parsed = payload.get("gt_parse", {})
    total = parsed.get("total") if isinstance(parsed.get("total"), dict) else {}
    subtotal = parsed.get("sub_total") if isinstance(parsed.get("sub_total"), dict) else {}
    items = []
    raw_menu = parsed.get("menu", [])
    menu = [raw_menu] if isinstance(raw_menu, dict) else raw_menu
    for item in menu:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nm") or "").strip()
        amount = _money(item.get("price"))
        if name and amount is not None:
            items.append(
                {
                    "description": name,
                    "quantity": _money(item.get("cnt")) or 1.0,
                    "unit_price": _money(item.get("unitprice")),
                    "amount": amount,
                }
            )
        sub_names = item.get("sub_nm") if isinstance(item.get("sub_nm"), list) else []
        sub_prices = item.get("sub_price") if isinstance(item.get("sub_price"), list) else []
        for index, sub_name in enumerate(sub_names):
            sub_amount = _money(sub_prices[index]) if index < len(sub_prices) else None
            if str(sub_name).strip() and sub_amount is not None:
                items.append({"description": str(sub_name).strip(), "quantity": 1.0, "unit_price": None, "amount": sub_amount})
    return {
        "total": _money(total.get("total_price")),
        "subtotal": _money(subtotal.get("subtotal_price")),
        "tax": _money(subtotal.get("tax_price")),
        "items": items,
    }


def _score_items(expected: list[dict[str, Any]], observed: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = set(range(len(observed)))
    matches = []
    for expected_item in expected:
        best = None
        for index in candidates:
            observed_item = observed[index]
            if _money(observed_item.get("amount")) != _money(expected_item.get("amount")):
                continue
            similarity = SequenceMatcher(None, _text(expected_item.get("description")), _text(observed_item.get("description"))).ratio()
            if best is None or similarity > best[0]:
                best = (similarity, index)
        if best and best[0] >= 0.45:
            candidates.remove(best[1])
            matches.append(
                {
                    "expected": expected_item,
                    "observed": observed[best[1]],
                    "description_similarity": round(best[0], 3),
                }
            )
    precision = len(matches) / len(observed) if observed else (1.0 if not expected else 0.0)
    recall = len(matches) / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "expected_count": len(expected),
        "observed_count": len(observed),
        "matched_count": len(matches),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matches": matches,
    }


def _score(expected: dict[str, Any], fields: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    observed_total = _money(fields.get("total"))
    expected_total = _money(expected.get("total"))
    total_match = None if expected_total is None else observed_total == expected_total
    item_score = _score_items(expected.get("items", []), items)
    document_correct = total_match is True and item_score["precision"] == 1.0 and item_score["recall"] == 1.0
    return {
        "expected_total": expected_total,
        "observed_total": observed_total,
        "total_match": total_match,
        "items": item_score,
        "document_correct": document_correct,
    }


def _usage_cost(usage: dict[str, Any], input_price: float, output_price: float) -> float:
    return round(
        int(usage.get("input_tokens") or 0) * input_price / 1_000_000
        + int(usage.get("output_tokens") or 0) * output_price / 1_000_000,
        6,
    )


def _attempt_costs(result: dict[str, Any], prices: dict[str, tuple[float, float]]) -> list[dict[str, Any]]:
    costs = []
    for attempt in result.get("model_attempts", []):
        model = attempt.get("model")
        input_price, output_price = prices.get(model, (0.0, 0.0))
        costs.append(
            {
                "model": model,
                "usage": attempt.get("usage", {}),
                "estimated_cost_usd": _usage_cost(attempt.get("usage", {}), input_price, output_price),
                "error": attempt.get("error"),
            }
        )
    return costs


def _summary(documents: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [entry for entry in documents if not entry.get("error")]
    scoreable = [entry for entry in completed if entry.get("qwen_score", {}).get("total_match") is not None]
    qwen_correct = [entry for entry in scoreable if entry["qwen_score"]["document_correct"]]
    gpt_correct = [entry for entry in scoreable if entry["gpt_score"]["document_correct"]]
    qwen_ready = [entry for entry in scoreable if entry["qwen"]["status"] == "ready"]
    false_accepts = [entry for entry in qwen_ready if not entry["qwen_score"]["document_correct"]]
    caught = [
        entry
        for entry in scoreable
        if not entry["qwen_score"]["document_correct"] and entry["gpt"]["verdict"] != "pass"
    ]
    qwen_errors = [entry for entry in scoreable if not entry["qwen_score"]["document_correct"]]
    return {
        "requested": len(documents),
        "completed": len(completed),
        "failed": len(documents) - len(completed),
        "scoreable_totals": len(scoreable),
        "qwen_total_accuracy": round(sum(entry["qwen_score"]["total_match"] is True for entry in scoreable) / len(scoreable), 4)
        if scoreable
        else None,
        "qwen_document_exact_accuracy": round(len(qwen_correct) / len(scoreable), 4) if scoreable else None,
        "gpt_total_accuracy": round(sum(entry["gpt_score"]["total_match"] is True for entry in scoreable) / len(scoreable), 4)
        if scoreable
        else None,
        "gpt_document_exact_accuracy": round(len(gpt_correct) / len(scoreable), 4) if scoreable else None,
        "qwen_mean_item_recall": round(statistics.mean(entry["qwen_score"]["items"]["recall"] for entry in completed), 4)
        if completed
        else None,
        "gpt_mean_item_recall": round(statistics.mean(entry["gpt_score"]["items"]["recall"] for entry in completed), 4)
        if completed
        else None,
        "qwen_ready_count": len(qwen_ready),
        "qwen_false_accept_count": len(false_accepts),
        "qwen_false_accept_rate_among_ready": round(len(false_accepts) / len(qwen_ready), 4) if qwen_ready else None,
        "gpt_caught_qwen_error_rate": round(len(caught) / len(qwen_errors), 4) if qwen_errors else None,
        "fallback_count": sum(bool(entry["qwen"].get("quality_gate", {}).get("fallback_triggered")) for entry in completed),
        "gpt_pass_count": sum(entry["gpt"]["verdict"] == "pass" for entry in completed),
        "gpt_review_or_correct_count": sum(entry["gpt"]["verdict"] != "pass" for entry in completed),
        "estimated_cost_usd": round(sum(entry.get("estimated_cost_usd", 0) for entry in completed), 4),
        "mean_elapsed_seconds": round(statistics.mean(entry["elapsed_seconds"] for entry in completed), 3) if completed else None,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _run_one(
    annotation_path: Path,
    dataset_root: Path,
    settings: Settings,
    verifier_model: str,
    prices: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    started = time.perf_counter()
    sample_id = annotation_path.stem
    image_matches = list(dataset_root.rglob(f"{sample_id}.jpg"))
    if len(image_matches) != 1:
        raise RuntimeError(f"Expected one image for {sample_id}; found {len(image_matches)}")
    image_path = image_matches[0]
    image_bytes = image_path.read_bytes()
    expected = _ground_truth(annotation_path)
    quality = inspect_image_quality(image_bytes)
    pdf_bytes = _image_to_pdf(image_bytes)
    qwen_started = time.perf_counter()
    qwen, preview = parse_pdf_with_atlas(
        pdf_bytes,
        api_key=settings.atlas_api_key,
        base_url=settings.atlas_base_url,
        primary_model=settings.atlas_primary_model,
        fallback_model=settings.atlas_fallback_model,
        max_pages=1,
        timeout_seconds=settings.atlas_timeout_seconds,
        min_confidence=settings.atlas_min_confidence,
        render_scale=settings.atlas_render_scale,
        max_render_dimension=settings.atlas_max_render_dimension,
    )
    qwen_seconds = round(time.perf_counter() - qwen_started, 3)
    if not preview:
        raise RuntimeError("Parser did not return a rendered preview for GPT verification.")
    gpt_started = time.perf_counter()
    gpt = verify_receipt_with_gpt(
        [preview],
        qwen,
        api_key=settings.atlas_api_key,
        base_url=settings.atlas_base_url,
        model=verifier_model,
        timeout_seconds=settings.atlas_timeout_seconds,
    )
    gpt_seconds = round(time.perf_counter() - gpt_started, 3)
    qwen_fields = {name: field.get("value") for name, field in qwen.get("fields", {}).items()}
    qwen_score = _score(expected, qwen_fields, qwen.get("items", []))
    gpt_score = _score(expected, gpt["independent"], gpt["independent"]["items"])
    attempt_costs = _attempt_costs(qwen, prices)
    gpt_input_price, gpt_output_price = prices[verifier_model]
    gpt_cost = _usage_cost(gpt.get("usage", {}), gpt_input_price, gpt_output_price)
    final_status = "ready" if qwen_score["document_correct"] and gpt_score["document_correct"] else "needs_review"
    return {
        "sample_id": sample_id,
        "image": str(image_path.relative_to(dataset_root)).replace("\\", "/"),
        "image_quality": quality,
        "ground_truth": expected,
        "qwen": {
            "status": qwen.get("status"),
            "model": qwen.get("extraction_model"),
            "confidence": qwen.get("overall_confidence"),
            "fields": qwen_fields,
            "items": [
                {key: item.get(key) for key in ("description", "quantity", "unit_price", "amount")}
                for item in qwen.get("items", [])
            ],
            "reconciliation": qwen.get("reconciliation"),
            "warnings": qwen.get("warnings", []),
            "deterministic_checks": qwen.get("deterministic_checks", []),
            "quality_gate": qwen.get("quality_gate", {}),
            "model_attempts": qwen.get("model_attempts", []),
            "usage": qwen.get("provider_usage", {}),
            "elapsed_seconds": qwen_seconds,
        },
        "gpt": {**gpt, "elapsed_seconds": gpt_seconds},
        "qwen_score": qwen_score,
        "gpt_score": gpt_score,
        "final_status": final_status,
        "costs": {"qwen_attempts": attempt_costs, "gpt": gpt_cost},
        "estimated_cost_usd": round(sum(item["estimated_cost_usd"] for item in attempt_costs) + gpt_cost, 6),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 50 labeled receipt images through Qwen extraction and GPT verification.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".verify-data/receipt-eval-50/report.json"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sample-ids", help="Comma-separated receipt IDs for targeted regression runs.")
    parser.add_argument("--verifier-model", default="openai/gpt-5.6-terra")
    args = parser.parse_args()
    settings = Settings()
    if not settings.atlas_api_key:
        raise SystemExit("ATLASCLOUD_API_KEY or RECEIPTSIFT_ATLAS_API_KEY is required.")
    annotations = sorted(args.dataset_root.rglob("*-REC-*.json"))
    if args.sample_ids:
        selected_ids = {sample_id.strip() for sample_id in args.sample_ids.split(",") if sample_id.strip()}
        annotations = [path for path in annotations if path.stem in selected_ids]
    else:
        annotations = annotations[: max(0, args.limit)]
    if not annotations:
        raise SystemExit("No labeled receipt annotations were found.")

    prices, pricing_source = _provider_prices(settings, args.verifier_model)
    report = {
        "pipeline": {
            "primary_model": settings.atlas_primary_model,
            "fallback_model": settings.atlas_fallback_model,
            "verifier_model": args.verifier_model,
            "min_confidence": settings.atlas_min_confidence,
            "price_usd_per_million_tokens": {
                model: {"input": price[0], "output": price[1]} for model, price in prices.items()
            },
            "pricing_source": pricing_source,
        },
        "dataset": {"root": str(args.dataset_root.resolve()), "requested": len(annotations)},
        "documents": [],
        "summary": {},
    }
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        report["documents"] = previous.get("documents", [])
    completed_ids = {entry.get("sample_id") for entry in report["documents"] if not entry.get("error")}
    pending = [path for path in annotations if path.stem not in completed_ids]

    def save() -> None:
        with REPORT_LOCK:
            report["documents"] = sorted(report["documents"], key=lambda entry: entry.get("sample_id", ""))
            report["summary"] = _summary(report["documents"])
            _atomic_write(args.output, report)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(_run_one, path, args.dataset_root, settings, args.verifier_model, prices): path for path in pending
        }
        for index, future in enumerate(as_completed(futures), 1):
            path = futures[future]
            try:
                entry = future.result()
            except Exception as error:  # benchmark must preserve every failure for diagnosis
                entry = {"sample_id": path.stem, "error": type(error).__name__, "message": str(error)}
            report["documents"] = [item for item in report["documents"] if item.get("sample_id") != path.stem]
            report["documents"].append(entry)
            save()
            print(
                json.dumps(
                    {
                        "progress": f"{index}/{len(pending)}",
                        "sample_id": path.stem,
                        "qwen_total": entry.get("qwen_score", {}).get("total_match"),
                        "qwen_items_f1": entry.get("qwen_score", {}).get("items", {}).get("f1"),
                        "gpt_total": entry.get("gpt_score", {}).get("total_match"),
                        "gpt_items_f1": entry.get("gpt_score", {}).get("items", {}).get("f1"),
                        "final_status": entry.get("final_status"),
                        "cost": entry.get("estimated_cost_usd"),
                        "error": entry.get("error"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    save()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved private benchmark report to {args.output.resolve()}")
    return 0 if not report["summary"].get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
