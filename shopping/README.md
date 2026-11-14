# Shopping Agent

A Codex skill for evidence-based shopping decisions, local financial calculations, and savings goals.

## Use with Codex

Clone this repository and open the folder in Codex. Then invoke:

```text
$shopping-agent
$shopping-agent ช่วยเปรียบเทียบรองเท้าที่ฉันสนใจ
$shopping-agent อยากซื้อของ ช่วยวางแผนเก็บเงินให้หน่อย
```

The skill is located at [`.agents/skills/shopping-agent/SKILL.md`](.agents/skills/shopping-agent/SKILL.md). To install it in your user skills directory, copy the entire `shopping-agent` folder from `.agents/skills/` into the skills directory used by your Codex installation, then start a new session.

Product names, images, and URLs are interpreted using the tools available in Codex. The Python financial engine does not search merchant websites. Inline UI support depends on the host; Markdown and native selection are available as fallbacks.

## Features

- Product identification and model confirmation, with separate identification and listing-match confidence.
- Evidence-based price comparison, including verified shipping and eligible discounts.
- Deterministic Financial Fit, time-to-afford, and purchase-impact calculations.
- Multiple savings goals, shared budget allocation, calendars, and duplicate-entry protection.
- Daily spending budgets, expense-reduction scenarios, and travel budgets using the same financial engines.
- An optional local dashboard with a shopping chat interface.

## Run the local dashboard

Use Python 3.10 or later. Core features require only the Python standard library.

On Windows, double-click `start-dashboard.bat`, or run this command from the repository root:

```sh
python dashboard/server.py --open
```

Open `http://127.0.0.1:8877`. Stop the server with Ctrl+C. If the port is occupied, add `--port 8878`.

The dashboard runs in **Demo Mode only**. It uses synthetic fixtures and stores goals separately in `local/dashboard-demo.sqlite3`. Its chat uses a deterministic local router, not a connected conversational AI. Live product search and image identification remain available through Codex Chat. Sending messages and moving sliders do not purchase products, transfer money, or record transactions.

## Expense-reduction analysis

The dashboard does not assume preset spending categories or subscriptions. Without user data it shows an empty state, not a savings estimate. Add only your own monthly category totals or explicitly monthly/annual subscriptions. Category sliders use percentages of those amounts; subscription switches are hypothetical. Inputs stay in server memory until restart, never become ledger transactions, and never increase cash or saved balances. Demo financial balances remain separate.

## Connect local financial data

No financial provider is configured by default. Specify a user-authorized local provider folder with `--finance-dir`. Read its `AGENTS.md` and inspect the actual schema before using the [data contract](.agents/skills/shopping-agent/references/data-contract.md) and [planning contract](.agents/skills/shopping-agent/references/planning-contract.md).

This repository contains no real ledger, receipts, financial profile, or credentials. Do not commit these files. Missing or unconfirmed values remain unknown, and transaction totals must not be interpreted as current account balances.

Pass CLI payloads through stdin or an ignored local file. Do not put private financial data in command-line arguments. Creating or changing a goal requires explicit confirmation. When sharing an installed skill across projects, use `--store <workspace>/local/goals.sqlite3` or set `SHOPPING_WORKSPACE` to keep project data separate.

## Tests

```sh
python -m unittest discover -s .agents/skills/shopping-agent/tests -p "test_*.py"
python -m unittest discover -s dashboard -p "test_*.py"
python .agents/skills/shopping-agent/scripts/test_comparison_states.py
```

With Node.js installed, run the simulated UI tests:

```sh
node --test .agents/skills/shopping-agent/component_tests/test_companion_dom.cjs .agents/skills/shopping-agent/component_tests/test_goal_dom.cjs .agents/skills/shopping-agent/component_tests/test_purchase_dom.cjs
python .agents/skills/shopping-agent/scripts/test_simulator_view.py --node node
```

Optional PNG renderer tests require Pillow and supported Thai fonts. Core financial commands do not import Pillow. Tests use synthetic data and temporary databases. DOM simulations do not certify inline behavior in every Codex version.

> Copied into my-finance from https://github.com/natanonlee/shopping-agent (commit da045f4). In this folder the skill is at `../.agents/skills/shopping-agent` and paths above starting with `dashboard/` are under `shopping/dashboard/`.
