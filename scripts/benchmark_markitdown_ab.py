from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.atlas_parser import parse_pdf_with_atlas  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.markitdown_router import _call_text_model, _parse_markdown_pages, decide_pdf_route  # noqa: E402

ROOT = PROJECT_ROOT.parent
DEFAULT_PDF_DIR = ROOT / "work" / "markitdown-poc" / "tmp" / "pdfs" / "native"
DEFAULT_EXPECTED_DIR = (
    ROOT
    / "收据账单数据"
    / "美国现代专项测试集200份_2020-2026"
    / "02_受控合成现代样本161份"
)
DEFAULT_OUTPUT = ROOT / "MarkItDown模型AB测试"
FIELDS = (
    "merchant",
    "date",
    "currency",
    "receipt_number",
    "card_last4",
    "gross_amount",
    "discount",
    "refund",
    "subtotal",
    "tax",
    "tip",
    "total",
    "payment_method",
)


def normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def field_matches(name: str, actual: Any, expected: Any) -> bool:
    if name in {"gross_amount", "discount", "refund", "subtotal", "tax", "tip", "total"}:
        try:
            return abs(float(actual) - float(expected)) <= 0.01
        except (TypeError, ValueError):
            return False
    return normalized(actual) == normalized(expected)


def score_result(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    field_checks = {
        name: field_matches(name, result.get("fields", {}).get(name, {}).get("value"), expected.get(name))
        for name in FIELDS
    }
    actual_items = {
        (normalized(item.get("description")), round(float(item.get("amount") or 0), 2))
        for item in result.get("items", [])
    }
    expected_items = {
        (normalized(item.get("description")), round(float(item.get("amount") or 0), 2))
        for item in expected.get("items", [])
    }
    item_hits = len(actual_items & expected_items)
    usage = result.get("provider_usage") if isinstance(result.get("provider_usage"), dict) else {}
    return {
        "field_hits": sum(field_checks.values()),
        "field_total": len(field_checks),
        "field_checks": field_checks,
        "item_hits": item_hits,
        "item_total": len(expected_items),
        "extra_items": len(actual_items - expected_items),
        "status": result.get("status"),
        "warnings": [warning.get("code") for warning in result.get("warnings", [])],
        "reconciliation": result.get("reconciliation"),
        "model": result.get("extraction_model"),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "calls": int(usage.get("calls") or 0),
    }


def load_expected(sample_id: str, expected_dir: Path) -> dict[str, Any]:
    path = expected_dir / sample_id / "expected.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def select_pdfs(pdf_dir: Path, ids: list[str], limit: int | None) -> list[Path]:
    if ids:
        paths = [pdf_dir / f"{sample_id}.pdf" for sample_id in ids]
    else:
        paths = sorted(pdf_dir.glob("*.pdf"))
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing PDFs: {', '.join(str(path) for path in missing)}")
    return paths[:limit] if limit else paths


def run() -> int:
    parser = argparse.ArgumentParser(description="Compare MarkItDown->text LLM with direct PDF->vision LLM.")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--expected-dir", type=Path, default=DEFAULT_EXPECTED_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ids", nargs="*", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--text-model")
    parser.add_argument("--vision-model")
    parser.add_argument("--routes", nargs="+", choices=("text", "vision"), default=("text", "vision"))
    args = parser.parse_args()

    settings = Settings()
    if not settings.atlas_api_key:
        raise SystemExit("ATLASCLOUD_API_KEY or RECEIPTSIFT_ATLAS_API_KEY is required.")
    args.output.mkdir(parents=True, exist_ok=True)
    pdfs = select_pdfs(args.pdf_dir, args.ids, args.limit)
    rows: list[dict[str, Any]] = []
    raw_results: dict[str, dict[str, Any]] = {}

    for pdf_path in pdfs:
        sample_id = pdf_path.stem
        expected = load_expected(sample_id, args.expected_dir)
        pdf_bytes = pdf_path.read_bytes()
        decision = decide_pdf_route(pdf_bytes, settings.max_pages)
        if decision.route != "markitdown_text_llm":
            rows.append({
                "sample_id": sample_id,
                "category": expected["category"],
                "route": "text",
                "error": f"router rejected text path: {decision.reason}",
            })
            continue

        for route in args.routes:
            started = time.perf_counter()
            try:
                if route == "text":
                    result = _parse_markdown_pages(
                        decision,
                        api_key=settings.atlas_api_key,
                        base_url=settings.atlas_base_url,
                        model=args.text_model or settings.atlas_primary_model,
                        timeout_seconds=settings.atlas_timeout_seconds,
                        call_text_model=_call_text_model,
                    )
                else:
                    result, _ = parse_pdf_with_atlas(
                        pdf_bytes,
                        api_key=settings.atlas_api_key,
                        base_url=settings.atlas_base_url,
                        primary_model=args.vision_model or settings.atlas_primary_model,
                        fallback_model=args.vision_model or settings.atlas_primary_model,
                        max_pages=settings.max_pages,
                        timeout_seconds=settings.atlas_timeout_seconds,
                        min_confidence=settings.atlas_min_confidence,
                        render_scale=settings.atlas_render_scale,
                        max_render_dimension=settings.atlas_max_render_dimension,
                    )
                score = score_result(result, expected)
                raw_results[f"{sample_id}:{route}"] = result
                row = {
                    "sample_id": sample_id,
                    "category": expected["category"],
                    "page_count": expected["page_count"],
                    "route": route,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    **score,
                }
            except Exception as error:
                row = {
                    "sample_id": sample_id,
                    "category": expected["category"],
                    "page_count": expected["page_count"],
                    "route": route,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "error": type(error).__name__,
                    "message": str(error),
                }
            rows.append(row)
            (args.output / "progress.json").write_text(
                json.dumps({"rows": rows, "raw_results": raw_results}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(row, ensure_ascii=False))

    summary: dict[str, Any] = {
        "documents": len(pdfs),
        "text_model": args.text_model or settings.atlas_primary_model,
        "vision_model": args.vision_model or settings.atlas_primary_model,
        "routes": {},
    }
    for route in args.routes:
        route_rows = [row for row in rows if row.get("route") == route and not row.get("error")]
        summary["routes"][route] = {
            "documents": len(route_rows),
            "field_hits": sum(int(row.get("field_hits") or 0) for row in route_rows),
            "field_total": sum(int(row.get("field_total") or 0) for row in route_rows),
            "item_hits": sum(int(row.get("item_hits") or 0) for row in route_rows),
            "item_total": sum(int(row.get("item_total") or 0) for row in route_rows),
            "extra_items": sum(int(row.get("extra_items") or 0) for row in route_rows),
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in route_rows),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in route_rows),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in route_rows),
            "calls": sum(int(row.get("calls") or 0) for row in route_rows),
            "elapsed_seconds": round(sum(float(row.get("elapsed_seconds") or 0) for row in route_rows), 3),
        }
    report = {"summary": summary, "rows": rows, "raw_results": raw_results}
    (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
