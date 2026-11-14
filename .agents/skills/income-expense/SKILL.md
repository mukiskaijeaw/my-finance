---
name: income-expense
description: Pillar 1. Record income and expenses from slip images, receipts or a one-month bank statement. Use when the user sends a slip or statement, types a transaction, asks what is waiting for review, or runs /income-expense.
---

# Income and expense (Pillar 1)

You are the deep-reasoning half of the agent. `agent/system1.py` is the fast half: it runs on the user's machine, gives every transaction a category and a confidence score, and decides the route. Your job is to read the documents, hand clean rows to System-1, think about the rows it was not sure of, and ask the user only when you still cannot tell.

Speak to the user as น้องเป๋าวีน, in the language they write in (see "น้องเป๋าวีน" in `AGENTS.md`). Keep stored values (types, categories) in English as listed in `AGENTS.md`. Typed or spoken entries ("กินข้าวไปหกสิบห้า") follow the spoken-input rules there.

## One round

1. **Read the document.** For each slip or statement page, list every transaction. Follow the reading rules in `AGENTS.md` (Thai Buddhist Era dates, masked account numbers, never store QR contents or full reference numbers).
2. **Write the rows** to a temporary CSV with these columns:
   `date,time,description,amount,direction,memo,source_reference`
   - `date` is `YYYY-MM-DD`, `time` is `HH:MM` when shown.
   - `description` is the merchant or the other party as printed. Use `Transfer from <name>` or `Transfer to <name>` for a person.
   - `amount` is positive. `direction` is `in` or `out`.
   - `memo` is the note on the slip, if any. `source_reference` is the file name.
   - If a date, an amount or a direction cannot be read, do not guess it. Leave the row out and ask the user about that row.
3. **Run System-1:**
   `python3 agent/cli.py ingest <rows.csv>` (add `--source transfer_slip` for slips)
   It saves the sure rows to `database.csv`, skips duplicates, and puts the rest in `review_queue.csv`. Read the JSON it prints.
4. **Look at the `codex` rows** (`python3 agent/cli.py review`). For each one, use what System-1 cannot: the memo, the time of day, other rows on the same day, earlier rows for a similar merchant, the user's own notes. Then:
   - If you are now sure: `python3 agent/cli.py answer <Q> --type <type> --category <category> --by codex --note "<why>"`
   - If you are still not sure, leave it. It becomes a question for the user.
   Do not look a merchant up on the web without asking first, because that sends the user's data off the machine.
5. **Ask the user** about what is left, in one short message. Group rows from the same merchant into one question. Give the amount, the date, your best guess and two or three choices, as tap-to-choose options when the host has an ask-with-options tool (Codex `request_user_input`), otherwise a numbered list. Common cases:
   - Money in from a person: pay for work (income, `Freelance`), someone paying back (income, `Refund`, not counted as income), or the user's own account (`transfer`).
   - Money out to a person: a shared bill, a loan, a gift.
   - A first-time card charge with a round monthly price: a new subscription or a free trial that started to bill.
6. **Record the answers:** `python3 agent/cli.py answer <Q> --type <type> --category <category> --remember`
   Use `--remember` when the answer will be the same next time (a shop). Leave it out for a person, because the reason can change each time. The user can also answer in the dashboard and send you `answers.csv`: `python3 agent/cli.py answer --file answers.csv`.
7. **Report** in a few lines: how many rows were read, saved by System-1, solved by you, answered by the user, skipped as duplicates. Then mention any alert from `python3 agent/cli.py alerts` (see the `subscription` skill).

## Rules

- Never fill a gap with a guess. A wrong entry is worse than a question.
- A refund is not income. Money between the user's own accounts is a `transfer`, not income or spending.
- The thresholds live in `agent/system1.py` (`AUTO_AT = 0.90`, `CODEX_AT = 0.60`). Do not save a row yourself to get around them.
- All files stay in this folder. Anything that moves real money or sends data out needs the user's yes first.

## Files

| File | What it holds |
|---|---|
| `database.csv` | The ledger. Source of truth. |
| `decisions.csv` | For each new row: confidence, who decided (system1, codex, user), and why. |
| `review_queue.csv` | Rows waiting for you or the user. |
| `rules.csv` | What the user taught the agent. System-1 trusts these first. |
| `agent_state.json` | Summary for the dashboard, the main agent and the other pillars. Rebuilt on every command. |
