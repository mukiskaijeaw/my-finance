---
name: tax
description: Thai personal income tax (Pillar 3). Use when the user asks about tax, sends a payslip, a 50 bis (50 ทวิ) certificate or a receipt that may count for tax, asks what is still missing for tax, or types /tax.
---

# Tax

Made by a teammate as the Tax pillar of the team's finance agent; it plugs into this folder next to `income-expense`, `subscription` and `dashboard`. Read `AGENTS.md` first for the ledger rules, then `tax/THAI_TAX_GUIDE.md` for the screening checklist.

## Files

- `database.csv` (Pillar 1) stays the cash ledger. Never change it from this skill.
- `tax_preparation.csv`: tax records linked by `transaction_id`. Create it from `tax_preparation.example.csv` if it is missing. Columns and rules are in `AGENTS.md` under "Tax records".
- `finance_evidence.json`: payslip / 50 bis figures used to reconcile salary deposits. Start from `tax/finance_evidence.example.json`.
- `finance_review.json`: the tax check's task list and audit trail. Written by the check, never by hand.

All four are private and ignored by Git.

## Steps

1. When the user sends a payslip or 50 bis, record the gross salary as an `income` row in `tax_preparation.csv` (Buddhist Era `tax_year`) linked to the salary deposit, and add a salary document to `finance_evidence.json` with only figures the document shows. Unknown withholding stays unknown; do not write zero.
2. When a receipt may count for tax (insurance, provident fund, RMF/SSF/Thai ESG, donation, mortgage interest, year-specific schemes), add a `deduction` row with `review_status` `needs_review`. Never infer eligibility from a merchant or receipt alone.
3. Run `python3 agent/cli.py tax`. It checks the ledger and the tax records and prints the open tasks: salary not reconciled with a payslip, missing documents, tax year mismatches.
4. Reply in plain Thai: what was added, then ask **one** focused question for the most important open task. Do not list every task at once.
5. When the user answers a task, record it: `cd tax && python3 -m finance_core --workspace .. review TASK-xxxx --note '<what the user said>'`. A reviewed task records the answer only; it does not grant a deduction or change any ledger.
6. `python3 agent/cli.py dashboard --open` shows the result on the Tax page (estimate, tax records, documents to check).

## Rules

- Separate assessable income, income-related expenses, allowances/deductions and tax credits. Ordinary personal spending is not deductible by default.
- Use gross salary from the employer's certificate for tax; keep the net deposit in `database.csv` as cash received. Do not count social security or provident fund withheld from salary twice.
- Rules and caps change every tax year. Check current Revenue Department sources (see `tax/TAX_RESEARCH.md`) before giving a number as advice, and say when a figure is an estimate.
- Nothing leaves this machine. A web search for current rules must not include the user's figures.
