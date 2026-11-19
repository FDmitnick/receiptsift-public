# ReceiptSift SEO content system

## Goal

Bring English-speaking users with a specific receipt-data task to a page that answers the task, states the product boundary, and offers the protected tool as the next step.

## Current page map

| Search intent | Primary page | Page type | Conversion action |
| --- | --- | --- | --- |
| PDF receipt parser | `/pdf-receipt-parser` | Feature guide | Open the parser |
| Extract receipt data to CSV / receipt to CSV | `/receipt-to-csv` | Workflow page | Export a reviewed CSV |
| How to extract data from PDF receipts | `/guides/how-to-extract-data-from-pdf-receipts` | Tutorial | Follow the six-step workflow |
| Receipt parser vs manual data entry | `/compare/receipt-parser-vs-manual-data-entry` | Comparison | Test one representative receipt |
| Receipt extraction resources | `/resources` | Content hub | Choose a task-specific page |

## Editorial rules

1. Write for a real task, not a target word count.
2. Use only capabilities that exist in the running product.
3. State unsupported inputs and review requirements near the relevant claim.
4. Never publish invented accuracy, speed, customer, pricing, or compliance claims.
5. Give each page a unique title, description, H1, canonical URL, and intent.
6. Link every new page from a crawlable hub or an existing relevant page.
7. Include an accurate author or product-team attribution when readers expect one.
8. Show the method: current schema, actual workflow, limitations, or a reproducible example.
9. Review financial and tax language so the page does not imply professional advice.
10. Update `sitemap.xml`, internal links, and the page test list with every published route.

## Technical requirements

- Server-rendered English text; important content must not depend on client JavaScript.
- Descriptive, stable URLs.
- Absolute canonical and Open Graph URLs generated from `RECEIPTSIFT_SITE_URL`.
- Breadcrumb structured data on leaf pages.
- Indexable public pages; app, account, login, registration, and document APIs remain blocked.
- Responsive layout, one H1, crawlable `<a href>` links, and no console errors.
- Unique metadata and valid JSON-LD enforced by `tests/test_seo_content.py`.

## Next content cluster

Do not publish this cluster until the first pages are indexed and Search Console shows real queries.

- `/guides/receipt-ocr-accuracy-checklist`
- `/guides/scan-receipts-for-bookkeeping`
- `/guides/organize-receipts-for-tax-season`
- `/compare/receipt-ocr-vs-invoice-ocr`
- `/receipt-line-item-extraction`

Each candidate needs a distinct user problem, evidence from product behavior, and a useful answer that is not already covered by the first cluster.

## Measurement after a domain is connected

Track by landing page and query:

- Indexed pages and crawl errors
- Search impressions and clicks
- Click-through rate by title and query intent
- Visits from content page to protected app
- Account creation after a content landing
- First successful PDF parse after account creation

Search visibility alone is not the commercial outcome; the useful funnel is content visit → qualified app open → account → successful parse.
