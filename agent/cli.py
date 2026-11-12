#!/usr/bin/env python3
"""Pillar 1 + 5 command line. Python 3.9+, standard library only, no network.

  python3 agent/cli.py ingest rows.csv     read new rows, save the sure ones, queue the rest
  python3 agent/cli.py review              show what is waiting (route: codex or ask)
  python3 agent/cli.py answer Q003 --type income --category Freelance [--remember]
  python3 agent/cli.py answer --file answers.csv
  python3 agent/cli.py alerts [--days 7]   renewals and due dates
  python3 agent/cli.py state               rebuild agent_state.json for the dashboard and other pillars

Options for every command: --dir <folder with database.csv> (default: current folder), --today YYYY-MM-DD
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recurring  # noqa: E402
import system1    # noqa: E402

LEDGER_COLS = ["transaction_id", "date", "transaction_type", "description", "amount_thb", "category",
               "action", "year_month", "source", "source_reference", "data_quality_flag"]
QUEUE_COLS = ["question_id", "date", "time", "description", "memo", "amount", "direction", "source", "source_reference",
              "same_as", "route", "confidence", "guess_type", "guess_category", "guess_action", "reason", "question", "candidates"]
DECISION_COLS = ["transaction_id", "confidence", "decided_by", "reason"]
RULE_COLS = ["pattern", "direction", "transaction_type", "category", "action", "learned_on"]


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, cols, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


class Workspace:
    def __init__(self, folder):
        self.dir = folder
        p = lambda n: os.path.join(folder, n)  # noqa: E731
        self.ledger_path, self.queue_path = p("database.csv"), p("review_queue.csv")
        self.decisions_path, self.rules_path, self.state_path = p("decisions.csv"), p("rules.csv"), p("agent_state.json")
        if not os.path.exists(self.ledger_path):
            example = p("database.example.csv")
            if not os.path.exists(example):
                sys.exit(f"No database.csv in {folder}")
            write_csv(self.ledger_path, LEDGER_COLS, read_csv(example))
        self.ledger = read_csv(self.ledger_path)
        self.queue = read_csv(self.queue_path)
        self.decisions = read_csv(self.decisions_path)
        self.rules = read_csv(self.rules_path)

    def next_id(self):
        nums = [int(r["transaction_id"][3:]) for r in self.ledger if re.fullmatch(r"TXN\d+", r["transaction_id"])]
        return f"TXN{(max(nums) if nums else 0) + 1:06d}"

    def append(self, row, t, category, action, confidence, decided_by, reason, flag=""):
        desc = row["description"].strip()
        if row.get("memo"):
            desc += f" - {row['memo'].strip()}"
        if row.get("time"):
            desc += f" (Bank {row['time']})"
        tid = self.next_id()
        self.ledger.append({
            "transaction_id": tid, "date": row["date"], "transaction_type": t, "description": desc,
            "amount_thb": f"{float(row['amount']):.2f}", "category": category, "action": action,
            "year_month": row["date"][:7], "source": row.get("source") or "bank_statement",
            "source_reference": row.get("source_reference", ""), "data_quality_flag": flag})
        self.decisions.append({"transaction_id": tid, "confidence": f"{confidence:.2f}",
                               "decided_by": decided_by, "reason": reason})
        return tid

    def save(self):
        self.ledger.sort(key=lambda r: (r["date"], r["transaction_id"]))
        write_csv(self.ledger_path, LEDGER_COLS, self.ledger)
        write_csv(self.queue_path, QUEUE_COLS, self.queue)
        write_csv(self.decisions_path, DECISION_COLS, self.decisions)
        write_csv(self.rules_path, RULE_COLS, self.rules)


def _time_of(description):
    m = re.search(r"\((?:[A-Za-z ]+)?(\d{1,2}:\d{2})\)", description)
    return m.group(1) if m else ""


def find_duplicate(row, ws):
    """Same amount, date within 1 day, and the same time (5 min) or the same merchant."""
    d, amt, key = date.fromisoformat(row["date"]), float(row["amount"]), system1.merchant_key(row["description"])
    for r in ws.ledger:
        if abs(float(r["amount_thb"]) - amt) > 0.005 or abs((date.fromisoformat(r["date"]) - d).days) > 1:
            continue
        t_old, t_new = _time_of(r["description"]), row.get("time", "")
        if t_old and t_new:
            a, b = (datetime.strptime(x, "%H:%M") for x in (t_old, t_new))
            if r["date"] == row["date"] and abs((a - b).total_seconds()) <= 300:
                return r["transaction_id"]
            continue
        if system1.merchant_key(r["description"]).startswith(key) and r["date"] == row["date"]:
            return r["transaction_id"]
    for q in ws.queue:
        if q["date"] == row["date"] and abs(float(q["amount"]) - amt) < 0.005 and q.get("time", "") == row.get("time", "") \
                and q["description"] == row["description"]:
            return q["question_id"]
    return None


def cmd_ingest(ws, args):
    rows = read_csv(args.file)
    need = {"date", "description", "amount", "direction"}
    if not rows or not need <= set(rows[0]):
        sys.exit(f"{args.file} needs the columns: date,time,description,amount,direction,memo,source_reference")
    report = {"read": len(rows), "auto": [], "codex": [], "ask": [], "duplicate": [], "unreadable": []}
    qn = max([int(q["question_id"][1:]) for q in ws.queue] or [0])
    for row in rows:
        row = {k: (v or "").strip() for k, v in row.items()}
        row["direction"] = {"in": "in", "out": "out", "credit": "in", "debit": "out"}.get(row["direction"].lower(), "")
        try:
            date.fromisoformat(row["date"])
            row["amount"] = f"{abs(float(row['amount'].replace(',', ''))):.2f}"
            assert row["direction"] and float(row["amount"]) > 0
        except (ValueError, AssertionError):
            report["unreadable"].append(row)   # never guess a date, an amount, or a direction
            continue
        row.setdefault("source", args.source)
        row["source"] = row["source"] or args.source
        dup = find_duplicate(row, ws)
        if dup:
            report["duplicate"].append({"description": row["description"], "amount": row["amount"], "matches": dup})
            continue
        dec = system1.classify(row, system1.Memory(ws.ledger, ws.rules))
        brief = {"date": row["date"], "description": row["description"], "amount": row["amount"],
                 "category": dec.category, "confidence": dec.confidence}
        if dec.route == "auto":
            brief["transaction_id"] = ws.append(row, dec.transaction_type, dec.category, dec.action,
                                                dec.confidence, "system1", dec.reason)
            report["auto"].append(brief)
        else:
            qn += 1
            brief["question_id"] = f"Q{qn:03d}"
            key = system1.merchant_key(row["description"])
            twin = next((q for q in ws.queue if not q.get("same_as") and q["direction"] == row["direction"]
                         and system1.merchant_key(q["description"]) == key
                         and not system1.PERSON.search(q["description"])), None)
            ws.queue.append({**row, "question_id": brief["question_id"], "route": dec.route,
                             "same_as": twin["question_id"] if twin else "",
                             "confidence": f"{dec.confidence:.2f}", "guess_type": dec.transaction_type,
                             "guess_category": dec.category, "guess_action": dec.action, "reason": dec.reason,
                             "question": dec.question, "candidates": json.dumps(dec.candidates, ensure_ascii=False)})
            report[dec.route].append(brief)
    ws.save()
    build_state(ws, args.today)
    print(json.dumps({k: (v if k == "read" else {"count": len(v), "items": v}) for k, v in report.items()},
                     ensure_ascii=False, indent=2))


def cmd_review(ws, args):
    for q in ws.queue:
        if q.get("same_as"):
            print(f"{q['question_id']} same merchant as {q['same_as']}: {q['date']} {q['amount']}")
            continue
        print(f"{q['question_id']} [{q['route']}, {float(q['confidence']):.0%}] {q['date']} {q['description']} "
              f"{q['amount']} {q['direction']}\n      guess: {q['guess_type']}/{q['guess_category']} - {q['reason']}"
              f"\n      ask:   {q['question']}")
    if not ws.queue:
        print("Nothing is waiting.")


def _answer_one(ws, qid, t, category, action, remember, by, note=""):
    q = next((q for q in ws.queue if q["question_id"] == qid), None)
    if not q:
        print(f"{qid}: not in the queue", file=sys.stderr)
        return False
    if t not in ("income", "expense", "transfer", "investment"):
        sys.exit(f"{qid}: type must be income, expense, transfer or investment")
    if note:
        q["memo"] = (q.get("memo", "") + " " + note).strip()
    action = action or ("Buy" if t == "investment" else "")
    tid = ws.append(q, t, category, action, 1.0 if by == "user" else float(q["confidence"]), by,
                    "You answered." if by == "user" else "Codex looked at the context: " + (note or q["reason"]))
    if remember:
        pattern = system1.merchant_key(q["description"])
        ws.rules = [r for r in ws.rules if not (r["pattern"] == pattern and r["direction"] == q["direction"])]
        ws.rules.append({"pattern": pattern, "direction": q["direction"], "transaction_type": t,
                         "category": category, "action": action, "learned_on": date.today().isoformat()})
    ws.queue.remove(q)
    print(f"{qid} -> {tid} {t}/{category}" + (" (remembered)" if remember else ""))
    for twin in [x for x in ws.queue if x.get("same_as") == qid]:   # one answer covers the same merchant
        twin["same_as"] = ""
        _answer_one(ws, twin["question_id"], t, category, action, False, by, note)
    return True


def cmd_answer(ws, args):
    if args.file:
        for a in read_csv(args.file):
            _answer_one(ws, a["question_id"], a["transaction_type"], a["category"], a.get("action", ""),
                        str(a.get("remember", "")).lower() in ("1", "true", "yes"), a.get("decided_by") or "user",
                        a.get("note", ""))
    else:
        if not (args.question_id and args.type and args.category):
            sys.exit("answer needs: <question_id> --type <type> --category <category>")
        _answer_one(ws, args.question_id, args.type, args.category, args.action, args.remember, args.by, args.note)
    ws.save()
    build_state(ws, args.today)


def cmd_alerts(ws, args):
    state = build_state(ws, args.today)
    shown = [a for a in state["alerts"] if a["level"] != "upcoming" or a["days_left"] <= args.days]
    for a in shown:
        print(f"[{a['level']}] {a['message']}")
    if not shown:
        print(f"Nothing is due in the next {args.days} days.")


def build_state(ws, today):
    """One JSON file with everything the dashboard, the main agent and the other pillars need."""
    led = ws.ledger
    covered = max((date.fromisoformat(r["date"]) for r in led), default=today)
    items = recurring.detect(led, today)
    alerts = recurring.alerts(items, today, covered)
    months = defaultdict(lambda: {"income": 0.0, "refunds": 0.0, "expense": 0.0, "invested": 0.0, "by_category": defaultdict(float)})
    for r in led:
        m, amt = months[r["year_month"]], float(r["amount_thb"])
        if r["transaction_type"] == "income":
            m["refunds" if r["category"] == "Refund" else "income"] += amt   # a refund is not income
        elif r["transaction_type"] == "expense":
            m["expense"] += amt
            m["by_category"][r["category"]] += amt
        elif r["transaction_type"] == "investment":
            m["invested"] += amt if r["action"] != "Sell" else -amt
    monthly = [{"month": k, "income": round(v["income"], 2), "refunds": round(v["refunds"], 2),
                "expense": round(v["expense"], 2), "invested": round(v["invested"], 2),
                "net": round(v["income"] + v["refunds"] - v["expense"], 2),
                "by_category": {c: round(a, 2) for c, a in sorted(v["by_category"].items(), key=lambda x: -x[1])}}
               for k, v in sorted(months.items())]
    by = defaultdict(int)
    for d in ws.decisions:
        by[d["decided_by"]] += 1
    active = [i for i in items if i["kind"] != "income"]
    state = {
        "schema": "pillar1-state/1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "ledger": {"rows": len(led), "from": min((r["date"] for r in led), default=""), "to": covered.isoformat()},
        "thresholds": {"auto_at": system1.AUTO_AT, "codex_at": system1.CODEX_AT},
        "routing": {"saved_by_system1": by["system1"], "solved_by_codex": by["codex"], "answered_by_user": by["user"],
                    "waiting_for_codex": sum(q["route"] == "codex" and not q.get("same_as") for q in ws.queue),
                    "waiting_for_user": sum(q["route"] == "ask" and not q.get("same_as") for q in ws.queue)},
        "review_queue": [{**q, "confidence": float(q["confidence"]), "amount": float(q["amount"]),
                          "candidates": json.loads(q["candidates"] or "[]")} for q in ws.queue],
        "decisions": {d["transaction_id"]: {"confidence": float(d["confidence"]), "decided_by": d["decided_by"],
                                            "reason": d["reason"]} for d in ws.decisions},
        "monthly": monthly,
        "recurring": items,
        "alerts": alerts,
        "fixed_costs": {"per_month": round(sum(i["monthly_cost"] for i in active if i["kind"] != "saving"), 2),
                        "subscriptions_per_month": round(sum(i["monthly_cost"] for i in active if i["kind"] == "subscription"), 2),
                        "debt_per_month": round(sum(i["monthly_cost"] for i in active if i["kind"] == "debt"), 2)},
        "rules_learned": len(ws.rules),
        # optional profile.json: {"gross_monthly": 22000, "salary_months": 12, "social_security_monthly": 875}
        "profile": json.load(open(os.path.join(ws.dir, "profile.json"), encoding="utf-8")) if os.path.exists(os.path.join(ws.dir, "profile.json")) else {},
    }
    with open(ws.state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    return state


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ingest"); s.add_argument("file"); s.add_argument("--source", default="bank_statement")
    sub.add_parser("review")
    s = sub.add_parser("answer"); s.add_argument("question_id", nargs="?"); s.add_argument("--type")
    s.add_argument("--category"); s.add_argument("--action", default=""); s.add_argument("--note", default="")
    s.add_argument("--remember", action="store_true"); s.add_argument("--by", default="user", choices=["user", "codex"])
    s.add_argument("--file")
    s = sub.add_parser("alerts"); s.add_argument("--days", type=int, default=7)
    sub.add_parser("state")
    args = ap.parse_args()
    ws = Workspace(args.dir)
    {"ingest": cmd_ingest, "review": cmd_review, "answer": cmd_answer, "alerts": cmd_alerts,
     "state": lambda w, a: print(f"Wrote {build_state(w, a.today) and w.state_path}")}[args.cmd](ws, args)


if __name__ == "__main__":
    main()
