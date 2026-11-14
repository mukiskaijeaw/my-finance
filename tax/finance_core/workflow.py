"""Deterministic evidence checks; no tax eligibility decisions or ledger writes."""
import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = 1
TX_COLUMNS = 'transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag,model,token_input,token_output'.split(',')
TAX_COLUMNS = 'tax_year,transaction_id,record_type,tax_category,amount_thb,source_reference,document_status,review_status,notes'.split(',')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.quantize(Decimal('.01')):
            raise ValueError('amount must be non-negative with at most two decimal places')
        return number.quantize(Decimal('.01'))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'invalid THB amount: {value!r}') from exc


# The Pillar 1 ledger (agent/cli.py) keeps the first 11 columns only; the
# Codex usage columns are optional and read as blank when absent.
PILLAR1_TX_COLUMNS = TX_COLUMNS[:11]


def load_csv(path, columns, optional=False):
    if optional and not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        short = columns is TX_COLUMNS and reader.fieldnames == PILLAR1_TX_COLUMNS
        if reader.fieldnames != columns and not short:
            raise ValueError(f'{path.name}: unexpected CSV schema')
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f'{path.name}: malformed CSV row')
    if short:
        rows = [{c: r.get(c, '') for c in columns} for r in rows]
    return rows


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def analyze(transactions, tax_rows, evidence):
    tasks = {}
    tx_by_id = {}

    def add(kind, key, title, question, rows, facts=None):
        task_id = 'TASK-' + digest([kind, key])[:16]
        task = dict(id=task_id, kind=kind, title=title, question=question,
                    transaction_ids=sorted({r['transaction_id'] for r in rows if r.get('transaction_id')}),
                    source_references=sorted({r['source_reference'] for r in rows if r.get('source_reference')}),
                    facts=facts or {})
        task['fingerprint'] = digest([task, rows])
        tasks[task_id] = task

    duplicates = defaultdict(list)
    recurring = defaultdict(list)
    salary = defaultdict(list)
    amounts = {}
    for r in transactions:
        tid = r['transaction_id']
        if not re.fullmatch(r'TXN\d{6}', tid) or tid in tx_by_id:
            raise ValueError(f'invalid or repeated transaction_id: {tid}')
        tx_by_id[tid] = r
        d = date.fromisoformat(r['date'])
        if d.isoformat() != r['date'] or r['year_month'] != r['date'][:7]:
            raise ValueError(f'{tid}: inconsistent date/year_month')
        amounts[tid] = money(r['amount_thb'])
        if r['transaction_type'] not in ('income', 'expense', 'investment', 'transfer'):
            raise ValueError(f'{tid}: invalid transaction type')
        if r['transaction_type'] == 'investment' and r['action'] not in ('Buy', 'Sell'):
            raise ValueError(f'{tid}: investment requires Buy or Sell')
        if r['transaction_type'] == 'investment' and amounts[tid] <= 0:
            raise ValueError(f'{tid}: investment amount must be positive')
        name = ' '.join(r['description'].casefold().split())
        # A match is a question, never an automatic deletion.
        if name:
            duplicates[(r['date'], str(amounts[tid]), name, r['transaction_type'])].append(r)
        if r['data_quality_flag']:
            add('transaction_review', tid, 'ตรวจรายละเอียดรายการ', r['data_quality_flag'], [r])
        if r['transaction_type'] == 'income' and r['category'] == 'Salary':
            salary[str(d.year + 543)].append(r)
        if r['transaction_type'] == 'expense' and name and not r['data_quality_flag']:
            recurring[(name, r['category'])].append(r)

    for key, rows in duplicates.items():
        if len(rows) > 1:
            add('possible_duplicate', list(key), 'พบรายการคล้ายกัน',
                'เป็นการจ่ายคนละครั้ง หรือบันทึกรายการเดียวกันซ้ำ?', rows)

    # At least three consecutive months; repeated payments within a month are ambiguous.
    for key, rows in recurring.items():
        rows = sorted(rows, key=lambda r: r['date'])
        months = [int(r['date'][:4]) * 12 + int(r['date'][5:7]) for r in rows]
        if len(rows) >= 3 and len(set(months)) == len(months) and all(b-a == 1 for a, b in zip(months, months[1:])):
            days = [int(r['date'][8:]) for r in rows]
            if max(days) - min(days) <= 4:
                add('recurring_candidate', list(key), 'อาจเป็นรายจ่ายประจำ',
                    'เป็น subscription หรือรายจ่ายประจำจริงไหม และวันต่ออายุตามสัญญาคือวันใด?', rows,
                    {'last_amount_thb': str(amounts[rows[-1]['transaction_id']]),
                     'amount_changed': len({amounts[r['transaction_id']] for r in rows}) > 1,
                     'note': 'ยอดเปลี่ยนอาจเกิดจากราคา ภาษี หรืออัตราแลกเปลี่ยน; ยังไม่สร้างตารางเตือน'})

    totals = defaultdict(lambda: defaultdict(Decimal))
    for r in tax_rows:
        if not re.fullmatch(r'\d{4}', r['tax_year']):
            raise ValueError('tax row requires Buddhist Era tax_year')
        if int(r['tax_year']) < 2400:
            raise ValueError('tax_year must use Buddhist Era')
        # Missing amounts are allowed for candidates; they are never treated as zero.
        amount = money(r['amount_thb']) if r['amount_thb'] else None
        status = r['review_status']
        if status not in ('confirmed', 'needs_review', 'source_snapshot', 'excluded'):
            raise ValueError('unknown tax review_status')
        if status in ('source_snapshot', 'excluded'):
            continue
        tid = r['transaction_id']
        if tid and tid not in tx_by_id:
            add('missing_transaction', digest(r), 'หา transaction ที่อ้างอิงไม่พบ',
                'รายการภาษีนี้อ้างถึงธุรกรรมใด?', [r])
        if tid in tx_by_id and str(int(tx_by_id[tid]['date'][:4]) + 543) != r['tax_year']:
            add('tax_year_mismatch', digest(r), 'ปีรายการกับปีภาษีต่างกัน',
                'ตรวจปีภาษีและเอกสารประกอบก่อนใช้รายการนี้', [r, tx_by_id[tid]])
        if r['record_type'] in ('income', 'deduction', 'tax_paid'):
            bucket = f"{status}_{r['record_type']}"
            if amount is not None:
                totals[r['tax_year']][bucket] += amount
            if status == 'needs_review' or r['document_status'] != 'available' or not r['source_reference'] or amount is None:
                add('tax_evidence', digest(r), 'ตรวจหลักฐานภาษี: ' + r['tax_category'],
                    'มีเอกสารของปีนี้ ยอดจริง และแหล่งกฎทางการที่ตรวจแล้วหรือยัง?', [r],
                    {'tax_year': r['tax_year'], 'review_status': status,
                     'document_status': r['document_status'], 'amount_thb': r['amount_thb']})

    documents = evidence.get('salary_documents', [])
    if evidence.get('schema_version', VERSION) != VERSION or not isinstance(documents, list):
        raise ValueError('unsupported evidence schema')
    used_ids, doc_ids = set(), set()
    for doc in documents:
        required = ('id', 'tax_year', 'source_reference', 'transaction_ids', 'gross_income_thb', 'withholding_thb', 'other_withheld_thb')
        if any(k not in doc for k in required) or not doc['source_reference']:
            raise ValueError('salary document missing required fields; use the evidence template')
        if doc['id'] in doc_ids:
            raise ValueError('duplicate document id')
        doc_ids.add(doc['id'])
        ids = doc['transaction_ids']
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or used_ids.intersection(ids):
            raise ValueError('salary document transaction links must be unique and non-empty')
        if any(i not in tx_by_id for i in ids):
            raise ValueError('salary document links unknown transaction')
        linked = [tx_by_id[i] for i in ids]
        if any(r not in salary[str(doc['tax_year'])] for r in linked):
            raise ValueError('salary document links non-salary or different tax year')
        used_ids.update(ids)
        gross, withheld, other = (money(doc[k]) for k in required[-3:])
        expected = gross - withheld - other
        if expected < 0:
            raise ValueError('salary deductions exceed gross')
        received = sum((amounts[i] for i in ids), Decimal(0))
        facts = {'document_id': doc['id'], 'tax_year': str(doc['tax_year']),
                 'document_source': doc['source_reference'], 'gross_income_thb': str(gross),
                 'expected_net_thb': str(expected), 'received_thb': str(received),
                 'difference_thb': str(received - expected)}
        # Matching arithmetic does not establish assessable income or deduction rights.
        if received != expected:
            add('salary_mismatch', doc['id'], 'ยอดเงินเดือนยังเทียบไม่ลงตัว',
                'เอกสารครอบคลุมรายการที่เลือกครบไหม หรือยังมีรายการหัก/รับอื่น?', linked, facts)
    for year, rows in salary.items():
        uncovered = [r for r in rows if r['transaction_id'] not in used_ids]
        if uncovered:
            add('salary_document', year, 'ยังไม่มีเอกสารเทียบเงินเดือน',
                'ขอข้อมูลจากสลิปเงินเดือนหรือ 50 ทวิที่ครอบคลุมรายการเหล่านี้ พร้อมรายการหักจริง', uncovered,
                {'tax_year': year})
    return tasks, {year: {k: str(v) for k, v in values.items()} for year, values in totals.items()}


