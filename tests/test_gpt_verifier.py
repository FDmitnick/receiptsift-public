from backend.gpt_verifier import verify_receipt_with_gpt


def test_gpt_verifier_normalizes_independent_result_and_usage():
    def call_model(_client, _base_url, _api_key, model, images, extraction):
        assert model == "openai/gpt-5.6-terra"
        assert images == [b"png"]
        assert extraction["fields"]["total"]["value"] == 12.5
        return {
            "document_type": "receipt",
            "verdict": "corrected",
            "confidence": 0.91,
            "independent": {
                "merchant": "CAFE",
                "date": None,
                "currency": "USD",
                "subtotal": "10.00",
                "tax": "2.50",
                "tip": None,
                "total": "$12.50",
                "items": [{"description": "Coffee", "quantity": 1, "unit_price": "10", "amount": "10"}],
            },
            "discrepancies": [{"field": "tax", "candidate": None, "observed": 2.5, "severity": "high"}],
            "notes": [],
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "calls": 1},
        }

    verified = verify_receipt_with_gpt(
        [b"png"],
        {"fields": {"total": {"value": 12.5}}, "items": []},
        api_key="test",
        base_url="https://api.atlascloud.ai/v1",
        call_model=call_model,
    )

    assert verified["verdict"] == "corrected"
    assert verified["independent"]["total"] == 12.5
    assert verified["independent"]["items"][0]["unit_price"] == 10.0
    assert verified["usage"]["total_tokens"] == 150
