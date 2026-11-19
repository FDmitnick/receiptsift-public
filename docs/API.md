# API reference

Base URL: `http://127.0.0.1:4317` · OpenAPI UI: `/api/docs` · OpenAPI JSON: `/api/openapi.json`

Hosted `/api/v1/*`, `/api/admin/*`, and OpenAPI routes require the signed account cookie. All API responses use `Cache-Control: no-store`.

Errors use:

```json
{"error":{"code":"not_pdf","message":"Only valid PDF files are accepted."}}
```

## Authentication

- `POST /api/auth/register`: email and a password of at least 12 characters; opens only when transactional email is ready
- `POST /api/auth/login`: create a signed HTTP-only session
- `POST /api/auth/logout`: clear the session
- `POST /api/auth/verification/resend`: request another verification email
- `GET /verify-email?token=...`: consume a 24-hour single-use verification token
- `POST /api/auth/password/forgot`: generic password-recovery response
- `POST /api/auth/password/reset`: consume a single-use reset token and invalidate prior sessions

Passwords are stored as Argon2id hashes. Verification and reset tokens are stored only as hashes.

## Health

`GET /api/health`

```json
{
  "status": "ok",
  "ocr_available": true,
  "max_upload_mb": 20,
  "max_pages": 30,
  "source_pdf_retained": false,
  "structured_result_retained": false,
  "preview_retained": false,
  "retention_days": 7,
  "document_storage_enabled": true,
  "parse_audit_metadata_retained": true,
  "diagnostic_reporting_available": true,
  "diagnostic_retention_days": 14,
  "diagnostic_evidence_requires_consent": true,
  "access_protected": true,
  "daily_ai_budget_guard_enabled": true,
  "auth_rate_limit_scope": "single_replica_memory",
  "pdf_active_content_rejected": true,
  "pdf_structure_limits_enabled": true,
  "parser_provider": "local",
  "atlas_primary_model": null,
  "atlas_fallback_model": null,
  "gpt_verifier_enabled": false,
  "gpt_verifier_model": null,
  "batch_workspace_available": true,
  "batch_database": "postgresql",
  "batch_object_store": "s3",
  "batch_worker_mode": "separate",
  "batch_source_retention_days": 7,
  "batch_result_retention_days": 7
}
```

## Account and usage

- `GET /api/v1/account`: signed-in account profile
- `GET /api/v1/account/usage`: monthly receipt count, page count, CSV export count, and `document_storage_enabled: false`
- `POST /api/v1/account/usage/csv-export`: record one aggregate browser-side CSV export; no receipt content is sent
- `GET /api/v1/account/export.json`: account profile, billing state, aggregate usage, parse-order metadata, diagnostic-case metadata, and retained batch results
- `DELETE /api/v1/account`: password-confirmed deletion; an active PayPal subscription must cancel first

## Batch workspace

- `POST /api/v1/batches`: create an owned batch
- `GET /api/v1/batches`: list owned batches with pending-confirmation, queue, ready, review, and failure counts
- `GET /api/v1/batches/{id}`: read one owned batch and its documents
- `DELETE /api/v1/batches/{id}`: delete the batch, encrypted source objects, results, and review history
- `POST /api/v1/batches/{id}/documents/delete`: delete 1–100 selected owned documents in one request; validates the full selection and deletes none if one is processing
- `POST /api/v1/batches/{id}/documents`: upload multiple `files` fields; returns `202` with per-file accepted and rejected arrays
- `POST /api/v1/batches/{id}/start`: atomically move every pending-confirmation document into the worker queue
- `GET /api/v1/batches/{id}/export.csv`: generate one UTF-8 CSV row per batch document
- `GET /api/v1/batches/{id}/export-items.csv`: generate one UTF-8 CSV row per extracted line item
- `GET /api/v1/batches/{id}/export.json?mode=clean|detailed`: download versioned clean values or the evidence-rich result
- `GET /api/v1/batch-documents/{id}`: read one owned document result
- `DELETE /api/v1/batch-documents/{id}`: delete an individual pending, queued, ready, review, or failed document; returns `409` once processing has started
- `GET /api/v1/batch-documents/{id}/export.json?mode=clean|detailed`: download one retained document result
- `GET /api/v1/batch-documents/{id}/source.pdf`: decrypt an unexpired owned source PDF
- `PATCH /api/v1/batch-documents/{id}`: save reviewed fields and mark the result ready
- `POST /api/v1/batch-documents/{id}/retry`: requeue a failed or review result while its source is available

