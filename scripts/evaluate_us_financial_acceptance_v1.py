from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = next((parent for parent in ROOT.parents if (parent / "收据账单数据").is_dir()), ROOT.parent)
DEFAULT_DATASETS = (
    WORKSPACE / "收据账单数据" / "01_产品验收主测试集" / "美国财务文档验收集275份_Schema_v1_2020-2026",
    WORKSPACE / "收据账单数据" / "01_产品验收主测试集" / "美国高级Invoice测试集30份_Schema_v1_2020-2026",
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.document_schema import classify_document_type, finalize_document_result  # noqa: E402
from backend.parser import parse_pdf  # noqa: E402


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _same(expected: Any, actual: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return math.isclose(float(expected), float(actual), abs_tol=0.02)
        except (TypeError, ValueError):
            return False
    return _normalized_text(expected) == _normalized_text(actual)


def _actual_fields(result: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, field in (result.get("fields") or {}).items():
        values[name] = field.get("value") if isinstance(field, dict) else field
    return values


def _line_item_amount_total(items: list[dict[str, Any]]) -> float | None:
    amounts = []
    for item in items:
        value = item.get("amount")
        if value is None:
            continue
        try:
            amounts.append(float(value))
        except (TypeError, ValueError):
            continue
    return round(sum(amounts), 2) if amounts else None


def _line_item_metrics(expected_items: list[dict[str, Any]], actual_items: list[dict[str, Any]]) -> dict[str, Any]:
    actual_by_sku = {
        _normalized_text(item.get("sku")): item
        for item in actual_items
        if isinstance(item, dict) and item.get("sku")
    }
    matched_items = 0
    evaluated_fields = 0
    matched_fields = 0
    fields: dict[str, Counter[str]] = defaultdict(Counter)
    for position, expected in enumerate(expected_items):
        sku = _normalized_text(expected.get("sku"))
        actual = actual_by_sku.get(sku) if sku else (actual_items[position] if position < len(actual_items) else None)
        if actual is not None:
            matched_items += 1
        for name, expected_value in expected.items():
            if expected_value is None:
                continue
            matched = actual is not None and _same(expected_value, actual.get(name))
            evaluated_fields += 1
            matched_fields += int(matched)
            fields[name]["evaluated"] += 1
            fields[name]["matched"] += int(matched)
    return {
        "expected_items": len(expected_items),
        "matched_items": matched_items,
        "evaluated_fields": evaluated_fields,
        "matched_fields": matched_fields,
        "fields": fields,
    }


def _route_from_result(result: dict[str, Any]) -> str:
    method = str(result.get("extraction_method") or "none")
    if method == "embedded_text":
        return "copyable_pdf_text_path_candidate"
    if method == "ocr":
        return "noncopyable_pdf_vision_path_candidate"
    return method


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evaluate(dataset: Path, limit: int | None = None, *, reuse_results: bool = False) -> dict[str, Any]:
    manifest = list(csv.DictReader((dataset / "manifest.csv").open(encoding="utf-8-sig")))
    if limit:
        manifest = manifest[:limit]

    previous_summary_path = dataset / "pipeline_summary_latest.json"
    previous_summary = (
        json.loads(previous_summary_path.read_text(encoding="utf-8"))
        if reuse_results and previous_summary_path.is_file()
        else {}
    )

    rows: list[dict[str, Any]] = []
    field_totals: dict[str, Counter[str]] = defaultdict(Counter)
    type_field_totals: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    type_totals: dict[str, Counter[str]] = defaultdict(Counter)
    group_totals: dict[str, Counter[str]] = defaultdict(Counter)
    status_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    excluded_from_accuracy_counts: Counter[str] = Counter()
    line_item_field_totals: dict[str, Counter[str]] = defaultdict(Counter)
    errors: list[dict[str, str]] = []

    for position, manifest_row in enumerate(manifest, start=1):
        folder = dataset / manifest_row["relative_folder"]
        truth = json.loads((folder / "ground_truth.v1.json").read_text(encoding="utf-8"))
        pdf_path = folder / "document.pdf"
        sample_id = manifest_row["sample_id"]
        document_type = truth["document_type"]
        group = manifest_row["group"]
        ground_truth_status = truth["source"]["ground_truth_status"]
        exact = ground_truth_status == "exact"
        try:
            result_path = folder / "pipeline_result.latest.json"
            if reuse_results and result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                result_text = "\n".join(
                    str(page.get("text") or "") for page in result.get("pages") or [] if isinstance(page, dict)
                )
                finalize_document_result(
                    result,
                    text=result_text,
                    document_type=classify_document_type(result_text),
                )
            else:
                result, _ = parse_pdf(pdf_path.read_bytes(), max_pages=30)
            _write_json(result_path, result)
        except Exception as error:  # noqa: BLE001 - an acceptance runner must record every failure
            errors.append({"sample_id": sample_id, "error": f"{type(error).__name__}: {error}"})
            rows.append(
                {
                    "sample_id": sample_id,
                    "group": group,
                    "expected_type": document_type,
                    "actual_type": "error",
                    "type_correct": "no",
                    "status": "error",
                    "extraction_method": "error",
                    "route_candidate": "error",
                    "evaluated_fields": 0,
                    "matched_fields": 0,
                    "field_accuracy": "",
                    "all_fields_correct": "no",
                    "line_item_total_correct": "",
                    "line_item_recall": "",
                    "line_item_field_accuracy": "",
                    "reconciliation_matched": "",
                    "warnings": "",
                    "error": str(error),
                }
            )
            print(f"[{position}/{len(manifest)}] {sample_id}: ERROR {error}", flush=True)
            continue

        status = str(result.get("status") or "unknown")
        method = str(result.get("extraction_method") or "none")
        route_candidate = _route_from_result(result)
        actual_type = str(result.get("document_type") or "")
        type_correct = actual_type == document_type
        status_counts[status] += 1
        method_counts[method] += 1
        route_counts[route_candidate] += 1
        type_totals[document_type]["documents"] += 1
        group_totals[group]["documents"] += 1
        if exact:
            type_totals[document_type]["type_evaluated_documents"] += 1
            type_totals[document_type]["type_matched"] += int(type_correct)
            group_totals[group]["type_evaluated_documents"] += 1
            group_totals[group]["type_matched"] += int(type_correct)
        else:
            excluded_from_accuracy_counts[ground_truth_status or "unknown"] += 1
        for warning in result.get("warnings") or []:
            warning_counts[str(warning.get("code") or "unknown")] += 1

        evaluated_fields = 0
        matched_fields = 0
        actual_fields = _actual_fields(result)
        if exact:
            for name, expected in truth["fields"].items():
                if expected is None:
                    continue
                matched = _same(expected, actual_fields.get(name))
                evaluated_fields += 1
                matched_fields += int(matched)
                field_totals[name]["evaluated"] += 1
                field_totals[name]["matched"] += int(matched)
                type_field_totals[document_type][name]["evaluated"] += 1
                type_field_totals[document_type][name]["matched"] += int(matched)
            type_totals[document_type]["exact_documents"] += 1
            type_totals[document_type]["evaluated_fields"] += evaluated_fields
            type_totals[document_type]["matched_fields"] += matched_fields
            type_totals[document_type]["all_fields_correct"] += int(evaluated_fields > 0 and evaluated_fields == matched_fields)
            group_totals[group]["exact_documents"] += 1
            group_totals[group]["evaluated_fields"] += evaluated_fields
            group_totals[group]["matched_fields"] += matched_fields
            group_totals[group]["all_fields_correct"] += int(evaluated_fields > 0 and evaluated_fields == matched_fields)

        expected_item_total = _line_item_amount_total(truth.get("line_items") or [])
        actual_item_total = _line_item_amount_total(result.get("items") or [])
        line_metrics = _line_item_metrics(truth.get("line_items") or [], result.get("items") or []) if exact else None
        item_total_correct = None
        if exact and expected_item_total is not None:
            item_total_correct = _same(expected_item_total, actual_item_total)
            for counter in (type_totals[document_type], group_totals[group]):
                counter["line_item_documents"] += 1
                counter["line_item_total_matched"] += int(item_total_correct)
        if line_metrics and line_metrics["expected_items"]:
            for counter in (type_totals[document_type], group_totals[group]):
                counter["expected_line_items"] += line_metrics["expected_items"]
                counter["matched_line_items"] += line_metrics["matched_items"]
                counter["line_item_fields_evaluated"] += line_metrics["evaluated_fields"]
                counter["line_item_fields_matched"] += line_metrics["matched_fields"]
            for name, counter in line_metrics["fields"].items():
                line_item_field_totals[name]["evaluated"] += counter["evaluated"]
                line_item_field_totals[name]["matched"] += counter["matched"]

        reconciliations = [check for check in result.get("reconciliations") or [] if check.get("matched") is not None]
        reconciliation_matched = all(check["matched"] for check in reconciliations) if reconciliations else None
        if exact and reconciliation_matched is not None:
            for counter in (type_totals[document_type], group_totals[group]):
                counter["reconciliation_documents"] += 1
                counter["reconciliation_matched"] += int(reconciliation_matched)

        rows.append(
            {
                "sample_id": sample_id,
                "group": group,
                "expected_type": document_type,
                "actual_type": actual_type,
                "type_correct": "yes" if type_correct else "no",
                "status": status,
                "extraction_method": method,
                "route_candidate": route_candidate,
                "evaluated_fields": evaluated_fields,
                "matched_fields": matched_fields,
                "field_accuracy": round(matched_fields / evaluated_fields, 4) if evaluated_fields else "",
                "all_fields_correct": "yes" if evaluated_fields and evaluated_fields == matched_fields else "no",
                "line_item_total_correct": "" if item_total_correct is None else ("yes" if item_total_correct else "no"),
                "line_item_recall": (
                    round(line_metrics["matched_items"] / line_metrics["expected_items"], 4)
                    if line_metrics and line_metrics["expected_items"]
                    else ""
                ),
                "line_item_field_accuracy": (
                    round(line_metrics["matched_fields"] / line_metrics["evaluated_fields"], 4)
                    if line_metrics and line_metrics["evaluated_fields"]
                    else ""
                ),
                "reconciliation_matched": "" if reconciliation_matched is None else ("yes" if reconciliation_matched else "no"),
                "warnings": "|".join(str(warning.get("code") or "unknown") for warning in result.get("warnings") or []),
                "error": "",
            }
        )
        if position % 10 == 0 or position == len(manifest):
            print(f"[{position}/{len(manifest)}] complete", flush=True)

    with (dataset / "PIPELINE_RESULTS_LATEST.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def counter_report(counter: Counter[str]) -> dict[str, Any]:
        documents = counter["documents"]
        type_evaluated_documents = counter["type_evaluated_documents"]
        exact_documents = counter["exact_documents"]
        evaluated = counter["evaluated_fields"]
        return {
            "documents": documents,
            "document_type_evaluated_documents": type_evaluated_documents,
            "document_type_accuracy": round(counter["type_matched"] / type_evaluated_documents, 4)
            if type_evaluated_documents
            else None,
            "exact_ground_truth_documents": exact_documents,
            "field_accuracy": round(counter["matched_fields"] / evaluated, 4) if evaluated else None,
            "all_non_null_fields_correct_rate": round(counter["all_fields_correct"] / exact_documents, 4) if exact_documents else None,
            "line_item_total_accuracy": round(counter["line_item_total_matched"] / counter["line_item_documents"], 4)
            if counter["line_item_documents"]
            else None,
            "line_item_recall": round(counter["matched_line_items"] / counter["expected_line_items"], 4)
            if counter["expected_line_items"]
            else None,
            "line_item_field_accuracy": round(counter["line_item_fields_matched"] / counter["line_item_fields_evaluated"], 4)
            if counter["line_item_fields_evaluated"]
            else None,
            "reconciliation_accuracy": round(counter["reconciliation_matched"] / counter["reconciliation_documents"], 4)
            if counter["reconciliation_documents"]
            else None,
        }

    field_report = {
        name: {
            "matched": counter["matched"],
            "evaluated": counter["evaluated"],
            "accuracy": round(counter["matched"] / counter["evaluated"], 4),
        }
        for name, counter in sorted(field_totals.items())
        if counter["evaluated"]
    }
    type_field_report = {
        document_type: {
            name: {
                "matched": counter["matched"],
                "evaluated": counter["evaluated"],
                "accuracy": round(counter["matched"] / counter["evaluated"], 4),
            }
            for name, counter in sorted(fields.items())
            if counter["evaluated"]
        }
        for document_type, fields in type_field_totals.items()
    }
    summary = {
        "schema_version": "1.0",
        "dataset": dataset.name,
        "parser_commit": previous_summary.get("parser_commit") if reuse_results else _git_commit(),
        "execution_mode": "reuse_results" if reuse_results else "fresh_parse",
        "documents_total": len(manifest),
        "accuracy_eligible_documents": sum(
            counter["type_evaluated_documents"] for counter in type_totals.values()
        ),
        "excluded_from_accuracy": dict(excluded_from_accuracy_counts),
        "pipeline_completed": len(manifest) - len(errors),
        "errors": errors,
        "status_counts": dict(status_counts),
        "extraction_method_counts": dict(method_counts),
        "route_candidate_counts": dict(route_counts),
        "warning_counts": dict(warning_counts),
        "by_document_type": {name: counter_report(counter) for name, counter in sorted(type_totals.items())},
        "by_group": {name: counter_report(counter) for name, counter in sorted(group_totals.items())},
        "field_accuracy": field_report,
        "field_accuracy_by_document_type": type_field_report,
        "line_item_field_accuracy": {
            name: {
                "matched": counter["matched"],
                "evaluated": counter["evaluated"],
                "accuracy": round(counter["matched"] / counter["evaluated"], 4),
            }
            for name, counter in sorted(line_item_field_totals.items())
            if counter["evaluated"]
        },
        "routing_note": (
            "Route candidates are inferred from the local extraction method. No paid Atlas/LLM calls were made: "
            "embedded-text PDFs are MarkItDown/text-path candidates; OCR PDFs are vision-path candidates."
        ),
    }
    _write_json(dataset / "pipeline_summary_latest.json", summary)
    _write_markdown_report(dataset / "ACCURACY_REPORT_LATEST.md", summary)
    print(json.dumps({"completed": summary["pipeline_completed"], "errors": len(errors)}, ensure_ascii=False), flush=True)
    return summary


def _git_commit() -> str | None:
    try:
        import subprocess

        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def _percent(value: Any) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# 最新解析器完整准确率报告",
        "",
        f"- Parser commit: `{summary['parser_commit'] or 'unknown'}`",
        f"- Execution mode: `{summary['execution_mode']}`",
        f"- 文档总数：{summary['documents_total']}",
        f"- 进入生产准确率：{summary['accuracy_eligible_documents']}",
        f"- 排除出准确率：{json.dumps(summary['excluded_from_accuracy'], ensure_ascii=False)}",
        f"- 完成：{summary['pipeline_completed']}",
        f"- 程序错误：{len(summary['errors'])}",
        f"- 状态：{json.dumps(summary['status_counts'], ensure_ascii=False)}",
        f"- 提取方式：{json.dumps(summary['extraction_method_counts'], ensure_ascii=False)}",
        "",
        "## 按文档类型",
        "",
        "| 类型 | 文档数 | 类型准确率 | 字段准确率 | 全字段全对 | 行项目召回率 | 行项目字段准确率 | 行项目金额准确率 | 勾稽准确率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in summary["by_document_type"].items():
        lines.append(
            f"| {name} | {result['documents']} | {_percent(result['document_type_accuracy'])} | "
            f"{_percent(result['field_accuracy'])} | {_percent(result['all_non_null_fields_correct_rate'])} | "
            f"{_percent(result['line_item_recall'])} | {_percent(result['line_item_field_accuracy'])} | "
            f"{_percent(result['line_item_total_accuracy'])} | {_percent(result['reconciliation_accuracy'])} |"
        )
    lines.extend(["", "## 逐字段准确率", "", "| 字段 | 匹配/评估 | 准确率 |", "|---|---:|---:|"])
    for name, result in summary["field_accuracy"].items():
        lines.append(f"| {name} | {result['matched']}/{result['evaluated']} | {_percent(result['accuracy'])} |")
    lines.extend(["", "## 行项目逐字段准确率", "", "| 字段 | 匹配/评估 | 准确率 |", "|---|---:|---:|"])
    for name, result in summary["line_item_field_accuracy"].items():
        lines.append(f"| {name} | {result['matched']}/{result['evaluated']} | {_percent(result['accuracy'])} |")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 准确率只统计真值中非空字段；39份 flow-only 官方公开页面只计流程成功，不计字段准确率。",
            "- `all_non_null_fields_correct_rate` 要求单份文档所有有真值字段全部匹配，是最严格指标。",
            "- 本轮为本地最新版解析器回归，没有调用付费 Atlas/LLM。",
            "- embedded_text 表示可复制PDF；ocr 表示扫描型PDF。是否实际调用 MarkItDown/视觉模型取决于生产环境是否启用 Atlas。",
            "- 失败和警告逐份见 `PIPELINE_RESULTS_LATEST.csv` 以及样本目录的 `pipeline_result.latest.json`。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, action="append", help="Repeat to evaluate multiple dataset roots.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reuse-results", action="store_true", help="Re-score existing pipeline_result.latest.json files.")
    args = parser.parse_args()
    datasets = tuple(args.dataset) if args.dataset else DEFAULT_DATASETS
    summaries = [evaluate(dataset.resolve(), args.limit, reuse_results=args.reuse_results) for dataset in datasets]
    print(
        json.dumps(
            {
                "datasets": len(summaries),
                "documents_total": sum(summary["documents_total"] for summary in summaries),
                "pipeline_completed": sum(summary["pipeline_completed"] for summary in summaries),
                "errors": sum(len(summary["errors"]) for summary in summaries),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
