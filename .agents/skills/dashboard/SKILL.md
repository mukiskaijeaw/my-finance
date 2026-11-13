---
name: dashboard
description: Show the user's money summary as the dashboard page. Use when the user asks to see the dashboard, a summary, an overview, or "how am I doing" (for example "ขอดูสรุป", "ขอดูแดชบอร์ด"), or types /dashboard.
---

# Dashboard

The dashboard is one HTML file built from the user's own `database.csv`. It opens by double-click and needs no server or internet for the data (fonts load from the web when online).

## Steps

1. If the user just sent slips or a statement in the same message, record them first with the `income-expense` skill.
2. Run `python3 agent/cli.py dashboard --open`.
   It rebuilds `agent_state.json`, writes `my-dashboard.html` in this folder with the user's data inside, and opens it in the browser. Leave out `--open` if no browser should open (for example on a server).
3. Read the JSON it prints and reply in the user's language with:
   - the file it opened (`my-dashboard.html`),
   - how many entries it covers and the date range,
   - the numbers that need the user: `waiting_for_user`, `marked_to_check`,
   - every line in `alerts` (renewals and due dates that are close, or new charges).
   Keep it to a few lines. The page shows the rest.
4. If the ledger has fewer than about two months of entries, say that the calendar and the subscription list will fill in once more months are recorded.

## Rules

- `my-dashboard.html` contains the user's real data. Never commit it, upload it or send it anywhere. `.gitignore` already excludes it.
- The page does not change `database.csv`. Answers the user clicks on the To check page stay in that browser until they send the downloaded `answers.csv` back (`python3 agent/cli.py answer --file answers.csv`).
- To refresh the page after new entries, run the command again. The Refresh button on a page opened by double-click only reloads what is already inside the file.
