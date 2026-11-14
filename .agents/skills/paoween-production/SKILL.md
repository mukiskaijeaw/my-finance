---
name: paoween-production
description: Install and operate the complete Paoween finance app, including its production dashboard, local Copilot backend, animated Blender character, and first-run onboarding. Use when setting up Paoween in a clean project or packaging its full application.
---

# Paoween Production

Use the bundled application at `assets/production-app/` as the source of the full Paoween experience. It includes the production dashboard, local finance workflow engine and Copilot API, animated Paoween models, and Thai/English new-user setup.

## Install into a project

When asked to set up or install Paoween, choose a new or empty destination and run:

```sh
python3 <path-to-this-skill>/scripts/install_app.py --destination <new-project-folder>
```

The installer refuses to copy into a non-empty directory. The bundle contains only header-only CSV templates; do not source or copy transaction, tax, receipt, preference, or review data from another workspace. Do not overwrite an existing app.

## Start and first-run route

On macOS, open `open-dashboard.command` in the installed project. Other systems can run `python3 run_local.py` from that project. The local web server binds only to `unused ports on `127.0.0.1`.

A fresh browser is routed from `/` to `/settings/new-user/`. After the user finishes or skips the setup and opens the dashboard, the completion flag sends future visits to `/dashboard.html`. Append `?force=1` to the onboarding URL to run setup again. Salary is passed to the dashboard as a same-tab temporary summary. A selected JPG/PNG appears in the dashboard attachment tray for review; it is not analyzed until the user presses Send and is not saved until a separate proposal is confirmed.

## Runtime notes

The dashboard and local CSV views can open without Codex CLI. Copilot analysis and receipt reading require the user’s own authenticated Codex CLI; receipt handling also requires Pillow (`python3 -m pip install -r requirements.txt`). Do not claim that a slip is processed until the user attaches it in the dashboard and submits it. The app presents a proposal for review before an approved write.

For the finance schemas and local-write safeguards, read [references/finance-workflow.md](references/finance-workflow.md) when handling records or investigating the backend. For the onboarding route and handoff, read [references/onboarding-flow.md](references/onboarding-flow.md) when changing first-run behavior. The bundled `AGENTS.md`, `COPILOT.md`, and `thai-finance-agent/` explain the app’s local operation.