The upload route detects duplicates by SHA-256 within one batch and reports `duplicate_document` without rejecting unrelated
files. Upload stores accepted files as `staged`, without calling the parser or consuming parse quota. The user can remove
unwanted files and explicitly start the remaining set. Starting changes `staged` rows to `queued`; an embedded or separate
`BatchWorker` then claims queued rows and performs parsing outside the web request. A queued-file deletion races safely with
worker claiming: deletion wins before the claim, otherwise the API returns `document_processing`. Encrypted source PDFs expire
after 7 days by default. Reviewed structured data explicitly confirmed into the ledger remains until the user deletes it.

Batch document payloads expose real worker progress through `progress_stage`, `progress_percent`, `progress_detail`,
`processing_started_at`, and calculated `elapsed_seconds`. Queued documents include their global worker `queue_position` and,
when enough live or historical timing evidence exists, `estimated_start_seconds`. Processing documents similarly include
`estimated_remaining_seconds`. Estimates are derived from recent completed batch durations or the current task's elapsed time
and completed stage percentage; the API returns `null` while there is not enough evidence instead of inventing a duration.
`progress_stale=true` indicates that the current stage has taken materially longer than the observed baseline.

## Upload and parse

`POST /api/v1/documents` accepts `multipart/form-data` with one `file` field. The request is synchronous and returns `201 Created`.

```bash
curl -b receiptsift.cookies \
  -F "file=@receipt.pdf;type=application/pdf" \
  http://127.0.0.1:4317/api/v1/documents
```

`POST /api/v1/documents/sample` generates and parses the live sample through the same encrypted 7-day history path.

Every successful result includes `schema_version: "1.0"`, `document_type`, optional `document_subtype`, type-specific
`reconciliations[]`, and legacy-compatible `fields`. New clients should prefer `vendor_name`, `issue_date`, and
`document_number`; `merchant`, `date`, and `receipt_number` remain aliases. Successful single-document results are encrypted
and available through the owned document routes for up to 7 days. JSON and line-item CSV are generated on demand and are not
stored as separate export files.

Invoice results can also include `bill_to_name`, `bill_to_address`, `ship_to_name`, `ship_to_address`, and
`original_invoice_number`. Credit notes are represented as invoices with `document_subtype: "credit_note"`.

Successful response excerpt:

```json
{
  "id": "parse-order-id",
  "order_id": "parse-order-id",
  "filename": "receipt.pdf",
  "status": "ready",
  "page_count": 1,
  "extraction_method": "embedded_text",
  "overall_confidence": 0.937,
  "storage_mode": "recent_7d",
  "preview_url": null,
  "preview_data_url": "data:image/png;base64,...",
  "fields": {
    "tip": {"value": 0.0, "confidence": 0.65, "source": null},
    "total": {
      "value": 27.06,
      "confidence": 0.96,
      "source": {"page": 1, "bbox": [0.09, 0.52, 0.71, 0.55], "text": "Total USD 27.06"}
    }
  },
  "items": [],
  "reconciliation": {"matched": true, "difference": 0.0},
  "warnings": []
}
```

In Atlas mode, the response also includes `quality_gate` and `model_attempts`. A clean result includes `verification: {"status": "not_run", "reason": "quality_gate_passed"}`. A risky single-page result may include:

```json
{
  "status": "needs_review",
  "verification": {
    "status": "completed",
    "model": "openai/gpt-5.6-terra",
    "verdict": "corrected",
    "confidence": 0.94,
    "independent": {"total": 59.50, "items": []},
    "discrepancies": [
      {"field": "total", "severity": "high", "evidence": "TOTAL 59.50"}
    ]
  }
}
```

Verifier suggestions are advisory and are never applied automatically. `corrected`, `review`, verifier unavailability, and unsupported multi-page verification remain `needs_review`.

