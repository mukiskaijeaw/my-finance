"""Pillar 5: find recurring charges and subscriptions in the ledger, and
raise alerts before a renewal or a due date. Reads the ledger only."""
from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import date, timedelta

from system1 import merchant_key

CADENCES = [("weekly", 7, 1), ("monthly", 30, 4), ("yearly", 365, 10)]  # name, days, tolerance
LEAD_DAYS = {"subscription": 3, "bill": 5, "debt": 5, "saving": 2, "income": 0}
SUB_WORDS = re.compile(r"netflix|spotify|youtube|disney|icloud|apple\.com|google one|chatgpt|openai|canva|\bviu\b|hbo|prime video|true ?id|premium|membership", re.I)


def _kind(row: dict) -> str:
    if row["transaction_type"] == "income":
        return "income"
    if row["transaction_type"] == "investment":
        return "saving"
    if row["category"] == "Subscriptions" or SUB_WORDS.search(row["description"]):
        return "subscription"
    if row["category"] == "Debt Repayment":
        return "debt"
    return "bill"


def _add_month(d: date, day: int) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def _next_due(last: date, cadence: str, day: int) -> date:
    if cadence == "weekly":
        return last + timedelta(days=7)
    if cadence == "yearly":
        return date(last.year + 1, last.month, min(last.day, calendar.monthrange(last.year + 1, last.month)[1]))
    return _add_month(last, day)


def detect(ledger_rows: list, today: date) -> list:
    """Return recurring items: same merchant, amount within 10%, steady interval."""
    groups = defaultdict(list)
    for r in ledger_rows:
        if r["transaction_type"] == "transfer":
            continue
        groups[(merchant_key(r["description"]), r["transaction_type"])].append(r)

    items = []
    for (key, _), rows in groups.items():
        rows.sort(key=lambda r: r["date"])
        dates = [date.fromisoformat(r["date"]) for r in rows]
        amounts = [float(r["amount_thb"]) for r in rows]
        kind = _kind(rows[-1])
        name = re.sub(r"\s*\((?:[A-Za-z ]+)?\d{1,2}:\d{2}\)", "", rows[-1]["description"]).strip()
        base = {"key": key, "name": name, "kind": kind, "category": rows[-1]["category"],
                "amount": amounts[-1], "last_paid": rows[-1]["date"], "times_seen": len(rows),
                "transaction_ids": [r["transaction_id"] for r in rows]}

        if len(rows) == 1:
            # one charge that looks like a subscription: likely new, or a trial that started to bill
            if kind == "subscription":
                items.append({**base, "cadence": "monthly", "status": "new",
                              "next_due": _add_month(dates[0], dates[0].day).isoformat(),
                              "confidence": 0.60, "monthly_cost": amounts[0],
                              "note": "Seen once. It may be a new subscription or a free trial that started to charge."})
            continue

        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        cadence = None
        for cname, days, tol in CADENCES:
            ok = sum(1 for g in gaps if abs(g - days) <= tol)
            if ok / len(gaps) >= 0.75:
                cadence, steady = cname, ok / len(gaps)
                break
        if not cadence:
            continue
        mid = sorted(amounts)[len(amounts) // 2]
        close = sum(1 for a in amounts if mid and abs(a - mid) / mid <= 0.10) / len(amounts)
        if close < 0.75:
            continue

        day = max(set(d.day for d in dates), key=[d.day for d in dates].count)
        due = _next_due(dates[-1], cadence, day)
        conf = round(min(0.99, 0.55 + 0.12 * min(len(rows), 3) + 0.04 * steady + 0.04 * close), 2)
        per_month = {"weekly": 52 / 12, "monthly": 1, "yearly": 1 / 12}[cadence]
        item = {**base, "cadence": cadence, "status": "active", "next_due": due.isoformat(),
                "confidence": conf, "monthly_cost": round(amounts[-1] * per_month, 2), "note": ""}
        if len(amounts) >= 2 and amounts[-1] != amounts[-2]:
            diff = amounts[-1] - amounts[-2]
            item["note"] = f"The price went {'up' if diff > 0 else 'down'} from {amounts[-2]:,.0f} to {amounts[-1]:,.0f} THB."
            item["price_change"] = round(diff, 2)
        items.append(item)

    items.sort(key=lambda i: i["next_due"])
    return items


def alerts(items: list, today: date, covered_until: date | None = None) -> list:
    """Alerts for the next 30 days. `covered_until` is the last date the ledger has data for."""
    out = []
    for it in items:
        if it["kind"] == "income":
            continue
        due = date.fromisoformat(it["next_due"])
        days = (due - today).days
        lead = LEAD_DAYS[it["kind"]]
        what = {"subscription": "renews", "bill": "is due", "debt": "is due", "saving": "is planned"}[it["kind"]]
        base = {"key": it["key"], "name": it["name"], "kind": it["kind"], "amount": it["amount"],
                "due": it["next_due"], "days_left": days}
        if it["status"] == "new":
            out.append({**base, "level": "check", "remind_on": (due - timedelta(days=lead)).isoformat(),
                        "message": f"New charge: {it['name']} took {it['amount']:,.0f} THB on {it['last_paid']}. "
                                   f"Do you want to keep it? It will likely charge again on {it['next_due']}."})
        elif days < 0:
            if covered_until and due > covered_until:
                out.append({**base, "level": "check", "remind_on": today.isoformat(),
                            "message": f"{it['name']} ({it['amount']:,.0f} THB) was expected on {it['next_due']}, "
                                       f"but your last statement ends on {covered_until.isoformat()}. Send a newer one to confirm."})
                continue
            out.append({**base, "level": "late", "remind_on": today.isoformat(),
                        "message": f"{it['name']} ({it['amount']:,.0f} THB) was expected on {it['next_due']} "
                                   f"but it is not in your statement. Please check that it was paid."})
        elif days <= 30:
            level = "soon" if days <= lead else "upcoming"
            when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
            msg = f"{it['name']} {what} {when} ({it['next_due']}): {it['amount']:,.0f} THB."
            if it.get("note"):
                msg += " " + it["note"]
            out.append({**base, "level": level, "remind_on": (due - timedelta(days=lead)).isoformat(), "message": msg})
    order = {"late": 0, "soon": 1, "check": 2, "upcoming": 3}
    out.sort(key=lambda a: (order[a["level"]], a["due"]))
    return out
