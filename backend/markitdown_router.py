from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from io import BytesIO
from typing import Any

import httpx

from .atlas_parser import (
    EXTRACTION_PROMPT,
    AtlasParseError,
    _assemble,
    _fallback_reasons,
    _json_object,
    _normalize_page,
    parse_pdf_with_atlas,
)
from .parser import PdfParseError, validate_pdf_security
from .provider import post_json_with_retry
from .quality import apply_extraction_quality_gate

FINANCIAL_ANCHORS = (
    "total",
    "amount due",
    "balance",
    "payment",
    "tax",
    "charge",
    "invoice",
    "statement",
    "account",
    "usage",
)
MONEY_PATTERN = re.compile(r"(?:\$\s*)?[-+]?\d[\d,]*\.\d{2}")


@dataclass(frozen=True)
class PageRouteAnalysis:
    page: int
    route: str
    reason: str
    markdown_chars: int
    money_count: int
    anchor_count: int
    embedded_text_chars: int
    image_count: int
    largest_image_ratio: float
    markdown: str


@dataclass(frozen=True)
class PdfRouteDecision:
    route: str
    reason: str
    pages: tuple[PageRouteAnalysis, ...]
    preview: bytes | None


def _page_image_metrics(page: Any) -> tuple[int, float]:
    page_area = max(1.0, float(page.rect.width * page.rect.height))
    ratios: list[float] = []
    for info in page.get_image_info(xrefs=True):
        try:
            import pymupdf

            bbox = pymupdf.Rect(info.get("bbox", (0, 0, 0, 0)))
        except (TypeError, ValueError):
            continue
        if not bbox.is_empty:
            ratios.append(min(1.0, max(0.0, float(bbox.get_area() / page_area))))
    return len(ratios), max(ratios, default=0.0)


@lru_cache(maxsize=1)
def _markitdown_converter():
    try:
        from markitdown import MarkItDown
    except ImportError as error:
        raise AtlasParseError("MarkItDown is not installed.") from error
    return MarkItDown(enable_plugins=False)


def _convert_page_with_markitdown(page_pdf: bytes) -> str:
    try:
        result = _markitdown_converter().convert_stream(BytesIO(page_pdf), file_extension=".pdf")
    except Exception as error:
        raise AtlasParseError("MarkItDown could not convert the PDF page.") from error
    return result.text_content or ""


def _page_pdf_bytes(document: Any, page_index: int) -> bytes:
    import pymupdf

    single_page = pymupdf.open()
    try:
        single_page.insert_pdf(document, from_page=page_index, to_page=page_index)
        return single_page.tobytes(garbage=4, deflate=True)
    finally:
        single_page.close()


def _analyze_page(
    page: Any,
    page_number: int,
    markdown: str,
    *,
    min_text_chars: int,
    min_money_values: int,
    min_financial_anchors: int,
    max_large_image_ratio: float,
) -> PageRouteAnalysis:
    lower = markdown.casefold()
    money_count = len(MONEY_PATTERN.findall(markdown))
    anchor_count = sum(anchor in lower for anchor in FINANCIAL_ANCHORS)
    image_count, largest_image_ratio = _page_image_metrics(page)
    embedded_text_chars = len(page.get_text("text").strip())

    if len(markdown.strip()) < min_text_chars:
        route, reason = "vision_llm", "insufficient_markdown_text"
    elif largest_image_ratio >= max_large_image_ratio:
        route, reason = "vision_llm", "hybrid_pdf_large_image"
    elif money_count < min_money_values or anchor_count < min_financial_anchors:
        route, reason = "vision_llm", "insufficient_financial_evidence"
    else:
        route, reason = "markitdown_text_llm", "markdown_quality_gate_passed"

    return PageRouteAnalysis(
        page=page_number,
        route=route,
        reason=reason,
        markdown_chars=len(markdown),
        money_count=money_count,
        anchor_count=anchor_count,
        embedded_text_chars=embedded_text_chars,
        image_count=image_count,
        largest_image_ratio=round(largest_image_ratio, 4),
        markdown=markdown,
    )


def decide_pdf_route(
    pdf_bytes: bytes,
    max_pages: int,
    *,
    convert_page: Callable[[bytes], str] = _convert_page_with_markitdown,
    min_text_chars: int = 120,
    min_money_values: int = 3,
    min_financial_anchors: int = 3,
    max_large_image_ratio: float = 0.20,
    max_render_dimension: int = 3000,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
) -> PdfRouteDecision:
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

        preview_side = max(float(document[0].rect.width), float(document[0].rect.height), 1.0)
        preview_scale = min(1.7, max_render_dimension / preview_side)
        preview = document[0].get_pixmap(
            matrix=pymupdf.Matrix(preview_scale, preview_scale),
            alpha=False,
        ).tobytes("png")
        analyses: list[PageRouteAnalysis] = []
        for index, page in enumerate(document):
            try:
                markdown = convert_page(_page_pdf_bytes(document, index))
            except AtlasParseError:
                markdown = ""
            analysis = _analyze_page(
                page,
                index + 1,
                markdown,
                min_text_chars=min_text_chars,
                min_money_values=min_money_values,
                min_financial_anchors=min_financial_anchors,
                max_large_image_ratio=max_large_image_ratio,
            )
            analyses.append(analysis)
    finally:
        document.close()

    fallback = next((analysis for analysis in analyses if analysis.route == "vision_llm"), None)
    if fallback:
        return PdfRouteDecision("vision_llm", f"page_{fallback.page}:{fallback.reason}", tuple(analyses), preview)
    return PdfRouteDecision("markitdown_text_llm", "all_pages_passed", tuple(analyses), preview)


