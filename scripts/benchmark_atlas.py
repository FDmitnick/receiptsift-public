from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backend.atlas_parser import parse_pdf_with_atlas
from backend.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run private PDF fixtures through the Atlas Cloud extraction pipeline.")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".verify-data/atlas-benchmark.json"))
    args = parser.parse_args()
    settings = Settings()
    if not settings.atlas_api_key:
        raise SystemExit("ATLASCLOUD_API_KEY or RECEIPTSIFT_ATLAS_API_KEY is required.")

    pdfs = [args.input_dir] if args.input_dir.is_file() else sorted(args.input_dir.rglob("*.pdf"))
    report = {
        "pipeline": {
            "primary_model": settings.atlas_primary_model,
            "fallback_model": settings.atlas_fallback_model,
            "min_confidence": settings.atlas_min_confidence,
            "render_scale": settings.atlas_render_scale,
        },
        "documents": [],
    }
    for path in pdfs:
        started = time.perf_counter()
        try:
            result, _ = parse_pdf_with_atlas(
                path.read_bytes(),
                api_key=settings.atlas_api_key,
                base_url=settings.atlas_base_url,
                primary_model=settings.atlas_primary_model,
                fallback_model=settings.atlas_fallback_model,
                max_pages=settings.max_pages,
                timeout_seconds=settings.atlas_timeout_seconds,
                min_confidence=settings.atlas_min_confidence,
                render_scale=settings.atlas_render_scale,
            )
            entry = {
                "filename": path.name,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "model": result.get("extraction_model"),
                "status": result["status"],
                "confidence": result["overall_confidence"],
                "fields": {name: field.get("value") for name, field in result["fields"].items()},
                "item_count": len(result["items"]),
                "items": [
                    {key: item.get(key) for key in ("description", "quantity", "unit_price", "amount")}
                    for item in result["items"]
                ],
                "reconciliation": result["reconciliation"],
                "warnings": result["warnings"],
            }
        except Exception as error:  # benchmark must continue and record the failed fixture
            entry = {
                "filename": path.name,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error": type(error).__name__,
                "message": str(error),
            }
        report["documents"].append(entry)
        print(json.dumps(entry, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved private benchmark report to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
