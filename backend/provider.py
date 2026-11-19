from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def post_json_with_retry(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    last_response: httpx.Response | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = client.post(url, headers=headers, json=payload)
        except httpx.RequestError:
            if attempt == attempts - 1:
                raise
            sleep(min(2**attempt, 8))
            continue
        last_response = response
        if response.status_code not in RETRYABLE_STATUS_CODES or attempt == attempts - 1:
            response.raise_for_status()
            return response
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = max(0.0, min(float(retry_after), 15.0))
        except ValueError:
            delay = min(2**attempt, 8)
        sleep(delay)
    if last_response is None:  # pragma: no cover - loop always executes
        raise RuntimeError("Provider request did not execute.")
    last_response.raise_for_status()
    return last_response
