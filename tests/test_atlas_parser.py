import io

import httpx
import pymupdf
from PIL import Image

from backend.atlas_parser import AtlasParseError, _call_model, parse_pdf_with_atlas
from backend.sample import create_sample_pdf


def _good_payload(merchant: str = "CEDAR & FINCH KITCHEN"):
    def field(value, confidence=0.96, evidence=None):
        return {"value": value, "confidence": confidence, "evidence": evidence or str(value)}

    return {
        "merchant": field(merchant),
        "date": field("2026-08-18"),
        "currency": field("USD"),
        "receipt_number": field("CF-1842"),
        "card_last4": field("1828"),
        "gross_amount": field(25.0),
        "discount": field(0.0),
        "refund": field(0.0),
        "subtotal": field(25.0),
        "tax": field(2.06),
        "tip": field(0.0),
        "total": field(27.06),
        "payment_method": field("VISA"),
        "items": [
            {
                "description": "Grilled Chicken Bowl",
                "quantity": 1,
                "unit_price": 18.0,
                "amount": 18.0,
                "confidence": 0.96,
                "evidence": "Grilled Chicken Bowl 18.00",
            },
            {
                "description": "House Lemonade",
                "quantity": 1,
                "unit_price": 7.0,
                "amount": 7.0,
                "confidence": 0.96,
                "evidence": "House Lemonade 7.00",
            },
        ],
        "raw_text": "CEDAR & FINCH KITCHEN\nTotal USD 27.06",
    }


def _parse(call_model, min_confidence=0.85):
    return parse_pdf_with_atlas(
        create_sample_pdf(),
        api_key="test-key",
        base_url="https://api.atlascloud.ai/v1",
        primary_model="qwen/qwen3.5-35b-a3b",
        fallback_model="qwen/qwen3-vl-235b-a22b-thinking",
        max_pages=30,
        min_confidence=min_confidence,
        call_model=call_model,
    )


def test_primary_atlas_model_preserves_result_contract():
    models = []

    def call_model(_client, _base_url, _api_key, model, image):
        models.append(model)
        assert image.startswith(b"\x89PNG")
        return _good_payload()

    result, preview = _parse(call_model)

    assert models == ["qwen/qwen3.5-35b-a3b"]
    assert result["extraction_method"] == "atlas_qwen3_vl"
    assert result["extraction_model"] == "qwen/qwen3.5-35b-a3b"
    assert result["fields"]["total"]["value"] == 27.06
    assert result["fields"]["card_last4"]["value"] == "1828"
    assert result["fields"]["discount"]["value"] == 0.0
    assert result["fields"]["total"]["source"]["bbox"] is None
    assert result["reconciliation"] == {"matched": True, "difference": -0.0}
    assert [item["description"] for item in result["items"]] == ["Grilled Chicken Bowl", "House Lemonade"]
    assert result["quality_gate"] == {
        "fallback_triggered": False,
        "fallback_reasons": [],
        "decision": "accept",
        "selected_model": "qwen/qwen3.5-35b-a3b",
    }
    assert result["provider_usage"] == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 1}
    assert preview and preview.startswith(b"\x89PNG")


def test_low_quality_primary_result_is_routed_to_verification_without_second_qwen_call():
    models = []

    def call_model(_client, _base_url, _api_key, model, _image):
        models.append(model)
        if model.endswith("35b-a3b"):
            return {
                "merchant": {"value": None, "confidence": 0, "evidence": None},
                "items": [],
                "raw_text": "blurred",
            }
        return _good_payload("FALLBACK CAFE")

    result, _ = _parse(call_model)

    assert models == ["qwen/qwen3.5-35b-a3b"]
    assert result["extraction_model"] == "qwen/qwen3.5-35b-a3b"
    assert result["fields"]["merchant"]["value"] is None
    assert result["quality_gate"]["fallback_triggered"] is False
    assert result["quality_gate"]["decision"] == "verify"
    assert {"merchant_missing", "total_missing", "items_missing"} <= set(result["quality_gate"]["fallback_reasons"])


def test_primary_request_error_also_uses_larger_model():
    models = []

    def call_model(_client, _base_url, _api_key, model, _image):
        models.append(model)
        if model.endswith("35b-a3b"):
            raise AtlasParseError("primary unavailable")
        return _good_payload()

    result, _ = _parse(call_model)

    assert models == ["qwen/qwen3.5-35b-a3b", "qwen/qwen3-vl-235b-a22b-thinking"]
    assert result["fields"]["total"]["value"] == 27.06
    assert result["quality_gate"]["fallback_reasons"] == ["primary_request_error"]
    assert result["quality_gate"]["decision"] == "verify"


def test_tip_is_included_in_reconciliation():
    def call_model(_client, _base_url, _api_key, _model, _image):
        payload = _good_payload()
        payload["subtotal"] = {"value": 25.0, "confidence": 0.96, "evidence": "Subtotal 25.00"}
        payload["tax"] = {"value": 2.0, "confidence": 0.96, "evidence": "Tax 2.00"}
        payload["tip"] = {"value": 5.0, "confidence": 0.96, "evidence": "Tip 5.00"}
        payload["total"] = {"value": 32.0, "confidence": 0.96, "evidence": "Total 32.00"}
        return payload

    result, _ = _parse(call_model)

    assert result["fields"]["tip"]["value"] == 5.0
    assert result["reconciliation"] == {"matched": True, "difference": 0.0}


def test_oversized_pdf_page_is_capped_before_model_request():
    document = pymupdf.open()
    page = document.new_page(width=1200, height=1800)
    page.insert_text((72, 72), "TOTAL 27.06")
    pdf_bytes = document.tobytes()
    document.close()
    observed_dimensions = []

    def call_model(_client, _base_url, _api_key, _model, image):
        with Image.open(io.BytesIO(image)) as rendered:
            observed_dimensions.append(rendered.size)
        return _good_payload()

    parse_pdf_with_atlas(
        pdf_bytes,
        api_key="test-key",
        base_url="https://api.atlascloud.ai/v1",
        primary_model="qwen/qwen3.5-35b-a3b",
        fallback_model="qwen/qwen3-vl-235b-a22b-thinking",
        max_pages=1,
        render_scale=2.0,
        max_render_dimension=3000,
        call_model=call_model,
    )

    assert observed_dimensions == [(2000, 3000)]


def test_model_retries_without_response_format_when_provider_rejects_it():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        requests.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"code": 400, "msg": "bad request"}, request=request)
        return httpx.Response(
            200,
            json={
                "id": "compatible-request",
                "choices": [{"message": {"content": __import__("json").dumps(_good_payload())}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _call_model(client, "https://atlas.test/v1", "secret", "fallback-model", b"png")

    assert len(requests) == 2
    assert "response_format" in requests[0]
    assert "response_format" not in requests[1]
    assert result["__receiptsift_meta"]["usage"]["total_tokens"] == 30
