"""System-1: fast transaction decisions with a confidence score.

Runs on the user's machine with the Python standard library only. Nothing here
calls the network. It decides (type, category) for one transaction and says how
sure it is. The confidence picks the route:

    confidence >= AUTO_AT   -> "auto"   save without asking
    confidence >= CODEX_AT  -> "codex"  hand to Codex for a deeper look
    otherwise               -> "ask"    ask the user

Evidence, strongest first:
  1. rules the user taught it (answers to earlier questions)
  2. memory of the same merchant in the ledger
  3. built-in keywords for Thai merchants and banks
  4. a small naive-Bayes model trained on the ledger's own descriptions

This is version 0 of System-1. Any model that returns the same Decision can
replace `classify` later (for example a small fine-tuned local model).
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict

AUTO_AT = 0.90
CODEX_AT = 0.60

EXPENSE_CATEGORIES = [
    "Food/Beverage", "Groceries", "Transportation", "Housing", "Utilities", "Shopping",
    "Health", "Entertainment", "Subscriptions", "Travel", "Debt Repayment", "Transfer money", "Other",
]
INCOME_CATEGORIES = ["Salary", "Freelance", "Interest", "Refund", "Other"]

# (pattern, direction, type, category, action, confidence)
SEEDS = [
    (r"own (savings |k ?plus |scb |bank )?account|บัญชีตัวเอง|from own|to own", "any", "transfer", "Transfer money", "", 0.95),
    (r"salary|เงินเดือน|payroll", "in", "income", "Salary", "", 0.96),
    (r"interest|ดอกเบี้ย", "in", "income", "Interest", "", 0.95),
    (r"refund|คืนเงิน|reversal|cashback", "in", "income", "Refund", "", 0.92),
    (r"netflix|spotify|youtube ?premium|disney|icloud|apple\.com/bill|google one|chatgpt|openai|canva|\bviu\b|hbo|prime video|true ?id", "out", "expense", "Subscriptions", "", 0.95),
    (r"kasset|scbam|ktam|\bfund\b|กองทุน|settrade|streaming|bitkub|finnomena|\bdime\b|jitta", "out", "investment", "Fund", "Buy", 0.92),
    (r"credit card|บัตรเครดิต|\bktc\b|credit repayment|loan|สินเชื่อ|ค่างวด|installment|\bpay ?later\b", "out", "expense", "Debt Repayment", "", 0.92),
    (r"\bais\b|true ?move|dtac|\bmea\b|\bpea\b|กฟน|กฟภ|\bmwa\b|\bpwa\b|ประปา|ไฟฟ้า|internet|3bb|mobile bill", "out", "expense", "Utilities", "", 0.93),
    (r"rent\b|ค่าเช่า|ค่าห้อง|residence|apartment|หอพัก", "out", "expense", "Housing", "", 0.92),
    (r"grab ?food|line ?man|foodpanda|robinhood|7-?eleven|เซเว่น|cafe|coffee|กาแฟ|ข้าว|ก๋วยเตี๋ยว|noodle|rice\b|curry|food|restaurant|ร้านอาหาร|starbucks|\bkfc\b|mcdonald|vending|bakery|tea\b|ชา", "out", "expense", "Food/Beverage", "", 0.91),
    (r"\bgrab\b|\bbolt\b|\bbts\b|\bmrt\b|taxi|แท็กซี่|rabbit|\bptt\b|bangchak|ทางด่วน|easy ?pass|bus\b|train", "out", "expense", "Transportation", "", 0.92),
    (r"lotus|big ?c\b|makro|\btops\b|villa market|gourmet market|cj express|supermarket", "out", "expense", "Groceries", "", 0.91),
    (r"watsons|uniqlo|ikea|muji|central|the mall", "out", "expense", "Shopping", "", 0.90),
    # marketplaces and wallets sell anything, and a membership can be health, sport or a subscription: let Codex look
    (r"shopee|lazada|tiktok shop", "out", "expense", "Shopping", "", 0.80),
    (r"gym|fitness|membership|member fee", "out", "expense", "Health", "", 0.72),
    (r"hospital|โรงพยาบาล|clinic|คลินิก|pharmacy|ร้านยา|\bboots\b|dental", "out", "expense", "Health", "", 0.91),
    (r"cinema|major cineplex|\bsf\b|concert|ticketmelon|steam|playstation|nintendo", "out", "expense", "Entertainment", "", 0.90),
    (r"agoda|booking\.com|airasia|nok air|thai airways|hotel|traveloka", "out", "expense", "Travel", "", 0.90),
]

PERSON = re.compile(
    r"^(transfer (from|to) )?(นาย|นางสาว|นาง|น\.ส\.|คุณ|mr\.?|mrs\.?|ms\.?|miss|khun)\s+\S+"
    r"|^(transfer (from|to) )[A-Z][a-z]+ [A-Z][a-z]*\.?$",
    re.IGNORECASE,
)


@dataclass
class Decision:
    transaction_type: str
    category: str
    action: str
    confidence: float
    route: str
    reason: str
    question: str = ""
    candidates: list = field(default_factory=list)  # [{"transaction_type", "category", "label"}]

    def to_dict(self):
        return asdict(self)


def merchant_key(description: str) -> str:
    """Stable name for a merchant: drop the bank time stamp, refs, and digits."""
    s = re.sub(r"\((?:[A-Za-z ]+)?\d{1,2}:\d{2}\)", " ", description or "")
    s = re.sub(r"\bref\b\s*\S+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[xX*]\d{3,}", " ", s)
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"[^\w฀-๿/& ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def tokens(description: str) -> list:
    return [t for t in merchant_key(description).split(" ") if len(t) > 1]


def direction_of(row: dict) -> str:
    """Ledger row -> 'in' or 'out'."""
    t = row.get("transaction_type", "")
    if t == "income" or (t == "investment" and row.get("action") == "Sell"):
        return "in"
    if t == "transfer":
        return "in" if re.search(r"\b(in|from)\b", row.get("description", ""), re.I) else "out"
    return "out"


class Memory:
    """What System-1 has learned from the ledger and from the user's answers."""

    def __init__(self, ledger_rows: list, rules: list | None = None):
        self.rules = rules or []
        self.by_merchant = defaultdict(Counter)   # (key, dir) -> Counter[(type, category, action)]
        self.amounts = defaultdict(list)          # (key, dir) -> [amount]
        self.class_tokens = defaultdict(Counter)  # (dir, type, category, action) -> token counts
        self.class_n = Counter()
        self.vocab = set()
        for r in ledger_rows:
            if (r.get("data_quality_flag") or "").startswith("needs_review"):
                continue  # do not learn from rows nobody has confirmed
            d = direction_of(r)
            label = (r["transaction_type"], r["category"], r.get("action", ""))
            key = merchant_key(r["description"])
            self.by_merchant[(key, d)][label] += 1
            try:
                self.amounts[(key, d)].append(float(r["amount_thb"]))
            except ValueError:
                pass
            cls = (d,) + label
            self.class_n[cls] += 1
            for t in tokens(r["description"]):
                self.class_tokens[cls][t] += 1
                self.vocab.add(t)

    def bayes(self, description: str, direction: str):
        """Naive Bayes over the ledger's own words. Returns (label, probability, known_tokens)."""
        toks = tokens(description)
        known = [t for t in toks if t in self.vocab]
        classes = [c for c in self.class_n if c[0] == direction]
        if not classes or not known:
            return None, 0.0, 0
        total = sum(self.class_n[c] for c in classes)
        v = len(self.vocab) or 1
        scores = {}
        for c in classes:
            n_c = sum(self.class_tokens[c].values())
            s = math.log(self.class_n[c] / total)
            for t in known:
                s += math.log((self.class_tokens[c][t] + 1) / (n_c + v))
            scores[c] = s
        top = max(scores.values())
        norm = sum(math.exp(s - top) for s in scores.values())
        best = max(scores, key=scores.get)
        return best[1:], 1.0 / norm, len(known)


