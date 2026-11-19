# ReceiptSift PDF

English-first PDF bill and receipt extraction with source-linked review, a public SEO site, and a protected private-beta workspace.

[中文说明](./README.zh-CN.md) · [API](./docs/API.md) · [Architecture](./docs/ARCHITECTURE.md) · [Operations](./docs/OPERATIONS.md) · [Evaluation](./docs/EVALUATION.md) · [Privacy](./docs/PRIVACY.md)

ReceiptSift turns text-based and scanned PDF receipts into editable structured data. Single and batch workflows keep encrypted recent history for up to 7 days for review, while an explicit ledger action can preserve confirmed structured data without the raw PDF.

The interface defaults to English and can switch to Chinese at any time.

## What works

- Real PDF upload with signature, size, page-count, and encryption checks
- Embedded PDF text extraction through PyMuPDF
- Local OCR fallback for scanned pages through RapidOCR and ONNX Runtime
- English and Chinese receipt labels
- Rule-based local extraction plus an optional Atlas Cloud vision pipeline with deterministic quality checks
- Conditional GPT independent verification for risky single-page results; suggestions never auto-overwrite extracted data
- Versioned Receipt, Invoice, and Bill classification with compatible common and type-specific fields
- Vendor, customer, dates, document/account numbers, balances, charges, tax, payment, and enriched line-item extraction
- Per-field confidence and normalized source coordinates
- First-page preview with click-to-highlight source review
- Editable fields and line items held only in the active browser page
- Browser-side UTF-8 line-item CSV and clean JSON export with an explicit leave/refresh warning
- Resumable batch workspace with multi-file upload, progress, duplicate reporting, exception review, retry, and unified CSV
- PostgreSQL batch state, application-encrypted private S3-compatible source storage, and embedded or separate workers
- English-first bilingual UI
- Public SEO landing page, Privacy Policy, Terms, Cookie Policy, Refund Policy, contact email, `robots.txt`, and dynamic sitemap
- Email accounts with Argon2id password hashing and verified-email registration
- Resend-powered email verification and single-use password recovery
- Per-account access, plan, aggregate usage totals, account export, and account deletion
- Content-free parse-order ledger with input/output digests, parser version, status, timing, and confidence metrics
- Explicit, encrypted incorrect-result reports with 14-day retention and user deletion
- Account-protected app, document API, and OpenAPI documentation
- PayPal-aware account deletion that fails closed if subscription cancellation cannot be confirmed
- Owner-only operations console for users, usage, traffic, payments, manual refunds, cancellations, and audit history
- Consent-gated first-party page and important-click analytics without raw IP or browser-fingerprint storage
- Host-aware routing for future `www.` and `app.` custom domains
- Privacy-minimized JSON request/provider logs with request IDs and owner-only runtime metrics
- A conservative daily AI-spend guard with restart-safe aggregate state on the existing volume
- Single-replica authentication rate limits and password re-authentication for destructive admin actions
- Static PDF active-content, embedded-file, complexity, dimension, and render-size controls
- Consistent SQLite online backups with integrity verification and no schema changes
- Parser and API lifecycle tests

## Privacy model

ReceiptSift supports local development and an account-isolated hosted beta.

- Single-document PDFs, previews, results, corrections, and filenames are encrypted and retained for up to 7 days so the user can reopen them.
- Users can delete recent history sooner. Confirmed ledger entries retain only reviewed structured fields and line items; raw PDFs, previews, and page text are excluded.
- The active result exists only in browser page memory and cannot be restored after leaving or refreshing.
- Single-document and batch workflows encrypt source PDFs, previews, results, and corrections for up to 7 days. Users can delete recent history sooner or explicitly keep reviewed structured fields in the long-term ledger without retaining the raw PDF.
- Local OCR runs inside the ReceiptSift process. If Atlas mode is explicitly enabled, rendered pages are sent to Atlas Cloud and its underlying model providers; local extraction remains the fallback.
- In hosted mode, the parser, account dashboard, and API docs require a signed account session.
- SQLite stores accounts, billing state, security records, aggregate usage, and content-free parse-order metadata.
- Receipt evidence is stored only after an explicit incorrect-result report. It is encrypted with a dedicated key, retained for up to 14 days, and can be deleted sooner.
- Registration fails closed until transactional email and the public site URL are configured.

