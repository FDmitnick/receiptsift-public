import httpx

from backend.provider import post_json_with_retry


def test_provider_retries_rate_limit_and_honors_retry_after():
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}, request=httpx.Request("POST", "https://example.test")),
        httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", "https://example.test")),
    ]
    sleeps = []

    class Client:
        def post(self, *_args, **_kwargs):
            return responses.pop(0)

    response = post_json_with_retry(
        Client(),  # type: ignore[arg-type]
        "https://example.test",
        headers={},
        payload={},
        sleep=sleeps.append,
    )

    assert response.status_code == 200
    assert sleeps == [0.0]


def test_provider_retries_transport_errors():
    request = httpx.Request("POST", "https://example.test")
    responses = [httpx.ConnectError("temporary failure", request=request), httpx.Response(200, request=request)]
    sleeps = []

    class Client:
        def post(self, *_args, **_kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    response = post_json_with_retry(
        Client(),  # type: ignore[arg-type]
        "https://example.test",
        headers={},
        payload={},
        sleep=sleeps.append,
    )

    assert response.status_code == 200
    assert sleeps == [1]
