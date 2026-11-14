import tempfile
import unittest
from pathlib import Path
from server import Dashboard
from chat import respond

class ExpenseInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Dashboard(Path(self.temp.name)/'local/test.sqlite3')
    def add(self,name='Custom expense',amount='800',kind='expense',period='monthly'):
        return self.app.expense_summary(dict(item=dict(name=name,amount=amount,kind=kind,period=period)))
    def test_empty_by_default_even_when_financial_demo_exists(self):
        state=self.app.state();self.assertEqual(state['leaks']['source'],'none')
        self.assertEqual(state['leaks']['analysis']['categories'],[]);self.assertEqual(state['leaks']['analysis']['subscriptions'],[])
        self.assertEqual(state['leaks']['simulation']['controls'],[]);self.assertEqual(state['leaks']['items'],[])
        self.assertEqual(state['leaks']['simulation']['states'],{});self.assertEqual(state['leaks']['status'],'INSUFFICIENT_DATA')
        self.assertEqual(state['daily']['initial']['available_month'],'6500')
    def test_custom_category_percentage_uses_only_user_amount(self):
        report=self.add('Books','800');self.assertEqual(report['analysis']['categories'][0]['name'],'Books')
        self.assertIsNone(report['analysis']['categories'][0]['count'])
        self.assertEqual(report['simulation']['states']['10']['monthly'],'80.00')
        self.assertEqual(report['simulation']['states']['100']['monthly'],'800.00')
    def test_no_small_purchase_heuristic_or_preset_categories(self):
        r=self.add('Transport','15000');self.assertEqual(len(r['simulation']['controls']),1)
        self.assertEqual(r['simulation']['states']['20']['monthly'],'3000.00')
        self.assertNotIn('Coffee',str(r));self.assertNotIn('359',str(r))
    def test_subscription_period_explicit_and_annual_amount_exact(self):
        report=self.add('User service','100','subscription','annual')
        self.assertEqual(report['simulation']['states']['1']['monthly'],'8.33')
        self.assertEqual(report['simulation']['states']['1']['annual'],'100.00')
        self.assertEqual(report['analysis']['categories'],[])
    def test_multiple_user_items_do_not_double_count(self):
        self.add('Books','800');report=self.add('Service','100','subscription','monthly')
        self.assertEqual(report['simulation']['states']['10,1']['monthly'],'180.00')
    def test_invalid_input_does_not_change_memory(self):
        for item in (dict(name='bad',amount='-1',kind='expense',period='monthly'),dict(name='bad',amount='100',kind='subscription',period='unknown'),dict(name=[],amount='100',kind='expense',period='monthly')):
            with self.assertRaises(ValueError):self.app.expense_summary(dict(item=item))
        self.assertEqual(self.app.expense_summaries,[])
    def test_duplicate_or_excess_categories_do_not_overwrite(self):
        self.add('Books');self.add('Transport')
        with self.assertRaises(ValueError):self.add('Third')
        with self.assertRaises(ValueError):self.add('Books')
        self.assertEqual(len(self.app.expense_summaries),2)
    def test_remove_changes_only_analysis(self):
        r=self.add();ident=r['items'][0]['id']
        result=self.app.expense_summary(dict(action='remove',id=ident))
        self.assertEqual(result['source'],'none');self.assertFalse(self.app.store.path.exists())
        self.assertEqual(self.app.state()['daily']['initial']['available_month'],'6500')
    def test_no_history_does_not_invent_expenses_in_chat(self):
        r=respond(self.app,dict(message='ช่วยลดรายจ่าย'));self.assertIn('ยังไม่มีข้อมูล',r['reply'])
        self.assertEqual(r['data']['items'],[])
    def test_new_instance_does_not_reuse_user_data(self):
        self.add();other=Dashboard(Path(self.temp.name)/'local/other.sqlite3')
        self.assertEqual(other.state()['leaks']['items'],[])

if __name__=='__main__':unittest.main()