See [docs/PRIVACY.md](./docs/PRIVACY.md) for exact data handling.

## Quick start

Requirements:

- Python 3.11 or newer
- Windows, macOS, or Linux on a CPU supported by ONNX Runtime
- About 350 MB of free disk space for the virtual environment and OCR models

### Windows PowerShell

```powershell
git clone <your-repository-url>
cd receipt-parser-prototype
.\run.ps1
```

Open <http://127.0.0.1:4317/>. The first run creates `.venv`, installs dependencies, and starts the local service.

For later starts without checking dependencies:

```powershell
.\run.ps1 -SkipInstall
```

### macOS or Linux

```bash
git clone <your-repository-url>
cd receipt-parser-prototype
chmod +x run.sh
./run.sh
```

### Manual setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.server:app --host 127.0.0.1 --port 4317
```

## Try the real sample

Select **View live demo** on the home page. The backend generates an actual PDF, sends it through the same parser used for uploads, and returns a real result and generated preview. It is not a hard-coded UI response; like other successful parses, it appears in encrypted recent history for up to 7 days.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Runtime, OCR, limits, and non-retention status |
| `GET` | `/api/auth/status` | Access-protection and session status |
| `POST` | `/api/auth/register` | Create a verified-email user account |
| `POST` | `/api/auth/login` | Create a signed access session |
| `POST` | `/api/auth/logout` | Clear the access session |
| `POST` | `/api/auth/verification/resend` | Request another verification email |
| `POST` | `/api/auth/password/forgot` | Request a generic password-reset email |
| `POST` | `/api/auth/password/reset` | Set a new password with a single-use token |
| `GET` | `/api/v1/account` | Read the signed-in account |
| `GET` | `/api/v1/account/usage` | Read aggregate monthly usage |
| `POST` | `/api/v1/account/usage/csv-export` | Record one aggregate browser-side export |
| `GET` | `/api/v1/account/export.json` | Export account, billing, and usage data |
| `DELETE` | `/api/v1/account` | Delete account and related service records |
| `POST` | `/api/v1/documents` | Upload and synchronously parse one PDF |
| `POST` | `/api/v1/documents/sample` | Generate and parse the live sample PDF |
| `GET/POST` | `/api/v1/batches` | List or create resumable receipt batches |
| `GET/DELETE` | `/api/v1/batches/{id}` | Read or delete an owned batch |
| `POST` | `/api/v1/batches/{id}/documents` | Queue multiple PDFs with per-file duplicate feedback |
| `POST` | `/api/v1/batches/{id}/documents/delete` | Delete selected non-processing documents in one validated request |
| `GET` | `/api/v1/batches/{id}/export.csv` | Generate one-document-per-row summary CSV |
| `GET` | `/api/v1/batches/{id}/export-items.csv` | Generate line-item CSV |
| `GET` | `/api/v1/batches/{id}/export.json` | Generate clean or detailed JSON |
| `GET/PATCH` | `/api/v1/batch-documents/{id}` | Read or review one retained result |
| `POST` | `/api/v1/batch-documents/{id}/retry` | Requeue a retained failed or review document |
| `GET/POST` | `/api/v1/diagnostic-cases` | List metadata or submit one consented encrypted report |
| `DELETE` | `/api/v1/diagnostic-cases/{id}` | Delete diagnostic evidence immediately |
| `GET` | `/api/v1/documents` | Compatibility response: empty, storage disabled |
| `GET/PATCH/DELETE` | `/api/v1/documents/{id}` | Legacy routes return `410` |

Interactive API documentation is available at <http://127.0.0.1:4317/api/docs>. See [docs/API.md](./docs/API.md) for response examples and error codes.

## Configuration

Environment variables are documented in [`.env.example`](./.env.example).

| Variable | Default | Description |
| --- | --- | --- |
| `RECEIPTSIFT_DATA_DIR` | `./data` | Account, billing, usage, parse-order, analytics, audit, and optional encrypted diagnostic data |
| `RECEIPTSIFT_MAX_UPLOAD_MB` | `20` | Maximum upload size |
| `RECEIPTSIFT_MAX_PAGES` | `30` | Maximum pages per PDF |
| `RECEIPTSIFT_MAX_PDF_XREF_OBJECTS` | `50000` | Reject PDFs with an excessive object graph |
| `RECEIPTSIFT_MAX_PDF_PAGE_DIMENSION` | `14400` | Reject extreme page dimensions, in PDF points |
| `RECEIPTSIFT_SESSION_SECRET` | empty | Secret used to sign access sessions |
| `RECEIPTSIFT_SESSION_DAYS` | `7` | Session lifetime in days |
| `RECEIPTSIFT_SECURE_COOKIES` | `true` | Send the session cookie only over HTTPS when hosted |
| `RESEND_API_KEY` | empty | Server-only transactional-email API key |
| `RECEIPTSIFT_EMAIL_FROM` | empty | Sender on a Resend-verified domain |
| `RECEIPTSIFT_ADMIN_EMAIL` | empty | The one verified account allowed to open `/admin` |
| `RECEIPTSIFT_OWNER_ONLY_MODE` | `true` | Reject registrations, non-owner logins, and existing non-owner sessions |
| `RECEIPTSIFT_OWNER_EMAIL` | current owner email | The only account allowed to use protected routes while owner-only mode is enabled; set explicitly in hosted environments |
| `RECEIPTSIFT_ANALYTICS_RETENTION_DAYS` | `180` | Retention for consented first-party page and click events |
| `RECEIPTSIFT_DIAGNOSTIC_ENCRYPTION_KEY` | empty | Fernet key for recent history, saved ledger, and diagnostic evidence; required for retained content and never falls back to plaintext |
| `RECEIPTSIFT_DIAGNOSTIC_RETENTION_DAYS` | `14` | Maximum active retention for explicit diagnostic evidence |
| `RECEIPTSIFT_BATCH_ENCRYPTION_KEY` | empty | Dedicated Fernet key; blank disables batch source writes |
| `RECEIPTSIFT_BATCH_DATABASE_URL` | main SQLite DB | PostgreSQL URL for shared batch state; also accepts Railway `DATABASE_URL` |
| `RECEIPTSIFT_BATCH_OBJECT_STORE` | `local` | `local` for development or `s3` for a private S3-compatible bucket |
| `RECEIPTSIFT_BATCH_WORKER_MODE` | `embedded` | `embedded`, `separate`, or `disabled` queue processing mode |
| `RECEIPTSIFT_HISTORY_RETENTION_DAYS` | `7` | Encrypted single-document history retention |
| `RECEIPTSIFT_BATCH_SOURCE_RETENTION_DAYS` | `7` | Encrypted batch source-PDF retention |
| `RECEIPTSIFT_BATCH_RESULT_RETENTION_DAYS` | `7` | Batch structured result and review retention |
| `RECEIPTSIFT_PUBLIC_HOST` | empty | Future public/`www` hostname |
| `RECEIPTSIFT_APP_HOST` | empty | Future protected `app` hostname |
| `RECEIPTSIFT_APP_HOST_REDIRECT_ENABLED` | `false` | Redirect public-host tool pages only after app-domain DNS/TLS is verified |
| `RECEIPTSIFT_PARSER_PROVIDER` | `local` | Set to `atlas` to enable MarkItDown text routing plus cloud vision fallback |
| `RECEIPTSIFT_ATLAS_API_KEY` | empty | Server-only Atlas credential |
| `RECEIPTSIFT_ATLAS_TEXT_MODEL` | `openai/gpt-5.6-luna` | Text-only model for accepted MarkItDown pages |
| `RECEIPTSIFT_ATLAS_PRIMARY_MODEL` | `qwen/qwen3.5-35b-a3b` | Primary vision extraction model |
| `RECEIPTSIFT_ATLAS_FALLBACK_MODEL` | `qwen/qwen3-vl-235b-a22b-thinking` | Request-failure fallback model |
| `RECEIPTSIFT_GPT_VERIFIER_ENABLED` | `true` | Independently verify quality-gate failures in Atlas mode |
| `RECEIPTSIFT_GPT_VERIFIER_MODEL` | `openai/gpt-5.6-terra` | Conditional verifier model routed through Atlas |
| `RECEIPTSIFT_DAILY_AI_BUDGET_USD` | `5.00` | Conservative application-level daily AI-spend ceiling |
| `RECEIPTSIFT_AI_CALL_RESERVE_USD` | `0.25` | Amount reserved before each provider call when exact usage is not yet known |
| `RECEIPTSIFT_SLOW_REQUEST_MS` | `2000` | Emit a privacy-minimized slow-request log and increment the daily counter |
| `RECEIPTSIFT_SQLITE_CONTENTION_THRESHOLD` | `3` | Daily lock/busy errors that change the database assessment to `consider_postgresql` |
| `RECEIPTSIFT_BATCH_QUEUE_DELAY_WARNING_SECONDS` | `300` | Queue delay that counts toward the separate worker-scaling signal |

Authentication-limit and model-price variables are listed in [`.env.example`](./.env.example). The rate limiter is intentionally in process and valid only for the current single-replica deployment.

## Development

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check backend tests scripts
.\.venv\Scripts\python.exe -m pytest
node --check app.js
node --check batch-workspace.js
.\.venv\Scripts\python.exe -m scripts.verify_batch_50
```

