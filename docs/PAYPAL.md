# PayPal subscriptions preparation

This module is deliberately isolated from the in-progress account implementation. It is ready to attach after the account layer exposes two callables:

- `require_user(request) -> {"id": ..., "email": ...}`
- `usage_for_user(user_id) -> {"documents_parsed": ..., "pages_processed": ...}`

## Draft commercial rules

All values are environment-driven. The checked-in defaults are only a beta proposal:

| Plan | Monthly price | PDF documents | Monthly pages | Per-file pages | Overage |
| --- | ---: | ---: | ---: | ---: | --- |
| Free | $0 | 2 | 10 | 5 | Hard stop |
| Pro | $9 USD | 300 | 500 | 30 | Hard stop |

Document and page allowances are independent hard limits. Each accepted upload consumes one document plus its actual
page count; processing pauses as soon as either monthly allowance is exhausted. There are no automatic overage fees.

Do not create the live PayPal plan until the owner confirms price and quota. Existing subscribers should never be moved to a different price silently.

## Modules

- `backend/billing.py`: configuration, quota decisions, PayPal OAuth/API client, product/plan/webhook setup calls
- `backend/billing_repository.py`: subscription state and webhook idempotency tables
- `backend/billing_router.py`: config, current entitlement, approval, cancellation, and verified webhook endpoints
- `scripts/setup_paypal.py`: one-time sandbox product, plan, and webhook creation
- `.env.paypal.example`: the complete variable contract

## Safe credential handling

The PayPal Client ID is intended for the JavaScript SDK and may be returned by `/api/billing/config`. The Client Secret must exist only in Railway service variables or a local ignored environment file. Do not commit it, put it in browser JavaScript, paste it into an issue, or send it through chat.

Required server variables:

```text
PAYPAL_ENVIRONMENT=sandbox
PAYPAL_CLIENT_ID=<sandbox client id>
PAYPAL_CLIENT_SECRET=<sandbox secret>
PAYPAL_PLUS_PLAN_ID=<generated plan id>
PAYPAL_PRO_PLAN_ID=<generated plan id>
PAYPAL_WEBHOOK_ID=<generated webhook id>
```

The current PayPal dashboard app label is `PDF transfer`. Rename the live-facing display name to `ReceiptSift` before launch so the approval screen matches the product users selected. This does not change the API Client ID.

## One-time sandbox setup

1. Put the sandbox Client ID and Secret in the current shell or an ignored local environment file.
2. Set `PAYPAL_WEBHOOK_URL=https://<temporary-or-app-domain>/api/billing/paypal/webhook`.
3. Confirm the draft price and quota variables.
4. Run:

```powershell
.\.venv\Scripts\python.exe scripts\setup_paypal.py
```

5. Copy only the generated Product, Plan, and Webhook IDs to Railway variables. The script never prints the secret.

## Account integration point

After the account work is complete, initialize and mount the router once:

```python
from backend.billing_router import build_billing_router

app.include_router(
    build_billing_router(
        database_path=settings.database_path,
        require_user=_require_user,
        usage_for_user=repository.usage,
    )
)
```

Before calling the PDF parser, calculate the account entitlement and call `BillingRepository.reserve_document` with a unique request ID, the detected PDF page count, and the account's document/page limits. It uses an immediate SQLite transaction and a short-lived reservation so concurrent uploads cannot pass the same final quota slot. Return HTTP `429` with code `monthly_limit_reached` when the reservation fails. Release the reservation after the document usage event is committed, and also release it on parse failure. Never rely on a disabled browser button for quota enforcement.

Free, Plus, and Pro use the same extraction and OCR quality. Free is restricted by quantity, not by a lower-quality parser. Plus is $9/month for 100 PDFs and 200 pages, with up to 15 pages per PDF and 25 PDFs per batch. Pro is $19/month for 300 PDFs and 500 pages, with up to 30 pages per PDF and 100 PDFs per batch. Failed parses do not consume an allowance; each successful parse records one aggregate document event, its page count, and a content-free parse-order record. Recent receipt content is encrypted for up to 7 days, and deleting or leaving the result does not restore the allowance.

## Free-plan abuse controls

`backend/abuse.py` prepares the account-side controls without modifying the in-progress login implementation:

- Require a verified email before granting Free usage. New email/password accounts now satisfy this after following a single-use verification link.
- Use an HMAC with `ABUSE_HASH_SECRET` to store pseudonymous identity and network keys; never store raw IP addresses in abuse tables.
- Allow at most three registrations from one network in 24 hours, requiring a CAPTCHA-style challenge from the second attempt.
- Limit authenticated upload bursts separately from the monthly allowance.
- Keep a pseudonymous Free identity claim for 31 days so deleting and immediately recreating an account does not reset the allowance.
- Purge rate-limit events and identity claims after 35 days.

The IP/network signal must remain a soft risk signal because households, offices, schools, and VPNs can legitimately share an address. The hard commercial boundary is the verified account's server-side document/page quota. Add the pseudonymous retention behavior to the public privacy notice before enabling it.

## Browser checkout contract

The pricing page should load the PayPal JavaScript SDK with:

```text
client-id=<PAYPAL_CLIENT_ID>&components=buttons&vault=true&intent=subscription
```

Create the subscription with either the configured `PAYPAL_PLUS_PLAN_ID` or `PAYPAL_PRO_PLAN_ID` and the authenticated ReceiptSift user ID as `custom_id`. After approval, send the returned `subscriptionID` to `/api/billing/paypal/approve`. The backend retrieves the subscription from PayPal, validates the exact plan and owner, and records the provider mapping. Webhooks only update a mapping that has already passed this authenticated approval step, and paid entitlement is granted only when PayPal reports `ACTIVE`.

## Webhook events

The setup subscribes to subscription activation, update, suspension, cancellation, and expiration, plus completed, denied, and refunded sales. Every webhook must pass PayPal signature verification before changing subscription state. Event IDs are stored so retries are idempotent.

Completed subscription-sale events are also stored as payment rows for the owner operations console. Refunds are never automatic: only the single account configured by `RECEIPTSIFT_ADMIN_EMAIL` can select a recorded payment, choose a full or partial amount, enter a reason, and type `REFUND`. The server validates the remaining refundable balance before calling PayPal and writes the result to both the refund ledger and owner audit trail. Cancelling a subscription is a separate, explicitly confirmed action and does not refund past payments.

Account deletion reads the user's local subscription mapping first. For any state other than `CANCELLED` or `EXPIRED`, ReceiptSift calls PayPal's subscription cancellation endpoint before deleting local account data. A PayPal error fails closed: the account, receipts, and billing mapping remain so the customer cannot accidentally keep paying for a deleted account.

## Launch TODO

- [ ] Complete one end-to-end PayPal Sandbox subscription payment. It passes only when the sandbox buyer approves Pro, `/api/billing/paypal/approve` attaches the subscription to the same ReceiptSift account, the entitlement becomes `ACTIVE`, the account page shows Pro, and a third PDF upload succeeds.

## Sandbox acceptance checklist

- Free account is blocked on the next upload after its monthly limit.
- Sandbox buyer can approve the Pro subscription.
- A forged subscription ID cannot upgrade a different user.
- Pro activates only after PayPal reports `ACTIVE`.
- Cancellation and suspension remove Pro access through a verified webhook.
- Replayed webhooks do not duplicate state changes.
- PayPal outage fails closed and does not grant Pro.
- The Client Secret never appears in HTML, JSON configuration, logs, Git, or screenshots.

Only after every item passes should the same resource-creation flow be repeated with live credentials.