def _call_text_model(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    markdown: str,
) -> dict[str, Any]:
    prompt = (
        f"{EXTRACTION_PROMPT}\n"
        "The PDF page was converted to Markdown by MarkItDown. Extract only from the Markdown below.\n\n"
        f"--- BEGIN MARKDOWN ---\n{markdown}\n--- END MARKDOWN ---"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
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
            response = post_json_with_retry(
                client,
                f"{base_url}/chat/completions",
                headers=headers,
                payload={key: value for key, value in payload.items() if key != "response_format"},
            )
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as error:
        raise AtlasParseError(f"Atlas Cloud text request failed with HTTP {error.response.status_code}.") from error
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise AtlasParseError("Atlas Cloud text request failed before a valid response was received.") from error
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


def _parse_markdown_pages(
    decision: PdfRouteDecision,
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
    call_text_model: Callable[[httpx.Client, str, str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds) as client:
        normalized_pages = [
            _normalize_page(
                call_text_model(client, base_url, api_key, model, analysis.markdown),
                analysis.page,
                model,
            )
            for analysis in decision.pages
        ]
    result = apply_extraction_quality_gate(_assemble(normalized_pages, len(normalized_pages), model))
    result["extraction_method"] = "atlas_text_markitdown"
    result["pages"] = [
        {"page": analysis.page, "text": analysis.markdown, "method": "markitdown", "model": model}
        for analysis in decision.pages
    ]
    return result


def parse_pdf_with_markitdown_router(
    pdf_bytes: bytes,
    *,
    api_key: str,
    base_url: str,
    text_model: str,
    primary_model: str,
    fallback_model: str,
    max_pages: int,
    timeout_seconds: float = 90,
    min_confidence: float = 0.85,
    render_scale: float = 2.0,
    max_render_dimension: int = 3000,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
    convert_page: Callable[[bytes], str] = _convert_page_with_markitdown,
    call_text_model: Callable[[httpx.Client, str, str, str, str], dict[str, Any]] = _call_text_model,
    parse_vision: Callable[..., tuple[dict[str, Any], bytes | None]] = parse_pdf_with_atlas,
) -> tuple[dict[str, Any], bytes | None]:
    if not api_key:
        raise AtlasParseError("Atlas Cloud API key is not configured.")

    decision = decide_pdf_route(
        pdf_bytes,
        max_pages,
        convert_page=convert_page,
        max_render_dimension=max_render_dimension,
        max_xref_objects=max_xref_objects,
        max_page_dimension=max_page_dimension,
    )

    def vision(reason: str, text_attempt: dict[str, Any] | None = None) -> tuple[dict[str, Any], bytes | None]:
        result, preview = parse_vision(
            pdf_bytes,
            api_key=api_key,
            base_url=base_url,
            primary_model=primary_model,
            fallback_model=fallback_model,
            max_pages=max_pages,
            timeout_seconds=timeout_seconds,
            min_confidence=min_confidence,
            render_scale=render_scale,
            max_render_dimension=max_render_dimension,
            max_xref_objects=max_xref_objects,
            max_page_dimension=max_page_dimension,
        )
        text_usage = text_attempt.get("provider_usage", {}) if text_attempt else {}
        vision_usage = result.get("provider_usage", {}) if isinstance(result.get("provider_usage"), dict) else {}
        pipeline_usage = {
            key: int(text_usage.get(key) or 0) + int(vision_usage.get(key) or 0)
            for key in ("input_tokens", "output_tokens", "total_tokens", "calls")
        }
        result["routing"] = {
            "selected": "vision_llm",
            "reason": reason,
            "text_attempt_usage": text_usage or None,
            "pipeline_usage": pipeline_usage,
            "pages": [{key: value for key, value in asdict(page).items() if key != "markdown"} for page in decision.pages],
        }
        return result, preview

    if decision.route == "vision_llm":
        return vision(decision.reason)

    try:
        text_result = _parse_markdown_pages(
            decision,
            api_key=api_key,
            base_url=base_url,
            model=text_model,
            timeout_seconds=timeout_seconds,
            call_text_model=call_text_model,
        )
    except AtlasParseError:
        return vision("text_model_request_failed")

    if _fallback_reasons(text_result, min_confidence):
        return vision("text_result_failed_quality_gate", text_result)

    text_result["routing"] = {
        "selected": "markitdown_text_llm",
        "reason": decision.reason,
        "pages": [{key: value for key, value in asdict(page).items() if key != "markdown"} for page in decision.pages],
    }
    return text_result, decision.preview
