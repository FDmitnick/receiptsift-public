# Atlas and model-provider due diligence

Status: **not approved for real customer receipts**.

ReceiptSift can send rendered receipt pages to Atlas only when `RECEIPTSIFT_PARSER_PROVIDER=atlas` and an API key are explicitly configured. Local extraction remains the no-provider fallback.

## Public-policy findings

Atlas's published [Data Retention Policy](https://www.atlascloud.ai/data-retention) says standard services may retain customer content for up to seven days, not every service is zero-data-retention, and Enterprise ZDR applies only to eligible services under a separate addendum. It also says third-party model providers can apply their own retention and training terms.

Atlas's [Privacy Policy](https://www.atlascloud.ai/privacy) describes a U.S.-hosted service, but that statement alone does not prove that every selected model request is executed and retained only in the United States. Its [Data Deletion Policy](https://www.atlascloud.ai/data-deletion-policy) repeats the standard-retention and executed-ZDR-addendum distinction.

ReceiptSift sends `X-AtlasCloud-Request-Retention-Hours: 0`, but the public policies do not establish that this header creates contractual zero retention for the selected chat-completions endpoint, Qwen models, or GPT verifier.

## Written evidence required before activation

Obtain and archive all of the following from Atlas:

1. an executed DPA naming Atlas and relevant subprocessors;
2. an executed ZDR addendum covering `/v1/chat/completions` and every configured model;
3. a provider/model routing matrix for the primary Qwen model, fallback Qwen model, and GPT verifier;
4. written confirmation of storage, processing, support-access, and backup locations for each route;
5. written confirmation that ReceiptSift inputs and outputs are not used for model training;
6. deletion timing for request bodies, rendered images, outputs, logs, abuse-monitoring copies, and backups;
7. incident notification, subprocessors, cross-border transfer, and deletion-request procedures.

Do not infer compliance from an API response, model listing, marketing page, or request header. Keep production provider mode `local` until these items and legal review are complete.