def _route(conf: float) -> str:
    return "auto" if conf >= AUTO_AT else "codex" if conf >= CODEX_AT else "ask"


def _cands(direction: str, first: tuple | None = None) -> list:
    if direction == "in":
        opts = [("income", "Freelance", "Pay for work (freelance income)"),
                ("income", "Refund", "Money returned to me (not income)"),
                ("transfer", "Transfer money", "From my own account"),
                ("income", "Salary", "Salary"),
                ("income", "Other", "Other income")]
    else:
        opts = [("expense", "Transfer money", "Money sent to a person"),
                ("expense", "Food/Beverage", "Food or drink"),
                ("expense", "Shopping", "Shopping"),
                ("expense", "Subscriptions", "A subscription"),
                ("transfer", "Transfer money", "To my own account"),
                ("expense", "Other", "Something else")]
    out = [{"transaction_type": t, "category": c, "label": l} for t, c, l in opts]
    if first:
        out = [o for o in out if (o["transaction_type"], o["category"]) != first[:2]]
        out.insert(0, {"transaction_type": first[0], "category": first[1], "label": f"{first[1]} (my best guess)"})
    return out


def classify(row: dict, memory: Memory) -> Decision:
    """row: {description, amount, direction: 'in'|'out', memo?}"""
    desc = (row.get("description") or "").strip()
    memo = (row.get("memo") or "").strip()
    text = f"{desc} {memo}".lower()
    d = row["direction"]
    amount = float(row["amount"])
    key = merchant_key(desc)
    money = f"{amount:,.2f} THB"

    def done(t, c, a, conf, reason, question="", cands=None):
        conf = round(max(0.05, min(conf, 0.99)), 2)
        route = _route(conf)
        if route != "auto" and not question:
            question = (f"{desc}: {money} {'came in' if d == 'in' else 'went out'}. "
                        f"I think it is {c}, but I am only {round(conf * 100)}% sure. What is it?")
        if route != "auto" and cands is None:
            cands = _cands(d, (t, c))
        return Decision(t, c, a, conf, route, reason, question if route != "auto" else "", cands or [])

    # 1. something the user already told us
    for r in memory.rules:
        if r["direction"] in (d, "any") and r["pattern"] and r["pattern"] in key:
            return done(r["transaction_type"], r["category"], r.get("action", ""), 0.98,
                        f"You told me before that '{r['pattern']}' is {r['category']}.")

    seen = memory.by_merchant.get((key, d))
    is_person = bool(PERSON.search(desc))
    seed = next((s for s in SEEDS if s[1] in (d, "any") and re.search(s[0], text, re.I)), None)

    # 2. the same merchant is already in the ledger
    if seen:
        n = sum(seen.values())
        label, hits = seen.most_common(1)[0]
        conf = (0.80 + 0.045 * min(n, 4)) * (hits / n)
        reason = f"Same as {hits} earlier entr{'y' if hits == 1 else 'ies'} for '{key}'."
        if seed and (seed[2], seed[3]) == label[:2]:
            conf = max(conf, seed[5]) + 0.02
        if is_person:
            conf = min(conf, 0.80)
            reason += " It is a person, so the reason can change each time."
        past = memory.amounts.get((key, d)) or []
        if len(past) >= 3:
            typical = sorted(past)[len(past) // 2]
            if typical > 0 and amount > 5 * typical:
                conf -= 0.20
                reason += f" But {money} is much more than the usual {typical:,.0f} THB."
        return done(label[0], label[1], label[2], conf, reason)

    # 3. a person, never seen before: do not guess
    who = re.sub(r"^transfer (from|to) ", "", desc, flags=re.I)
    if is_person and not seed:
        if d == "in":
            return done("income", "Other", "", 0.40, "Money from a person I have not seen before.",
                        f"{who} sent you {money}. Is it pay for work, or someone paying you back?",
                        _cands("in"))
        return done("expense", "Transfer money", "", 0.45, "Money to a person I have not seen before.",
                    f"You sent {money} to {who.rstrip('.')}. What was it for?", _cands("out"))

    # 4. built-in keywords
    if seed:
        conf, reason = seed[5], f"The name matches a known {seed[3]} merchant."
        if seed[5] < AUTO_AT:
            reason = f"The name suggests {seed[3]}, but this kind of merchant can be several things."
        if seed[3] == "Subscriptions":
            reason += " First time I see this charge, so it may be a new subscription or a trial that started to bill."
        return done(seed[2], seed[3], seed[4], conf, reason)

    # 5. words learned from the ledger
    label, p, known = memory.bayes(desc, d)
    if label and known >= 2 and p >= 0.80:
        return done(label[0], label[1], label[2], 0.55 + 0.25 * p,
                    f"The words look like earlier {label[1]} entries, but the merchant is new.")
    if d == "in":
        return done("income", "Other", "", 0.35, "I do not know this sender.",
                    f"{money} came in from '{desc}'. What kind of money is it?", _cands("in"))
    return done("expense", "Other", "", 0.35, "I do not know this merchant.",
                f"You paid {money} to '{desc}'. What was it for?", _cands("out"))
