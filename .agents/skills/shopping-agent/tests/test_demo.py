import contextlib
import io
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shopping import run_demo, render, main, run_request

class DemoTests(unittest.TestCase):
    def test_demo_isolated_from_real_finance_and_network(self):
        with (patch('shopping.load_finance',side_effect=AssertionError('no real data')),
              patch('socket.socket',side_effect=AssertionError('no network'))):
            request,report=run_demo(date(2026,11,12))
        self.assertEqual(report['data_mode'],'demo')
        small,large=[x['financial'] for x in report['results']]
        self.assertEqual((small['status'],small['available'],small['remaining_after_purchase'],small['spending_percent']),
                         ('AFFORDABLE','200','111','44.50'))
        self.assertEqual((large['status'],large['months'],large['savings_progress']['remaining']),('SAVE_FIRST',1,'79'))

    def test_demo_card_clearly_labeled_no_fake_store_links(self):
        request,report=run_demo(date(2026,11,12))
        text=render(request,report)
        self.assertTrue(text.startswith('> **DEMO'))
        self.assertIn('ทั้งหมดเป็นข้อมูลจำลอง',text)
        self.assertNotIn('https://example.invalid',text)

    def test_demo_does_not_modify_fixture(self):
        p=Path(__file__).resolve().parents[1]/'tests/fixtures/demo.json'
        before=p.read_bytes()
        request,_=run_demo(date(2030,1,1))
        self.assertEqual(request['profile']['as_of'],'2030-01-01')
        self.assertEqual(p.read_bytes(),before)

    def test_real_mode_missing_data_never_falls_back_to_demo(self):
        with patch('shopping.load_finance',return_value={'profile':{},'ledger':{'issues':[]},'issues':[]}):
            _,report=run_request({'include_financial':True,'listings':[]},date(2026,11,12))
        self.assertNotIn('data_mode',report)
        self.assertEqual(report['results'],[])

    def test_demo_cli_markdown_and_reject_profile(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['demo','--format','markdown']),0)
        self.assertIn('DEMO',out.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['demo','--profile-path','real.json']),2)

if __name__=='__main__': unittest.main()
