import json
from unittest.mock import patch

import pytest

from backend.email import EmailDeliveryError, EmailSettings, ResendMailer


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_resend_mailer_uses_server_key_and_idempotency_header():
    mailer = ResendMailer(EmailSettings("re_secret", "ReceiptSift <accounts@example.com>"))

    with patch("urllib.request.urlopen", return_value=Response()) as urlopen:
        mailer.send(
            to="owner@example.com",
            subject="Verify",
            text="plain",
            html="<p>plain</p>",
            idempotency_key="verification-1",
        )

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer re_secret"
    assert request.headers["Idempotency-key"] == "verification-1"
    assert payload["to"] == ["owner@example.com"]
    assert "re_secret" not in request.data.decode()


def test_unconfigured_mailer_fails_closed():
    mailer = ResendMailer(EmailSettings("", ""))

    with pytest.raises(EmailDeliveryError):
        mailer.send(to="owner@example.com", subject="Verify", text="plain", html="<p>plain</p>", idempotency_key="x")
