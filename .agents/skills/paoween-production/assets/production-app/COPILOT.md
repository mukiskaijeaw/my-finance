# Paoween local finance dashboard

Start the application with `open-dashboard.command` on macOS or `python3 run_local.py` elsewhere. A clean browser opens `/settings/new-user/` before the production dashboard. The dashboard reads local CSV files and provides a chat, data views, receipt attachment, and reviewable transaction proposals.

Copilot uses the authenticated Codex CLI installed by the app operator. The backend creates a scoped temporary snapshot rather than granting the CLI direct write access to the live project. Chat history stays in server memory and expires after inactivity or restart. A request to analyze an image does not commit a transaction. The backend may append only after a user reviews and confirms the displayed proposal; it rechecks duplicates and source fingerprints and keeps a backup.

Receipt images are attached and submitted from the dashboard. The onboarding page stages a selected JPG/PNG locally, then places it in the dashboard attachment tray and removes the staged copy. It is not sent for analysis until the user presses Send and is not saved until a separate transaction proposal is confirmed.

The launcher chooses unused ports for the HTTP server and API, both bound only to `127.0.0.1`, and pairs the browser with that project’s API. Never bind either service to a public or LAN interface.

For record schemas and privacy boundaries, see `../references/finance-workflow.md` in the skill package. In a copied project, see `thai-finance-agent/WORKFLOW.md` and the finance core source.
