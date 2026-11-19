# Privacy and data handling

This document describes the repository as shipped. The hosted Privacy Policy is served at `/privacy`; privacy requests use `contact@example.invalid`.

## Data processed for one active result

- Uploaded PDF bytes
- Extracted page text, fields, line items, confidence, and source coordinates
- Original filename, page count, and processing method
- A first-page PNG preview generated in memory
- Corrections made in the browser before export

The single-PDF API parses these values in memory, returns them to the active browser page, and encrypts the source PDF and result for the signed-in account for up to 7 days. Browser corrections update that encrypted recent result. CSV generation happens on demand and does not create a retained export file. The account page can reopen or delete an unexpired result.

## Data retained in the batch workspace

The batch workspace is a separate, explicit persistence mode for users who need to process many receipts over time. It stores the batch name, original filename, encrypted source PDF, SHA-256 duplicate digest, processing state, structured result, error state, and user-authored review corrections. Every record and source lookup is scoped to the signed-in account. Source objects are encrypted before private storage and are not exposed through static file serving.

- encrypted source PDFs and previews: up to 7 days from creation;
- structured results and review corrections: up to 7 days from creation;
- user-confirmed ledger fields and line items: until the ledger entry or account is deleted, without raw PDFs or previews;
- generated CSV files: created on demand and not retained by the application;
- batch deletion: immediately removes active source objects, results, and review records;
- account deletion: also removes all owned batches and their active source objects.

Local mode keeps document extraction inside the ReceiptSift process. When Atlas mode is explicitly enabled, rendered page images and extraction instructions are submitted to Atlas Cloud and its underlying model providers. A result that fails the local quality gate may also be sent to the configured GPT verifier through Atlas for an independent read. ReceiptSift requests zero-hour retention using `X-AtlasCloud-Request-Retention-Hours: 0`, but Atlas and underlying-provider terms still apply; ReceiptSift cannot independently guarantee their processing location or deletion behavior.

## Data retained for the service

- Account email, Argon2id password hash, timestamps, and signed-session state
- Hashed, single-use email verification and password-reset tokens
- Aggregate monthly usage: successful document count, processed page count, and CSV export count
- Content-free parse-order metadata: user and order IDs, timestamps, page count, parser version and method, status or error code, input/output SHA-256 digests, duration, confidence, and warning count
- PayPal subscription, payment, refund, and cancellation state
- Consented first-party page views and important product clicks using a random browser identifier
- Administrator audit records and security/abuse controls

## Optional diagnostic evidence

The “Report incorrect result” action is separate from routine parsing. It requires an unchecked consent box and a user description. After explicit submission, ReceiptSift stores the original extraction, current corrected extraction, description, and the original PDF when the user uploaded one. Live-demo reports contain results only.

Each evidence file is encrypted with Fernet using `RECEIPTSIFT_DIAGNOSTIC_ENCRYPTION_KEY`. An invalid or missing key disables submissions and never falls back to plaintext. Evidence is isolated under `RECEIPTSIFT_DATA_DIR/diagnostics/<case-id>/`, available only to the submitting account for metadata/deletion and to the configured owner for investigation. Owner views, PDF downloads, and deletions are written to the administrator audit trail.

Application analytics do not accept receipt content, filenames, raw IP addresses, or browser fingerprints from the browser. Infrastructure providers may still process ordinary network and service logs.

## Storage

`RECEIPTSIFT_DATA_DIR` contains `receiptsift.sqlite3` for new installations. Existing installations continue reading the legacy database filename until a controlled migration. The database stores accounts, authentication, billing, aggregate usage, parse-order metadata, diagnostic-case metadata, analytics, and audit state. The schema retains a legacy `documents` table only for safe migration; startup removes any legacy document rows and matching preview files, and current parse routes never write new rows.

The persistent volume is required for account, billing, order-ledger, and optional diagnostic continuity. Local development can also keep encrypted batch objects there. Production batch mode supports PostgreSQL for job state and private S3-compatible storage for encrypted source objects. The batch workspace is limited-retention working storage, not a permanent tax-record archive.

## Retention and deletion

- Single-PDF receipt content, extracted results, corrections, and previews: no application retention after the active response/page.
- Single and batch source PDFs and previews: encrypted and retained for up to 7 days by default.
- Single and batch structured results and corrections: encrypted and retained for up to 7 days by default.
- Confirmed ledger entries: retained until deleted by the user; raw PDFs, previews, and extracted page text are excluded.
- Parse-order metadata: retained with the account and removed on account deletion, subject to backups or legal exceptions.
- Explicit diagnostic evidence: up to `RECEIPTSIFT_DIAGNOSTIC_RETENTION_DAYS`, default 14 days; the user or owner can delete it sooner.
- Consented analytics: normally up to `RECEIPTSIFT_ANALYTICS_RETENTION_DAYS`, default 180 days.
- Account: until the user deletes it.
- Billing, refund, security, backup, and audit records: only as reasonably necessary for accounting, disputes, fraud prevention, or legal obligations.

Account deletion requires password confirmation and first attempts to cancel a linked non-terminal PayPal subscription. It then removes active batch source objects and results, active diagnostic evidence, parse-order metadata, the account, authentication tokens, billing mapping, and usage events. Analytics rows retained for aggregate reporting are disconnected from the deleted account. If PayPal cannot confirm cancellation, deletion stops and the local account remains.

## Network boundary

The included launch scripts bind to `127.0.0.1`. Hosted mode keeps the tool, account dashboard, receipt-processing API, and OpenAPI documentation behind a signed account session. Hosted registration opens only when transactional email delivery and the public site URL are configured.

When configured, account verification and password-recovery emails are delivered through Resend. PayPal handles subscription payments. The owner operations console is disabled unless `RECEIPTSIFT_ADMIN_EMAIL` exactly matches one verified account.

## Backups

Back up the configured data directory and PostgreSQL database for account and billing continuity. A backup can contain encrypted batch content or user-authorized diagnostic evidence after it has expired from active storage. Backups should be encrypted, access-controlled, and governed by a documented deletion schedule that does not silently turn limited-retention processing into permanent storage.
