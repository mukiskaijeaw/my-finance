# Thai Finance Agent

Open-source starter kit for tracking personal income, spending, investments, and Thai tax-preparation records with a local CSV dashboard.

## Quick start with Codex

1. Clone or download this repository into a private folder on your computer.
2. Copy `database.example.csv` to `database.csv` and `tax_preparation.example.csv` to `tax_preparation.csv`. Never replace existing local data files.
3. Open the folder in Codex and ask it to follow `AGENTS.md`.
4. To use the bundled project skill, invoke `$finance` from a Codex environment that supports repository skills. The skill is in `.agents/skills/finance/`.

The example CSV files contain headers only. The real CSV filenames, receipts, tax documents, and logs are excluded by `.gitignore`; keep those files local and inspect the staged file list before publishing changes.

## Record a transaction

Attach a receipt or type a transaction. The agent extracts the date, amount, description, and category, checks likely duplicates, and appends clear entries to the local `database.csv`. If a critical detail is uncertain, it asks before recording. Items that may matter for Thai taxes are linked to `tax_preparation.csv` and marked `needs_review` until their tax-year rules and evidence are checked.

## Thai tax guidance

See [THAI_TAX_GUIDE.md](THAI_TAX_GUIDE.md) for a practical screening guide. It distinguishes assessable income, income-related expenses, tax allowances, and tax credits; explains why ordinary personal spending is not automatically deductible; and lists evidence to check. Tax rules and temporary incentives can change each year, so the agent must verify current official Revenue Department sources before advising or calculating.

## Open the dashboard on macOS

Double-click `open-dashboard.command` and leave its Terminal window running. The read-only dashboard loads the local CSV files from the local app server. Reload the page after updating CSV data. If opened directly with `file://`, select both CSV files in the page's file picker.

## Privacy

This repository contains no real transaction or tax records. Local files are ignored by Git. Use synthetic data in issues and screenshots, and do not upload financial data to external services.

## Local review workflow

The new standard-library Python core turns ledger flags and document gaps into persistent review tasks, reconciles explicitly linked salary evidence, and detects recurring expense candidates. Start with [WORKFLOW.md](WORKFLOW.md) for commands, synthetic demo data, sidecar evidence fields, implemented scope across the five pillars, and remaining gaps.

Run `python3 -m finance_core --workspace /path/to/finance report` from this repository. Reports and evidence stay in that workspace; the core does not change the transaction or tax ledgers.

## License

MIT; see [LICENSE](LICENSE).
