from io import BytesIO

import pymupdf
import pytest
from PIL import Image, ImageDraw

from backend.parser import PdfParseError, locate_result_sources, ocr_available, parse_pdf
from backend.sample import create_sample_pdf


def test_sample_pdf_extracts_core_fields_and_line_items():
    result, preview = parse_pdf(create_sample_pdf())

    assert result["status"] == "ready"
    assert result["extraction_method"] == "embedded_text"
    assert result["fields"]["merchant"]["value"] == "CEDAR & FINCH KITCHEN"
    assert result["fields"]["date"]["value"] == "2026-08-18"
    assert result["fields"]["receipt_number"]["value"] == "CF-1842"
    assert result["fields"]["currency"]["value"] == "USD"
    assert result["fields"]["subtotal"]["value"] == 25.0
    assert result["fields"]["tax"]["value"] == 2.06
    assert result["fields"]["tip"]["value"] == 0.0
    assert result["fields"]["total"]["value"] == 27.06
    assert result["fields"]["payment_method"]["value"] == "VISA"
    assert [item["description"] for item in result["items"]] == ["Grilled Chicken Bowl", "House Lemonade"]
    assert result["reconciliation"] == {"matched": True, "difference": -0.0}
    assert result["warnings"] == []
    assert preview and preview.startswith(b"\x89PNG")


def test_sources_are_normalized_to_first_page():
    result, _ = parse_pdf(create_sample_pdf())
    source = result["fields"]["total"]["source"]

    assert source["page"] == 1
    assert source["text"] == "Total USD 27.06"
    assert all(0 <= coordinate <= 1 for coordinate in source["bbox"])


def test_atlas_evidence_is_located_on_the_source_pdf():
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 120), "Payments received -94.18", fontsize=14)
    page.insert_text((72, 160), "Credits applied -1.30", fontsize=14)
    pdf_bytes = document.tobytes()
    document.close()
    result = {
        "fields": {
            "payments": {"value": -94.18, "confidence": 0.94, "source": {"page": 1, "bbox": None, "text": "Payments -94.18"}},
            "credits": {"value": -1.3, "confidence": 0.94, "source": {"page": 1, "bbox": None, "text": "Credits -1.30"}},
        },
        "items": [],
    }

    assert locate_result_sources(pdf_bytes, result) == 2
    payments_box = result["fields"]["payments"]["source"]["bbox"]
    credits_box = result["fields"]["credits"]["source"]["bbox"]
    assert all(0 <= coordinate <= 1 for coordinate in payments_box)
    assert all(0 <= coordinate <= 1 for coordinate in credits_box)
    assert payments_box[1] < credits_box[1]


def test_ambiguous_bare_evidence_is_not_boxed():
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 120), "Previous balance 94.18", fontsize=14)
    page.insert_text((72, 160), "Amount due 94.18", fontsize=14)
    pdf_bytes = document.tobytes()
    document.close()
    result = {
        "fields": {
            "total": {"value": 94.18, "confidence": 0.7, "source": {"page": 1, "bbox": None, "text": "94.18"}},
        },
        "items": [],
    }

    assert locate_result_sources(pdf_bytes, result) == 0
    assert result["fields"]["total"]["source"]["bbox"] is None


def test_image_only_pdf_uses_local_ocr():
    assert ocr_available()
    image = Image.new("RGB", (1000, 1200), "white")
    draw = ImageDraw.Draw(image)
    lines = [
        "ACME SCAN STORE",
        "Receipt No: SCAN-101",
        "Date: 2026-08-21",
        "Coffee 1 x 12.00 12.00",
        "Subtotal 12.00",
        "Tax 0.96",
        "Total USD 12.96",
        "Payment: VISA",
    ]
    for index, line in enumerate(lines):
        draw.text((80, 80 + index * 110), line, fill="black", font_size=48)
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    document = pymupdf.open()
    page = document.new_page(width=500, height=600)
    page.insert_image(page.rect, stream=image_bytes.getvalue())
    pdf_bytes = document.tobytes()
    document.close()

    result, _ = parse_pdf(pdf_bytes)

    assert result["extraction_method"] == "ocr"
    assert result["fields"]["merchant"]["value"] == "ACME SCAN STORE"
    assert result["fields"]["date"]["value"] == "2026-08-21"
    assert result["fields"]["total"]["value"] == 12.96
    assert result["warnings"] == []


def test_pdf_with_embedded_file_is_rejected_before_parsing():
    document = pymupdf.open()
    document.new_page()
    document.embfile_add("payload.txt", b"not executed")
    pdf_bytes = document.tobytes()
    document.close()

    with pytest.raises(PdfParseError) as error:
        parse_pdf(pdf_bytes)

    assert error.value.code == "active_pdf_content"


def test_pdf_with_extreme_page_dimensions_is_rejected():
    document = pymupdf.open()
    document.new_page(width=20_000, height=500)
    pdf_bytes = document.tobytes()
    document.close()

    with pytest.raises(PdfParseError) as error:
        parse_pdf(pdf_bytes)

    assert error.value.code == "page_dimensions_exceeded"


def test_pdf_object_count_limit_is_enforced():
    with pytest.raises(PdfParseError) as error:
        parse_pdf(create_sample_pdf(), max_xref_objects=1)

    assert error.value.code == "pdf_too_complex"
