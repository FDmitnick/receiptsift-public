# ReceiptSift batch workspace

## Product boundary

The batch workspace turns ReceiptSift from a single-response converter into a resumable receipt-processing tool. A user can
upload a group of PDFs, leave the page, return to review exceptions, correct fields, and export one accounting-ready dataset.

This is a limited-retention processing workspace, not a permanent tax-record archive.

## Retention contract

The initial defaults are:

- rendered pages and OCR/model intermediates: request lifetime only, with a one-hour operational ceiling for future workers;
- encrypted source PDFs: 7 days from batch creation;
- structured results, review state, and corrections: 7 days from batch creation;
- CSV exports: generated on demand and not retained by the application;
- account, billing, aggregate usage, and security audit metadata: governed separately by the account and legal policies.

Users can delete a batch before either deadline. Source and result expiry must be visible in the product before batch storage is
enabled for customers.

## Storage model

`receipt_batches` owns the user-visible job and its retention deadlines. `receipt_batch_documents` owns per-file processing
state, encrypted source-object references, extraction results, failures, and attempt counts. `receipt_review_changes` records
the user-authored patch and resulting reviewed payload.

Every batch and document lookup is scoped by `user_id`. Source objects use generated keys, are encrypted before being written,
and are never exposed by static file serving. A missing or invalid `RECEIPTSIFT_BATCH_ENCRYPTION_KEY` disables source writes and
fails closed. PostgreSQL is supported through `RECEIPTSIFT_BATCH_DATABASE_URL`. Private AWS S3, Cloudflare R2, MinIO, and other
S3-compatible storage is supported through the `RECEIPTSIFT_BATCH_OBJECT_*` settings. Objects are written without public ACLs
or static URLs.

## Implemented workflow

1. `/batches` provides an English-first, bilingual workspace with a pending-confirmation upload list, per-file deletion,
   explicit processing start, progress, duplicate reporting, exception review, retry, and unified CSV/JSON export.
2. Authenticated `/api/v1/batches*` routes scope every read and mutation to the signed-in account.
3. Uploads are stored as `staged` and do not call the parser. The explicit start action atomically changes staged files to
   `queued`. `backend.batch_worker.BatchWorker` claims queued files outside the request. Pending and queued files can be
   deleted; a processing file is locked until its current worker attempt finishes. Embedded mode is available for
   one-replica local use; production can run `python -m scripts.run_batch_worker` as a separate worker service.
4. The worker persists real processing milestones for PDF safety checks, allowance checks, structure analysis, model or local
   extraction, quality checking, independent verification, finalization, and result saving. The workspace shows queue position,
   elapsed time, adaptive estimated start/remaining time, and a slow-stage notice. Timing estimates stay unavailable until
   recent completed work or enough live progress exists; the UI does not present a fabricated countdown.
5. Account deletion removes every batch, encrypted source object, structured result, and review record before deleting the
   account. Startup removes expired sources and expired batches and requeues interrupted work older than 15 minutes.
6. The repeatable `python -m scripts.verify_batch_50` check generates, parses, and validates a 50-PDF synthetic batch without
   using a paid provider.

SQLite and encrypted local objects remain available for development. Before public batch traffic, configure PostgreSQL and a
private object bucket, add provider-side lifecycle rules as defense in depth, and run the web service with
`RECEIPTSIFT_BATCH_WORKER_MODE=separate` plus a dedicated worker process. This repository contains the adapters but does not
prove a live production database or bucket until those credentials are supplied and verified.
