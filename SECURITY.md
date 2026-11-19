# Security policy

## Supported version

Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability

Do not open a public issue for a vulnerability or include a real receipt in a report. Use GitHub's private vulnerability reporting feature for the repository. Include reproduction steps with synthetic data, affected versions, and expected impact.

## Deployment warning

ReceiptSift supports loopback use and a controlled account beta with verified-email accounts, password recovery, fail-closed email configuration, authenticated encrypted 7-day history, a user-confirmed structured ledger, content-free parse-order records, and opt-in encrypted diagnostic reports. It does not yet provide MFA, distributed login limits, organization roles, or a sandboxed document worker. General public tool access is unsupported until the controls listed in [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) are added.

Diagnostic evidence must never run without a dedicated valid `RECEIPTSIFT_DIAGNOSTIC_ENCRYPTION_KEY`. Keep that key in the deployment secret manager, separate from backups and the session secret. Owner access to decrypted evidence is audited. Rotate keys only with an explicit migration or after all active cases have expired or been deleted.

## Sensitive artifacts

The following must never be committed:

- `data/` and SQLite files
- Receipt previews or extracted-result dumps
- Uploaded PDFs
- `.env` files
- Logs containing extracted document content
- Real receipt fixtures
- Diagnostic encryption keys or decrypted diagnostic evidence
