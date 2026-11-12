#!/usr/bin/env python3
"""Rebuild the example data inside dashboard-folder.html and dashboard-journal.html.

Runs one full agent round on synthetic data (demo/database.example.csv, then
demo/statement-2026-11.example.csv) in a temporary folder and writes the result
into the dashboard, so the page shows something when opened by double-click.

  python3 demo/build-demo.py [--today 2026-11-12] [--keep <folder>]
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--today", default="2026-11-12")
ap.add_argument("--keep", help="keep the working folder here (it is a ready-to-open example workspace)")
a = ap.parse_args()

work = a.keep or tempfile.mkdtemp()
os.makedirs(work, exist_ok=True)
for f in ("database.csv", "review_queue.csv", "decisions.csv", "rules.csv", "agent_state.json"):
    if os.path.exists(os.path.join(work, f)):
        os.remove(os.path.join(work, f))
shutil.copy(os.path.join(root, "demo", "database.example.csv"), os.path.join(work, "database.csv"))
subprocess.run([sys.executable, os.path.join(root, "agent", "cli.py"), "--dir", work, "--today", a.today, "ingest",
                os.path.join(root, "demo", "statement-2026-11.example.csv")], check=True, stdout=subprocess.DEVNULL)

state = open(os.path.join(work, "agent_state.json"), encoding="utf-8").read().replace("</", "<\\/")
ledger = open(os.path.join(work, "database.csv"), encoding="utf-8").read().replace("</", "< /")
for name in ("dashboard-folder.html", "dashboard-journal.html"):
    page = os.path.join(root, name)
    html = open(page, encoding="utf-8").read()
    html = re.sub(r"/\*DEMO-STATE\*/.*?/\*END-DEMO-STATE\*/", lambda m: "/*DEMO-STATE*/" + state + "/*END-DEMO-STATE*/", html, flags=re.S)
    html = re.sub(r"/\*DEMO-LEDGER\*/.*?/\*END-DEMO-LEDGER\*/", lambda m: "/*DEMO-LEDGER*/" + ledger + "/*END-DEMO-LEDGER*/", html, flags=re.S)
    open(page, "w", encoding="utf-8").write(html)
print("Updated both dashboards" + (f"; workspace kept in {work}" if a.keep else ""))
if not a.keep:
    shutil.rmtree(work)
