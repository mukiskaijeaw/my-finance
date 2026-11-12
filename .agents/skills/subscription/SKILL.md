---
name: subscription
description: Pillar 5. Find recurring charges and subscriptions in the ledger and warn the user before a renewal or a due date. Use for /subscription, questions like "what is due soon" or "which subscriptions do I pay for", and after every statement is recorded.
---

# Subscriptions and due dates (Pillar 5)

This skill only reads the ledger that Pillar 1 keeps. It does not need any other data.

## How to make the alerts

1. Run `python3 agent/cli.py alerts --days 7`. It rebuilds `agent_state.json` and prints the alerts.
2. Tell the user, most urgent first. Speak in the user's language:
   - `late`: a charge was expected but is not in the statement. Ask the user to check that it was paid.
   - `soon`: a renewal or a due date is close (3 days for a subscription, 5 days for a bill or a debt payment).
   - `check`: a new charge that looks like a subscription, often a free trial that started to bill. Ask if the user wants to keep it.
   - `upcoming`: everything else in the next 30 days. Mention only if the user asks.
3. For `/subscription`, also list every subscription with its price, how often it is paid, the cost per year and the next date. The list is in `agent_state.json` under `recurring` (`kind` is `subscription`, `bill`, `debt`, `saving` or `income`).
4. If a price changed, say the old and the new price.

## How a recurring charge is found

`agent/recurring.py` groups ledger rows by merchant and keeps a group when:

- it has at least two payments,
- at least 75% of the amounts are within 10% of the usual amount, and
- at least 75% of the gaps between payments are about 7, 30 or 365 days.

The next date is the last payment plus one period. A single charge with a subscription name is listed as `new` with 60% confidence until it repeats.

## To run it every day

The check is one command, so any scheduler works. On macOS, add this line with `crontab -e` to check at 09:00 every day and keep the result in the folder:

`0 9 * * * cd "/path/to/this/folder" && /usr/bin/python3 agent/cli.py alerts --days 7 > alerts.txt`

Next time the user opens Codex, read `alerts.txt` (or just run the command again) and tell them what is due.

## Rules

- Never cancel a subscription, pay a bill or send a reminder outside this folder without the user's yes. Say what you would do and wait.
- Do not call something a subscription from one payment alone. Say it "may be" one and ask.
- Money saved by cancelling goes to the main agent's plan through `agent_state.json` (`fixed_costs`), so say the monthly and yearly amount when the user decides to cancel.
