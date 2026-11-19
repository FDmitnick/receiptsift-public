from io import BytesIO

import pymupdf
from PIL import Image

from backend.markitdown_router import decide_pdf_route, parse_pdf_with_markitdown_router
from backend.sample import create_sample_pdf

GOOD_MARKDOWN = """# CEDAR & FINCH KITCHEN

Date: 2026-08-18
Receipt No: CF-1842
Currency: USD

| Item | Amount |
|---|---:|
| Grilled Chicken Bowl | $18.00 |
| House Lemonade | $7.00 |

Subtotal $25.00
Tax $2.06
Tip $0.00
Total $27.06
Payment VISA
"""


def good_payload():
    def field(value, evidence):
        return {"value": value, "confidence": 0.98, "evidence": evidence}

    return {
        "merchant": field("CEDAR & FINCH KITCHEN", "CEDAR & FINCH KITCHEN"),
        "date": field("2026-08-18", "Date: 2026-08-18"),
        "currency": field("USD", "Currency: USD"),
        "receipt_number": field("CF-1842", "Receipt No: CF-1842"),
        "subtotal": field(25.0, "Subtotal $25.00"),
        "tax": field(2.06, "Tax $2.06"),
        "tip": field(0.0, "Tip $0.00"),
        "total": field(27.06, "Total $27.06"),
        "payment_method": field("VISA", "Payment VISA"),
        "items": [
            {
                "description": "Grilled Chicken Bowl",
                "quantity": 1,
                "unit_price": 18,
                "amount": 18,
                "confidence": 0.98,
                "evidence": "Grilled Chicken Bowl $18.00",
            },
            {
                "description": "House Lemonade",
                "quantity": 1,
                "unit_price": 7,
                "amount": 7,
                "confidence": 0.98,
                "evidence": "House Lemonade $7.00",
            },
        ],
        "raw_text": GOOD_MARKDOWN,
    }


def image_pdf_with_embedded_text() -> bytes:
    image = Image.new("RGB", (900, 1100), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    document = pymupdf.open()
    page = document.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=buffer.getvalue())
    page.insert_text((40, 40), "TOTAL $27.06 SUBTOTAL $25.00 TAX $2.06 PAYMENT VISA ACCOUNT 123")
    pdf = document.tobytes()
    document.close()
    return pdf


def vision_result(*_args, **_kwargs):
    return (
        {
            "status": "ready",
            "page_count": 1,
            "extraction_method": "atlas_qwen3_vl",
            "overall_confidence": 0.98,
            "fields": {},
            "items": [],
            "reconciliation": {"matched": True, "difference": 0.0},
            "warnings": [],
            "pages": [],
        },
        b"vision-preview",
    )


def test_native_financial_markdown_uses_text_model_without_vision():
    calls = []

    def call_text(_client, _base_url, _api_key, model, markdown):
        calls.append((model, markdown))
        return good_payload()

    def fail_vision(*_args, **_kwargs):
        raise AssertionError("Vision should not be called for a safe native-text PDF")

    result, preview = parse_pdf_with_markitdown_router(
        create_sample_pdf(),
        api_key="test-key",
        base_url="https://example.test/v1",
        text_model="text-model",
        primary_model="text-model",
        fallback_model="vision-model",
        max_pages=30,
        convert_page=lambda _pdf: GOOD_MARKDOWN,
        call_text_model=call_text,
        parse_vision=fail_vision,
    )

    assert calls == [("text-model", GOOD_MARKDOWN)]
    assert result["extraction_method"] == "atlas_text_markitdown"
    assert result["routing"]["selected"] == "markitdown_text_llm"
    assert result["fields"]["total"]["value"] == 27.06
    assert preview and preview.startswith(b"\x89PNG")


def test_empty_markdown_routes_directly_to_vision():
    result, preview = parse_pdf_with_markitdown_router(
        image_pdf_with_embedded_text(),
        api_key="test-key",
        base_url="https://example.test/v1",
        text_model="text-model",
        primary_model="text-model",
        fallback_model="vision-model",
        max_pages=30,
        convert_page=lambda _pdf: "",
        call_text_model=lambda *_args: (_ for _ in ()).throw(AssertionError("Text model should not be called")),
        parse_vision=vision_result,
    )

    assert result["routing"]["selected"] == "vision_llm"
    assert "insufficient_markdown_text" in result["routing"]["reason"]
    assert preview == b"vision-preview"


def test_large_embedded_image_forces_vision_even_when_text_looks_complete():
    decision = decide_pdf_route(
        image_pdf_with_embedded_text(),
        30,
        convert_page=lambda _pdf: GOOD_MARKDOWN,
    )

    assert decision.route == "vision_llm"
    assert decision.pages[0].reason == "hybrid_pdf_large_image"
    assert decision.pages[0].largest_image_ratio >= 0.9


def test_bad_text_model_result_falls_back_to_vision():
    incomplete = good_payload()
    incomplete["total"] = {"value": None, "confidence": 0, "evidence": None}

    result, _ = parse_pdf_with_markitdown_router(
        create_sample_pdf(),
        api_key="test-key",
        base_url="https://example.test/v1",
        text_model="text-model",
        primary_model="text-model",
        fallback_model="vision-model",
        max_pages=30,
        convert_page=lambda _pdf: GOOD_MARKDOWN,
        call_text_model=lambda *_args: incomplete,
        parse_vision=vision_result,
    )

    assert result["routing"]["selected"] == "vision_llm"
    assert result["routing"]["reason"] == "text_result_failed_quality_gate"
    assert result["routing"]["text_attempt_usage"]["calls"] == 1
    assert result["routing"]["pipeline_usage"]["calls"] == 1
