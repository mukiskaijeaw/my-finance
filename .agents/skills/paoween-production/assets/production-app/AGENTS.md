# Paoween finance workspace

This app uses local CSV files as its transaction and tax-preparation records. Keep those files in the project and preserve their schemas and source references. This distribution starts with blank templates; never import data from another workspace unless the user explicitly asks and provides the specific source.

## Transaction handling

- Append new transactions; do not rewrite or remove unrelated rows.
- Treat a receipt as an expense by default. Use `income`, `investment`, or `transfer` only when the evidence supports that type. Transfers between the user's own accounts are neither income nor spending.
- Keep investment buys and sells as separate positive amounts. Use existing category labels where possible; add a consistent neutral label only when needed.
- Store dates as ISO `YYYY-MM-DD`, amounts as numeric THB, and `year_month` as `YYYY-MM`. Use Buddhist Era year conversion for Gregorian transaction dates.
- Preserve the original amount. Do not split line items unless requested or the receipt clearly supports a useful split.
- Check date, amount, merchant, receipt number, and source for likely duplicates before proposing a new row.
- Never invent missing details. Preserve source/source_reference and mark uncertain categories for review. Ask before recording if amount, date, or transaction type cannot be determined.
- Assign the next unused `TXN000001`-style ID. Preserve existing IDs when correcting a row.
- Keep the CSV schema and chronological sort. Transaction changes require a displayed proposal and explicit user confirmation in the dashboard.

## Privacy and tax

- Keep financial data local. Do not publish, share with other services, or sync to a spreadsheet unless explicitly requested.
- The dashboard sends a scoped snapshot to the user's authenticated local Codex CLI only when the user submits a question. Receipt images are sent only when explicitly attached and submitted.
- Candidate tax records require evidence and current official Thai rules. Mark unverified deductions `needs_review`; do not assume ordinary spending is deductible.
- Keep cash salary deposits separate from gross assessable salary supported by the employer's certificate. Do not count a withheld contribution twice.

## Dashboard and backend

`dashboard.html` reads `database.csv` and `tax_preparation.csv`. The local web service and Copilot API bind to unused ports on `127.0.0.1`. Do not change them to a network-wide bind. Tables and charts are read-only; the approved local action endpoint validates proposals and keeps backups.
