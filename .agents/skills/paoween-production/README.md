# Paoween Production Skill

This folder is an installable Codex skill plus the complete Paoween app release. The app is in `assets/production-app/`; it contains the production dashboard, local backend and finance core, onboarding page, Blender source projects, GLB runtime models, Three.js dependencies, and model-building tools.

## Install the skill

Copy the whole `paoween-production` folder into your Codex skills directory, usually `~/.codex/skills/paoween-production`. Restart or refresh Codex’s skill list if needed.

## Install a clean app project

Use the skill’s installer to copy a fresh app into a new empty folder:

```sh
python3 scripts/install_app.py --destination /path/to/new/paoween-project
```

The destination must be empty. The included ledgers contain headers only. No existing personal ledger, tax worksheet, receipt, preferences, or review data is bundled.

On macOS, open `open-dashboard.command` in the installed project. Elsewhere, run `python3 run_local.py`. The first visit enters new-user setup, which then routes to the production dashboard. A slip selected there moves into the dashboard attachment tray for review; nothing is analyzed or saved until the user takes those steps. Use `/settings/new-user/?force=1` to revisit onboarding in the same browser.

## Requirements

- Python 3.9 or newer; Python 3.10+ is recommended.
- Pillow for validating receipt image uploads: `python3 -m pip install -r requirements.txt`.
- An authenticated Codex CLI for Copilot analysis and receipt reading. Codex CLI is not embedded in this archive.

The local dashboard serves on unused `127.0.0.1` ports. Keep the launcher running while using the app and stop with Ctrl-C. The server does not expose itself on the local network.