The current test suite covers deterministic and Atlas parsing, quality-gate routing, independent-verifier behavior, provider retries, adaptive rendering, pricing conversion, API lifecycle, batch isolation and deletion, encrypted storage, worker processing, health semantics, and a 50-PDF synthetic batch.

## Repository layout

```text
backend/              FastAPI app, parsers, runtime safeguards, repositories, object storage, and batch worker
tests/                Parser and API tests
docs/                 Architecture, API, extraction, privacy, deployment, operations
.github/              CI and contribution templates
seo.html / seo.css     Public English-first product and SEO surface
login.html / login.js  Protected-app sign-in surface
register.html           Owner-only private-beta account creation guard
account.html            Usage, diagnostic-case controls, account export, and deletion dashboard
privacy.html           Public data-handling notice
terms.html             Public private-beta terms
cookies.html           Cookie and browser-storage disclosures
refunds.html           Paid-plan refund rules
index.html             Bilingual protected application shell
styles.css             Black-and-white product UI
app.js                 API-connected browser interactions
batches.html           Protected batch workspace
batch-workspace.js     Batch API, progress polling, review, retry, and CSV interactions
run.ps1 / run.sh       One-command local startup
```

## Known boundaries

This repository is a functional account-isolated beta, not a complete commercial identity platform.

- Extraction remains probabilistic in Atlas mode. Unusual layouts can require manual correction, and verifier suggestions are not treated as ground truth.
- The first page is visually previewed; text and source metadata are extracted from every page.
- Password-protected PDFs are rejected.
- MFA, distributed authentication rate limits, team roles, and organization workspaces are not implemented yet. The operations console intentionally supports one configured owner only.
- Confidence is a review signal, not a calibrated legal or accounting guarantee.
- Always review results before reimbursement, bookkeeping, or tax use.

See [docs/EXTRACTION.md](./docs/EXTRACTION.md) for the extraction contract and extension points.

Commercial-launch work is tracked in [docs/LAUNCH_ROADMAP.md](./docs/LAUNCH_ROADMAP.md). Mark an item complete only with dated verification evidence.

## Contributing and security

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before opening a pull request. Please report vulnerabilities according to [SECURITY.md](./SECURITY.md), not in a public issue.

## License

No open-source license has been granted yet. See [LICENSE](./LICENSE). Replace it with the repository owner's chosen license before presenting the project as open source.
