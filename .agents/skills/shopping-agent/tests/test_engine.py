import json
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from engine import SCHEMA, confidence, effective_price, evaluate, financial_fit, money, read_ledger

TODAY = date(2026, 11, 12)

def profile(**changes):
    return dict(income='30000', essential='15000', debt='2000', saving='3000', cash='20000',
                emergency='10000', reserved='2000', earmarked='1000', as_of='2026-11-12',
                complete=True, future_complete=True, income_kind='stable', future_extra=[], **changes)

def listing():
    return dict(name='Synthetic product', price='1000', shipping='50', discount='100',
                verified=True, shipping_verified=True, discount_verified=True, eligible=True,
                url='https://example.org/product', checked='2026-11-12')

class EngineTests(unittest.TestCase):
    def fit(self, price='9000', **changes):
        p = profile(); p.update(changes)
        return financial_fit(p, price, TODAY)

    def test_affordable(self):
        r = self.fit('5000')
        self.assertEqual((r['status'], r['available'], r['monthly_surplus'], r['months']), ('AFFORDABLE','8000','10000',0))

    def test_save_ceiling_and_earmarked_not_added(self):
        r = self.fit('11001')
        self.assertEqual((r['status'],r['months']),('SAVE_FIRST',2))

    def test_missing_not_zero(self):
        self.assertEqual(self.fit(cash='')['status'],'INSUFFICIENT_DATA')

    def test_zero_surplus(self):
        r = self.fit(income='20000')
        self.assertEqual((r['status'],r['months']),('NOT_AFFORDABLE',None))

    def test_deficit_even_with_cash(self):
        self.assertEqual(self.fit('1000',income='19000')['status'],'NOT_AFFORDABLE')

    def test_emergency_protected(self):
        self.assertEqual(self.fit('1',emergency='20000')['status'],'NOT_AFFORDABLE')

    def test_due_debt_reservation_once(self):
        self.assertEqual(self.fit('8000')['status'],'AFFORDABLE')

    def test_future_expenses_protected(self):
        r=self.fit('7000',future_extra=[{'month':1,'amount':'3000'}])
        self.assertEqual((r['status'],r['available']),('SAVE_FIRST','5000'))

    def test_future_uncovered(self):
        self.assertEqual(self.fit(future_extra=[{'month':1,'amount':'9000'}])['status'],'NOT_AFFORDABLE')

    def test_variable_income(self):
        r=self.fit(income_kind='variable',income_history=['24000','28000','30000'])
        self.assertEqual(r['monthly_surplus'],'4000')

    def test_variable_incomplete(self):
        self.assertEqual(self.fit(income_kind='variable',income_history=['30000'])['status'],'INSUFFICIENT_DATA')

    def test_stale_future_and_missing_date(self):
        for value in ('2026-09-01','2026-11-13',''):
            self.assertEqual(self.fit(as_of=value)['status'],'INSUFFICIENT_DATA')

    def test_invalid_money(self):
        for n in ('NaN','Infinity','-1','0.001',True,None):
            with self.assertRaises(ValueError): money(n)

    def test_decimal_price(self):
        l=listing();l.update(price='0.10',shipping='0.20',discount='0')
        self.assertEqual(effective_price(l,TODAY)['effective'],'0.30')

    def test_verified_price(self):
        self.assertEqual(effective_price(listing(),TODAY)['effective'],'950')

    def test_unknown_shipping(self):
        l=listing();l['shipping']=''
        self.assertIsNone(effective_price(l,TODAY)['effective'])

    def test_discount_and_price_evidence(self):
        for key,value in [('eligible',False),('discount_verified',False),('verified',False),('checked','2026-01-01'),('discount','99999')]:
            l=listing();l[key]=value
            self.assertIsNone(effective_price(l,TODAY)['effective'])

    def test_confidence_requires_source(self):
        self.assertEqual(confidence({'model':'A'},{'model':{'value':'A'}})['tier'],'LOW')
        self.assertEqual(confidence({'model':'A'},{'model':{'value':'B','source':'label'}})['conflicts'],['model'])

    def test_identity_and_listing_separate(self):
        l=listing();l['evidence']={'model':{'value':'A','source':'retailer'}}
        r=evaluate({'target':{'model':'A'},'listings':[l],'profile':profile()},TODAY)['results'][0]
        self.assertEqual((r['identification']['tier'],r['listing_match']['tier']),('LOW','HIGH'))

    def test_comparison(self):
        a,b=listing(),listing();b['price']='2000'
        r=evaluate({'listings':[a,b],'profile':profile()},TODAY)
        self.assertEqual(r['results'][1]['difference_from_lowest_verified'],'1000')
        self.assertFalse(r['cheapest_claim_supported'])

    def test_search_without_finances(self):
        r=evaluate({'listings':[listing()]},TODAY)['results'][0]
        self.assertEqual(r['price']['effective'],'950')
        self.assertEqual(r['financial']['status'],'INSUFFICIENT_DATA')

    def test_local_calculation_no_network(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            evaluate({'listings':[listing()],'profile':profile()},TODAY)

    def test_ledger_schema_quality_and_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'database.csv'
            raw=','.join(SCHEMA)+'\nTXN000001,2026-11-10,expense,synthetic,100.00,Shopping,,2026-11,manual_entry,,,,,\n'
            path.write_text(raw,encoding='utf-8')
            r=read_ledger(path,TODAY)
            self.assertEqual(r['monthly']['2026-11']['expense'],'100.00')
            self.assertFalse(r['cash_inferred'])
            self.assertEqual(path.read_text(encoding='utf-8'),raw)
            path.write_text('date,amount\n',encoding='utf-8')
            self.assertIn('schema_mismatch',read_ledger(path,TODAY)['issues'])

    def test_invalid_future_and_unconfirmed(self):
        self.assertEqual(self.fit(future_extra=[{'month':0,'amount':'1'}])['status'],'INSUFFICIENT_DATA')
        self.assertEqual(self.fit(complete=False)['status'],'INSUFFICIENT_DATA')
        self.assertEqual(self.fit(future_complete=False)['status'],'INSUFFICIENT_DATA')

    def test_ledger_stale_duplicate_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'db.csv'
            self.assertIn('ledger_unavailable',read_ledger(p,TODAY)['issues'])
            row='TXN000001,2026-01-01,income,synthetic,100,Salary,,2026-01,manual_entry,,,,,\n'
            p.write_text(','.join(SCHEMA)+'\n'+row+row,encoding='utf-8')
            issues=read_ledger(p,TODAY)['issues']
            self.assertIn('ledger_outdated',issues)
            self.assertIn('invalid_or_duplicate_transaction',issues)
