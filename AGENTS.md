# Personal Finance Agent

Use this folder as a local personal-finance workspace. `database.csv` is the source of truth. `dashboard.html` reads that file and presents a read-only view.

## First use and privacy

- If `database.csv` is missing, create it by copying `database.example.csv`. Never overwrite an existing local file.
- `database.csv`, slips, statements and receipts are private local data. `.gitignore` keeps them out of Git; check the staged file list before every push.
- Use synthetic data only in examples, screenshots, issues and demos.

## Transaction workflow

- When the user attaches a receipt or types a transaction, identify the date, merchant or recipient, amount paid, transaction type, and a suitable category. Append the transaction to `database.csv` unless the user asks for a correction or deletion.
- Treat a purchase receipt as an expense. Treat money received as income. Record investment purchases and sales as separate `investment` rows with positive amounts and `action` set to `Buy` or `Sell`.
- Use `transfer` only when the receipt or user clearly identifies movement between the user's own accounts. A payment to a merchant or another person remains an expense when the user says it is spending.
- Record the amount the user actually paid. For a discount, government subsidy, or co-payment, record the net amount paid and preserve the original amount and discount in `description` when shown.
- Store dates as Gregorian ISO `YYYY-MM-DD` in the `Asia/Bangkok` timezone. Convert Thai Buddhist Era years to Gregorian by subtracting 543. Store `year_month` as `YYYY-MM`.
- Store `amount_thb` as a number with two decimal places. Do not split totals into line items unless the user asks or the receipt makes a useful split clear.
- Use consistent categories. Suggested expense categories include `Food/Beverage`, `Groceries`, `Transportation`, `Housing`, `Utilities`, `Shopping`, `Health`, `Entertainment`, `Subscriptions`, `Travel`, `Transfer money`, and `Other`. Suggested income categories include `Salary`, `Freelance`, `Interest`, `Refund`, and `Other`. For investments, use `Fund`, `Stocks`, `Bonds`, `Crypto`, or `Savings` when appropriate. Keep existing category spellings once they appear in the database.
- Before appending, check likely duplicates using date, amount, merchant or recipient, receipt number, and source. Do not add a likely duplicate; explain the match.
- Do not guess a critical value. Ask if the date, amount, or transaction type cannot be read. If the category is uncertain but the transaction is clear, use the closest category and set `data_quality_flag` to `needs_review: <brief reason>`.
- Assign the next unused ID in the `TXN000001` sequence. Keep the exact CSV schema below, preserve existing rows, and keep rows sorted by date. Use the attachment filename in `source_reference` for receipt images and `manual_entry` as the source for typed entries.
- Do not store full account or card numbers, credentials, or QR contents. Store only details needed to understand and reconcile the transaction.
- Keep receipts and financial data local to this folder. Do not upload, share, or send them to external services.
- For tax questions, check current Thai rules and the user's specific supporting documents. Do not assume an expense is deductible or present an estimate as a final tax determination.

## Bank transfer slips (PNG or JPG)

The user may send e-slips: the image a Thai banking app saves after a transfer or QR/PromptPay payment (K PLUS, SCB EASY, Krungthai NEXT, Bangkok Bank, krungsri, TrueMoney and others). Accept `.png`, `.jpg` and `.jpeg` slips, and screenshots of them.

- Read: date and time, amount, sender name and masked account, receiver name or merchant and masked account, bank names, transaction reference number, and any memo or note.
- Slip dates usually use Thai Buddhist Era short years, such as `8 พ.ย. 69` = `2026-11-08` (BE 2569 − 543). Store the date in `Asia/Bangkok` time.
- Decide the type from the user's side:
  - Sender is the user and receiver is a merchant or another person → `expense`.
  - Receiver is the user and sender is someone else → `income`. Ask what kind of income if it is not clear.
  - Sender and receiver are both the user's own accounts → `transfer` with category `Transfer money`. Confirm unknown accounts with the user.
  - Receiver is a fund, broker or savings product → `investment` with `action` `Buy`.
- A slip names who was paid, but not always what for. Use the receiver name, the memo and the user's message to choose a category. If the purpose is unclear, use the closest category and set `data_quality_flag` to `needs_review: <reason>`. Ask only when the amount, date or type is unreadable.
- Set `source` to `transfer_slip` and `source_reference` to the image filename. Put the last 4–6 characters of the reference number in `description` (for example `ref …A1B2C3`) so the slip can be matched later.
- Never store the QR code contents, full account numbers or the full reference number.
- Duplicates: a slip and a bank statement row for the same transfer are one transaction. Before appending, look for an existing row with the same amount, a date within 1 day, and a matching time (within 5 minutes) or receiver. If a statement row already exists, add the slip's detail (receiver, memo) to that row's `description` instead of adding a new row. If a slip row exists and a statement arrives later, keep the slip row and do not append the statement line again.
- Several slips at once: process each slip, then report one short summary of what was added, merged as a duplicate, or flagged.

## Skills and System-1

This folder holds two pillars of the team's finance agent. Each one has a skill in `.agents/skills/`:

- `income-expense` (Pillar 1): read slips and statements, classify with a confidence score, ask only when unsure. Use it for every slip, receipt, statement or typed transaction instead of editing `database.csv` by hand.
- `subscription` (Pillar 5): find recurring charges and warn before a renewal or a due date. Run it after every statement and when the user types `/subscription`.

`agent/cli.py` is the System-1 side. It runs on the user's machine with plain Python and no network. It writes `agent_state.json`, the one file the dashboard, the main finance agent and the other pillars (tax, investment, price check) read from this pillar.

Any action that moves real money or sends data off this machine (a payment, a cancellation, an email, a web search that includes the user's data) needs the user's yes first.

## Database schema

Keep these columns in this exact order:

`transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag`

## Dashboard

- `dashboard-journal.html` (journal look: sidebar, payment calendar, spending chart) and `dashboard-folder.html` (folder-tab look) are the new dashboard drafts. Each reads `database.csv` and `agent_state.json` and shows the open questions, the confidence of each decision, and the bills and subscriptions. `dashboard.html` is the earlier dashboard and still works.

- The dashboard is read-only. Update `database.csv` to add or correct transactions, then reload the page.
- It provides year and month filters, monthly income and expense trends, investment buy and sell trends, expense categories, and recent transactions.
- On macOS, open `open-dashboard.command`. It serves this folder on `127.0.0.1:8765` and opens the dashboard. Keep its Terminal window open while using the dashboard and press Control-C there to stop the server.
- If the dashboard is opened directly with `file://`, choose `database.csv` in the file picker or use `open-dashboard.command` for automatic loading.
