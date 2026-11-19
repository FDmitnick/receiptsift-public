from scripts.benchmark_receipts_50 import _money, _prices_from_models, _score


def test_benchmark_understands_cord_thousands_separators():
    assert _money("23.000") == 23000.0
    assert _money("45,500") == 45500.0
    assert _money("12.50") == 12.5


def test_provider_pricing_is_converted_from_per_token_to_per_million():
    defaults = {"model-a": (1.0, 2.0), "model-b": (3.0, 4.0)}
    prices = _prices_from_models(
        [{"id": "model-a", "pricing": {"prompt": "0.0000025", "completion": "0.000015"}}],
        defaults,
    )

    assert prices == {"model-a": (2.5, 15.0), "model-b": (3.0, 4.0)}


def test_benchmark_scores_total_and_line_items_independently():
    expected = {
        "total": 12.5,
        "items": [
            {"description": "Iced Coffee", "amount": 7.5},
            {"description": "Bagel", "amount": 5.0},
        ],
    }
    observed = [
        {"description": "ICED COFFEE", "amount": 7.5},
        {"description": "Bagel", "amount": 5.0},
    ]

    score = _score(expected, {"total": 12.5}, observed)

    assert score["total_match"] is True
    assert score["items"]["f1"] == 1.0
    assert score["document_correct"] is True
