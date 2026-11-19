# Extraction contract

## Pipeline

1. Validate PDF signature, readability, encryption state, page count, and size.
2. Select the configured provider: local or Atlas Cloud.
3. Local mode extracts ordered text spans and page-relative bounding boxes with PyMuPDF.
4. If a local page contains fewer than 20 embedded-text characters, rasterize it and run RapidOCR locally.
5. Atlas mode first converts each page with MarkItDown, then checks Markdown length, financial anchors, monetary values, and large embedded-image coverage.
6. Send the Markdown to the text model only when every page passes. Scanned, weak-text, and hybrid image/text PDFs go directly to the vision model.
7. If the text-model result fails completeness, confidence, or amount reconciliation, rerun the original PDF through the vision route.
8. Retry transient provider failures. Use the larger Qwen fallback only when the primary vision request itself fails.
9. Validate core fields, evidence text, line items, dates, tender/change confusion, and amount reconciliation.
10. When the deterministic quality gate fails on a single-page document, ask GPT for an independent read. Never apply its corrections automatically.
11. Return `needs_review` with warnings and verifier discrepancies when a value cannot be safely accepted.

## Financial Document Schema v1

Every result includes `schema_version: "1.0"`, `document_type` (`receipt`, `invoice`, or `bill`), and an optional
`document_subtype`. The runtime keeps the legacy `merchant`, `date`, and `receipt_number` fields as aliases for
`vendor_name`, `issue_date`, and `document_number` so older clients remain compatible.

Common fields cover the vendor/biller, customer, document and account numbers, issue and due dates, currency,
payment method, gross amount, discounts, refunds, subtotal, shipping, fees, tax, tip, total, amount paid, and balance
due. Invoice fields add Bill To, Ship To, purchase order, payment terms, and original invoice number. Bill To is also
copied to the legacy-compatible customer fields. Bill fields add service period, previous balance, payments,
credits, adjustments, current charges, late fees, minimum due, and autopay date.

`items[]` includes description, optional SKU, quantity, unit, unit price, line discount, tax rate, tax amount, and line
amount plus line total. Negative line amounts are preserved for printed returns and credits. Credit notes use
`document_type: "invoice"` with `document_subtype: "credit_note"` and separate total-credit/refund reconciliations.

Every field includes a confidence value and source evidence when available. Local extraction includes the original page, line text, and normalized bounding box. MarkItDown/text-model and Atlas vision extraction include page-level evidence text but deliberately leave the bounding box null because the provider does not return a verified coordinate region.

Receipt, invoice, and bill results use separate reconciliation formulas. The legacy `reconciliation` object remains for
clients that need one primary matched/difference pair; `reconciliations[]` carries the named, type-specific checks.

Atlas responses include a `routing` object with the selected branch, the reason, and non-content page diagnostics. When a text result falls back to vision, the object also reports text-attempt and full-pipeline token usage. The router is deliberately conservative: a large embedded image forces vision even when some surrounding text is copyable.

## Confidence semantics

Confidence combines OCR confidence with a rule-specific prior. Embedded text receives high recognition confidence, but the semantic rule can lower the final value. Derived values, such as subtotal computed from items, deliberately receive lower confidence.

Atlas confidence is model-reported and is checked alongside deterministic completeness and amount reconciliation. It is not a calibrated probability.

The independent verifier is disagreement detection, not ground truth. A `corrected` or `review` verdict always remains `needs_review`; a verifier outage also fails closed to manual review. Clean quality-gate results skip the verifier.

These values are review priorities, not statistically calibrated probabilities.

## Supported patterns

The included rules recognize common English and Chinese labels for total, subtotal, tax/VAT/GST/service fee, payment method, receipt/invoice/order number, and dates. Currency detection covers USD, CNY/RMB, EUR, GBP, and JPY.

Line items support coordinate-aligned invoice tables across pages as well as text rows that end with either:

```text
Description   quantity x unit_price   amount
Description                              amount
```

## Known failure modes

- Complex tables whose columns or headers change between pages
- Handwriting, severe blur, folds, glare, or very low-resolution scans
- Totals without two decimal places
- Currency symbols that are ambiguous between CNY and JPY without textual context
- Receipts whose merchant name is not near the top
- Discounts and negative amounts with unusual notation
- Multi-line item descriptions

The UI is intentionally built around correction because no generic receipt extractor is exact across all layouts.

See [EVALUATION.md](./EVALUATION.md) for the current 50-document results, costs, and dataset limitations.

## Extension points

Add new labels and parsing rules in `backend/parser.py`. Keep parser output stable and add a fixture-based regression test for every new layout. For a learned extraction model, preserve the existing field/source contract so the API and review UI do not need to change.