def scan(folder):
    transactions = load_csv(folder / 'database.csv', TX_COLUMNS)
    tax_rows = load_csv(folder / 'tax_preparation.csv', TAX_COLUMNS, optional=True)
    evidence = read_json(folder / 'finance_evidence.json', {'schema_version': VERSION})
    state_path = folder / 'finance_review.json'
    state = read_json(state_path, {'schema_version': VERSION, 'tasks': {}, 'audit': []})
    if state.get('schema_version') != VERSION:
        raise ValueError('unsupported review state schema')
    findings, totals = analyze(transactions, tax_rows, evidence)
    inputs = digest([transactions, tax_rows, evidence])
    now = datetime.now(timezone.utc).isoformat()
    previous = state['tasks']
    for tid, task in findings.items():
        old = previous.get(tid, {})
        unchanged = old.get('fingerprint') == task['fingerprint'] and old.get('status') != 'resolved'
        task.update(status=old.get('status', 'open') if unchanged else 'open',
                    first_seen=old.get('first_seen', now))
        if unchanged and 'review' in old:
            task['review'] = old['review']
    for tid, old in previous.items():
        if tid not in findings:
            findings[tid] = dict(old, status='resolved')
    changed = inputs != state.get('input_digest') or findings != previous
    if changed:
        state.update(input_digest=inputs, tasks=findings, tax_totals=totals, last_scan=now)
        state['audit'].append({'at': now, 'action': 'scan', 'input_digest': inputs,
                               'open_count': sum(t['status'] == 'open' for t in findings.values())})
        atomic_json(state_path, state)
    return state