The ID is a persistent parse-order ID, not a stored-document key. The routine PDF, filename, extracted text, structured result, corrections, and preview are not written to application storage. The order ledger stores user/order IDs, timestamps, page count, parser version and method, status/error, duration, confidence, warning count, and SHA-256 input/output digests. When Atlas mode is enabled, `extraction_method` identifies the cloud vision path; an `_atlas_fallback` suffix means the request safely fell back to local extraction.

## Opt-in diagnostic cases

- `GET /api/v1/diagnostic-cases`: list the signed-in user's case metadata
- `POST /api/v1/diagnostic-cases`: explicitly submit encrypted evidence for one owned parse order
- `DELETE /api/v1/diagnostic-cases/{case_id}`: delete the user's case and encrypted evidence immediately

The create route accepts `multipart/form-data` fields `order_id`, `description`, `consent=true`, `original_result_json`, `corrected_result_json`, and optional original `file`. The server verifies order ownership, the original result digest, and, when attached, the PDF digest. A missing or invalid encryption key returns `503` and stores nothing. One case is allowed per parse order.

## Disabled persistence routes

For compatibility, `GET /api/v1/documents` returns an empty list and `storage_enabled: false`.

These legacy routes return HTTP `410` with code `document_storage_disabled`:

- `GET /api/v1/documents/{id}`
- `PATCH /api/v1/documents/{id}`
- `DELETE /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/preview`
- `GET /api/v1/documents/{id}/export.csv`

Corrections are saved into the encrypted 7-day result. UTF-8 CSV generation happens on demand and does not create a retained
export file.

## Billing

- `GET /api/billing/config`: public PayPal client and plan configuration
- `GET /api/billing/me`: subscription and entitlement state
- `POST /api/billing/paypal/approve`: validate and attach an approved subscription
- `POST /api/billing/paypal/cancel`: request cancellation
- `POST /api/billing/paypal/webhook`: PayPal callback with signature verification

## Analytics and owner operations

- `POST /api/events`: consented first-party allow-listed event
- `GET /api/admin/overview`: aggregate visitors, registrations, use, subscribers, and revenue
- `GET /api/admin/users`: user, plan, aggregate usage, and last activity
- `GET /api/admin/payments`: PayPal payment and refund list
- `GET /api/admin/events`: product event stream
- `GET /api/admin/audit`: high-risk action history
- `GET /api/admin/runtime`: aggregate AI spend, provider failures, token usage, parse failures, latency, HTTP/batch health, SQLite contention, and separate database/worker/application capacity assessments
- `GET /api/admin/diagnostic-cases`: metadata-only diagnostic queue
- `GET /api/admin/diagnostic-cases/{case_id}`: decrypt one case report and record an audit event
- `GET /api/admin/diagnostic-cases/{case_id}/source.pdf`: decrypt one source PDF and record an audit event
- `DELETE /api/admin/diagnostic-cases/{case_id}`: delete evidence and record an audit event
- `POST /api/admin/payments/{payment_id}/refund`: owner-confirmed refund requiring `REFUND` and the current owner password
- `POST /api/admin/subscriptions/{subscription_id}/cancel`: owner-confirmed cancellation requiring `CANCEL` and the current owner password

The operations API requires a valid session matching `RECEIPTSIFT_ADMIN_EMAIL`. Public analytics do not accept receipt content, filename, email, raw IP address, or browser fingerprint from the browser.

## Common parse errors

| HTTP | Code | Meaning |
| --- | --- | --- |
| `410` | `document_storage_disabled` | A legacy persistence route was requested |
| `413` | `file_too_large` | Upload exceeded the byte limit |
| `415` | `not_pdf` | Missing PDF signature |
| `422` | `invalid_pdf` | Parser could not open the file |
| `422` | `encrypted_pdf` | Password-protected PDF |
| `422` | `empty_pdf` | PDF has no pages |
| `422` | `too_many_pages` | PDF exceeded the plan/configured page limit |
| `422` | `active_pdf_content` | PDF contains an embedded file or active action |
| `422` | `pdf_too_complex` | PDF object graph exceeded the safety limit |
| `422` | `page_dimensions_exceeded` | A page has unsafe extreme dimensions |
| `429` | `monthly_limit_reached` | Account allowance is exhausted |
| `429` | `rate_limit_reached` | Authentication attempts exceeded the in-process limit |

All responses include `X-Request-ID`. Provide that ID, not a customer PDF, when investigating a server error.
