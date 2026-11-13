#!/bin/zsh
# Double-click on a Mac: rebuild the dashboard from database.csv and open it.
set -e
cd -- "$(dirname -- "$0")"
python3 agent/cli.py dashboard --open
