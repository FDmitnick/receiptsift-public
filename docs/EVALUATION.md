# Receipt extraction evaluation

## Current 50-document run

The private regression run completed 50 labeled receipt images with no request-level failures. Forty-eight documents had a labeled total; two annotations did not provide one.

| Metric | Qwen 3.5 35B extraction | GPT 5.6 Terra independent read |
| --- | ---: | ---: |
| Total accuracy (48 scoreable) | 85.42% | 100.00% |
| Strict document exact match (48 scoreable) | 81.25% | 89.58% |
| Mean line-item recall (50) | 95.45% | 97.45% |

This was an evaluation run, so GPT read every document to measure disagreement. It is not the production routing policy. With the Atlas prices returned by `/v1/models` at test time, the run consumed 130,631 Qwen input tokens, 206,935 Qwen output tokens, 197,819 GPT input tokens, and 26,107 GPT output tokens. Repriced at $0.225/$1.80 and $2.50/$15.00 per million input/output tokens respectively, the estimated total is $1.2880, or $0.0258 per evaluated receipt.

After correcting locale-aware thousands separators, oversized rendering, provider retries, and fallback request compatibility, the nine original Qwen error cases were rerun. All nine totals matched their labels. Three still failed the strict line-item exact-match metric because of severe blur or annotation-policy differences around discounts, modifiers, and zero-price/free items.

## What this run proves

- The 50 selected files complete the PDF wrapper, render, primary extraction, deterministic checks, independent GPT read, scoring, cost capture, and crash-safe reporting path.
- The quality gate did not auto-accept a labeled Qwen error in the original run.
- GPT is useful for detecting missing or mis-scaled totals, but it can also add or omit line items. Its suggestions must not overwrite the primary extraction automatically.
- Very large source images must be capped before vision requests; the parser now limits the rendered longest side to 3,000 pixels by default.
- The configured 235B fallback rejects `response_format` on Atlas. ReceiptSift retries that model without the incompatible field and uses it only after a primary request failure.

## What this run does not prove

The labeled set is CORD-derived and predominantly Indonesian, not a representative United States launch set. Merchant headers are redacted in 43 of 50 images, two annotations omit the total, and zero-price items, modifiers, and discounts are not labeled consistently. One image is severely blurred and partly handwritten. Do not quote this run as US production accuracy.

Before launch, repeat the same test with at least 50 consented or synthetic US receipts covering USD, sales tax, tips, card/cash tender, returns, discounts, multi-page invoices, scans, glare, skew, and complex line-item tables.

## Production routing policy

1. Run `qwen/qwen3.5-35b-a3b` once.
2. Check required fields, evidence text, tender/change confusion, amount reconciliation, line-item evidence, date normalization, and confidence locally.
3. If the primary request fails, retry and then use `qwen/qwen3-vl-235b-a22b-thinking` as a provider fallback.
4. If extraction succeeds but the quality gate reports risk, run `openai/gpt-5.6-terra` as an independent verifier.
5. A GPT disagreement or unreadable image remains `needs_review`; GPT suggestions are returned for review but are not applied automatically.
6. A clean quality-gate result skips GPT.

## Reproduce privately

Keep the dataset outside the repository. The default report directory is gitignored.

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmark_receipts_50 `
  "C:\samples\receipts" `
  --limit 50 `
  --workers 3 `
  --output ".verify-data\receipt-eval-50\report.json"
```

Use `--resume` after an interruption. Use `--sample-ids B-REC-006,M-REC-008` for targeted regression without rerunning the full set.
