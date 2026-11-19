from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailSettings:
    api_key: str
    sender: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.sender)


class ResendMailer:
    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.configured

    def send(self, *, to: str, subject: str, text: str, html: str, idempotency_key: str) -> None:
        if not self.configured:
            raise EmailDeliveryError("Transactional email is not configured.")
        payload = json.dumps(
            {"from": self.settings.sender, "to": [to], "subject": subject, "text": text, "html": html},
            separators=(",", ":"),
        ).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key[:256],
                "User-Agent": "ReceiptSift/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise EmailDeliveryError("The email provider rejected the message.")
        except urllib.error.HTTPError as error:
            raise EmailDeliveryError("The email provider rejected the message.") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise EmailDeliveryError("The email provider could not be reached.") from error
