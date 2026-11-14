# Finance workflow and data boundaries

The application keeps its ledger files in the app project. The release templates are empty except for their column headers.

## Files and schemas

- `database.csv`: `transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag,model,token_input,token_output`
- `tax_preparation.csv`: `tax_year,transaction_id,record_type,tax_category,amount_thb,source_reference,document_status,review_status,notes`
- `codex_usage_log.csv`: account-level Codex usage observations. Leave readings and deltas blank when unavailable; never estimate them.

Dates use ISO `YYYY-MM-DD` and amounts use numeric THB. Keep transfers separate from income and spending. Investment buys and sells remain separate positive values. Preserve source details and never invent missing transaction information. Avoid duplicate entries.

## Processing and writes

The backend builds a scoped temporary snapshot for Copilot analysis. Images are sent only when the user explicitly attaches them in the dashboard and submits the request. Analysis itself does not write a row. A local proposal must be reviewed and confirmed before the backend can append a transaction. The backend validates fields, source fingerprints, duplicates, and keeps backups. Do not write directly from a generated answer or modify unrelated rows.

Keep financial records local. Do not sync to a spreadsheet, publish, or send them to unrelated services. Any tax screening is a candidate only: use evidence and current official Thai rules before stating a deduction or calculation. Keep salary cash received distinct from gross assessable salary supported by an employer certificate.

## Core engine

`thai-finance-agent/finance_core/` is the shared local workflow engine. `dashboard_server.py` launches Codex CLI against a scoped snapshot and uses the engine for validation. The CLI and the user’s authentication are external requirements.
