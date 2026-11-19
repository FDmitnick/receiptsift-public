# Contributing

Thank you for improving ReceiptSift.

## Before opening a change

- Use an issue for behavior changes that alter the extraction contract or stored data.
- Keep the application local-first unless the change explicitly introduces and documents a new trust boundary.
- Never add real financial documents, API keys, personal data, or the `data/` directory to Git.

## Setup

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
```

Activate the virtual environment for your platform, then run:

```bash
python -m ruff check backend tests
python -m pytest
node --check app.js
```

## Parser changes

Every extraction fix should include a minimal synthetic or properly licensed test fixture. Assert both the extracted value and its source location. Do not weaken an existing assertion to accommodate a new format.

Never commit a user's real receipt. A redacted document can still contain recoverable metadata; prefer generating a synthetic PDF in the test.

## Pull requests

- Describe the user-facing problem and the exact behavior after the change.
- List the tests run.
- Call out privacy, retention, API, or schema changes.
- Keep unrelated formatting or generated files out of the pull request.
- Update README, API, extraction, or privacy documentation when the contract changes.