def render_report(state, limit=20):
    priority = {'salary_mismatch': 0, 'possible_duplicate': 1, 'missing_transaction': 2,
                'tax_year_mismatch': 3, 'salary_document': 4, 'tax_evidence': 5,
                'recurring_candidate': 6, 'transaction_review': 7}
    active = sorted((t for t in state['tasks'].values() if t['status'] != 'resolved'),
                    key=lambda t: (t['status'] != 'open', priority.get(t['kind'], 99), t['id']))
    lines = ['# งานการเงินที่ต้องตรวจ', '',
             'ผลคัดกรองจากข้อมูลในเครื่อง การกด reviewed ไม่ยืนยันสิทธิภาษีหรือแก้บัญชี', '',
             f"ตรวจล่าสุด: {state['last_scan']}", '',
             f'งานที่ยังแสดงอยู่ {len(active)} รายการ · แสดงรายละเอียด {min(limit, len(active))} รายการแรก', '',
             'ธงคุณภาพเดิมเป็นรายการชวนตรวจ ไม่ใช่ข้อยืนยันว่าบันทึกผิด', '',
             '| ประเภทงาน | จำนวน |', '| --- | ---: |']
    for kind, count in Counter(t['kind'] for t in active).items():
        lines.append(f'| {kind} | {count} |')
    lines.append('')
    for task in active[:limit]:
        lines += [f"## {task['title']} ({task['status']})", '',
                  f"ID: {task['id']}", '', task['question'], '',
                  'รายการ: ' + ', '.join(task['transaction_ids']), '',
                  'หลักฐาน: ' + ', '.join(task['source_references']), '']
        if task['facts']:
            lines += ['```json', json.dumps(task['facts'], ensure_ascii=False, indent=2), '```', '']
        if 'review' in task:
            lines += ['ผลตรวจ: ' + task['review']['note'], '']
    if not any(t['status'] != 'resolved' for t in state['tasks'].values()):
        lines += ['ไม่พบงานค้างตามเงื่อนไขที่ระบบตรวจได้; ไม่ใช่การรับรองว่าข้อมูลครบทุกด้าน', '']
    lines += ['## ยอดภาษีแยกตามสถานะ', '', 'ไม่รวม snapshot, excluded หรือแถว rollup; ยอดว่างไม่ถูกแทนเป็นศูนย์', '',
              '```json', json.dumps(state.get('tax_totals', {}), ensure_ascii=False, indent=2), '```', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Local finance review workflow')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('scan', help='Refresh tasks from CSVs and optional evidence JSON')
    review = commands.add_parser('review', help='Record a review note; does not grant tax eligibility')
    review.add_argument('task_id')
    review.add_argument('--note', required=True)
    report = commands.add_parser('report', help='Print local review report')
    report.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    folder = args.workspace.resolve()
    # Serialize scan/review; a terminated process leaves a lock to inspect explicitly.
    lock = folder / '.finance_review.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        parser.exit(2, 'Review workflow already locked. Check the running process before removing .finance_review.lock\n')
    try:
        os.close(fd)
        state = scan(folder)
        if args.command == 'review':
            if not args.note.strip():
                raise ValueError('review note cannot be empty')
            task = state['tasks'].get(args.task_id)
            if not task or task['status'] == 'resolved':
                raise ValueError('task missing or already resolved; run report for current IDs')
            task.update(status='reviewed', review={'note': args.note, 'at': datetime.now(timezone.utc).isoformat()})
            state['audit'].append({'action': 'review', 'task_id': args.task_id, **task['review']})
            atomic_json(folder / 'finance_review.json', state)
        if args.command == 'report':
            if args.limit < 1:
                raise ValueError('report limit must be positive')
            print(render_report(state, args.limit))
        else:
            print(json.dumps({'tasks': dict(Counter(t['status'] for t in state['tasks'].values())),
                              'state': str(folder / 'finance_review.json')}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'Review failed: {exc}\n')
    finally:
        lock.unlink()
