import csv
import json
import tempfile
import unittest
from pathlib import Path

from finance_core.workflow import TX_COLUMNS, TAX_COLUMNS, analyze, render_report, scan, money


def tx(tid='TXN000001', **fields):
    row = dict.fromkeys(TX_COLUMNS, '')
    row.update(transaction_id=tid, date='2026-09-25', year_month='2026-09',
               transaction_type='income', category='Salary', amount_thb='28000.00',
               description='Synthetic salary', source='demo', source_reference='synthetic.csv')
    row.update(fields)
    return row


def tax(**fields):
    row = dict.fromkeys(TAX_COLUMNS, '')
    row.update(tax_year='2569', record_type='deduction', tax_category='Synthetic insurance',
               amount_thb='100.00', document_status='missing', review_status='needs_review')
    row.update(fields)
    return row


def evidence(**fields):
    doc = dict(id='DEMO-01', tax_year='2569', source_reference='synthetic-payslip',
               transaction_ids=['TXN000001'], gross_income_thb='30000.00',
               withholding_thb='1000.00', other_withheld_thb='1000.00')
    doc.update(fields)
    return {'schema_version': 1, 'salary_documents': [doc]}


class WorkflowTests(unittest.TestCase):
    def test_salary_reconciliation_does_not_change_cash_or_create_deduction(self):
        rows = [tx()]
        tasks, totals = analyze(rows, [], evidence())
        self.assertEqual(tasks, {})
        self.assertEqual(totals, {})
        self.assertEqual(rows[0]['amount_thb'], '28000.00')
        tasks, _ = analyze(rows, [], evidence(other_withheld_thb='0.00'))
        task = next(iter(tasks.values()))
        self.assertEqual(task['kind'], 'salary_mismatch')
        self.assertEqual(task['facts']['difference_thb'], '-1000.00')

    def test_salary_links_cannot_double_count_or_cross_years(self):
        docs = evidence()
        docs['salary_documents'].append(dict(docs['salary_documents'][0], id='second'))
        with self.assertRaises(ValueError):
            analyze([tx()], [], docs)
        with self.assertRaises(ValueError):
            analyze([tx()], [], evidence(tax_year='2568'))

    def test_tax_totals_separate_candidates_and_exclude_snapshots_rollups(self):
        rows = [tax(), tax(amount_thb='200.00', review_status='confirmed', document_status='available', source_reference='demo'),
                tax(amount_thb='999.00', review_status='source_snapshot'),
                tax(amount_thb='500.00', record_type='deduction_total'), tax(amount_thb='')]
        tasks, totals = analyze([], rows, {})
        self.assertEqual(totals['2569'], {'needs_review_deduction': '100.00', 'confirmed_deduction': '200.00'})
        self.assertTrue(any(t['facts'].get('amount_thb') == '' for t in tasks.values()))

    def test_duplicate_normalizes_amount_and_does_not_delete(self):
        rows = [tx(amount_thb='28000.0'), tx('TXN000002', amount_thb='28000.00')]
        tasks, _ = analyze(rows, [], {})
        self.assertEqual(sum(t['kind'] == 'possible_duplicate' for t in tasks.values()), 1)
        self.assertEqual(len(rows), 2)

    def test_recurring_is_only_candidate_and_excludes_transfers(self):
        rows = [tx(f'TXN00000{i}', date=f'2026-0{i}-05', year_month=f'2026-0{i}',
                   transaction_type='expense', category='AI', description='Synthetic service', amount_thb='120.00')
                for i in range(1, 4)]
        tasks, _ = analyze(rows, [], {})
        self.assertEqual([t['kind'] for t in tasks.values()], ['recurring_candidate'])
        for r in rows:
            r['transaction_type'] = 'transfer'
        self.assertEqual(analyze(rows, [], {})[0], {})

    def test_invalid_critical_data_is_rejected(self):
        for value in ['NaN', 'Infinity', '-1.00', '1.001']:
            with self.assertRaises(ValueError):
                money(value)
        with self.assertRaises(ValueError):
            analyze([tx(year_month='2026-01')], [], {})

    def test_report_keeps_reviewed_visible_and_bounds_detail(self):
        tasks, totals = analyze([tx(data_quality_flag='needs_review: source')], [], {})
        state = dict(tasks=tasks, tax_totals=totals, last_scan='demo')
        for t in tasks.values():
            t['status'] = 'reviewed'
        rendered = render_report(state, 1)
        self.assertEqual(rendered.count('ID: TASK-'), 1)
        self.assertIn('(reviewed)', rendered)

    def test_retry_review_reopen_and_failed_scan_preserve_ledgers(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            def write(rows):
                with (folder / 'database.csv').open('w', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=TX_COLUMNS)
                    w.writeheader()
                    w.writerows(rows)
            write([tx(data_quality_flag='needs_review: category')])
            (folder / 'tax_preparation.csv').write_text(','.join(TAX_COLUMNS) + '\n')
            ledger = (folder / 'database.csv').read_bytes()
            state = scan(folder)
            scan(folder)
            self.assertEqual((folder / 'database.csv').read_bytes(), ledger)
            task = next(t for t in state['tasks'].values() if t['kind'] == 'transaction_review')
            task['status'] = 'reviewed'
            task['review'] = {'note': 'user explanation'}
            (folder / 'finance_review.json').write_text(json.dumps(state))
            same = scan(folder)
            self.assertEqual(same['tasks'][task['id']]['status'], 'reviewed')
            self.assertEqual(len(same['audit']), 1)
            write([tx(amount_thb='29000.00', data_quality_flag='needs_review: category')])
            self.assertEqual(scan(folder)['tasks'][task['id']]['status'], 'open')
            write([tx()])
            self.assertEqual(scan(folder)['tasks'][task['id']]['status'], 'resolved')
            saved = (folder / 'finance_review.json').read_bytes()
            write([tx(amount_thb='NaN')])
            with self.assertRaises(ValueError):
                scan(folder)
            self.assertEqual((folder / 'finance_review.json').read_bytes(), saved)

    def test_reads_pillar1_ledger_without_usage_columns_and_missing_tax_file(self):
        from finance_core.workflow import PILLAR1_TX_COLUMNS
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with (folder / 'database.csv').open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=PILLAR1_TX_COLUMNS, extrasaction='ignore')
                w.writeheader()
                w.writerow(tx())
            state = scan(folder)
            kinds = {t['kind'] for t in state['tasks'].values()}
            self.assertEqual(kinds, {'salary_document'})
            self.assertFalse((folder / 'tax_preparation.csv').exists())


if __name__ == '__main__':
    unittest.main()
