import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from engine import SCHEMA, effective_price, financial_fit, confidence, when_can_afford, compare_financial_impact
from shopping import product_query, load_finance, run_request, render, save_watchlist, main
from test_engine import profile, listing, TODAY

class ChatTests(unittest.TestCase):
    def test_named_financial_functions(self):
        self.assertEqual(when_can_afford(profile(),'11001',TODAY)['months'],2)
        results=compare_financial_impact(profile(),['5000','9000',None],TODAY)
        self.assertEqual(results[0]['goal_impact'],'protected')
        self.assertEqual(results[1]['difference_from_lowest_verified'],'4000')
        self.assertEqual(results[2]['status'],'INSUFFICIENT_DATA')

    def finance_dir(self, root):
        root=Path(root)
        (root/'AGENTS.md').write_text('Synthetic local rules',encoding='utf-8')
        (root/'database.csv').write_text(','.join(SCHEMA)+'\n',encoding='utf-8')
        return root

    def test_query_rejects_financial_fields(self):
        for key in ('profile','income','cash','budget','transaction','description'):
            with self.assertRaises(ValueError): product_query({'model':'A',key:'private'})
        self.assertEqual(product_query({'model':'A','color':'black'}),'A black ประเทศไทย')

    def test_query_nested_values_rejected(self):
        with self.assertRaises(ValueError): product_query({'model':{'income':'secret'}})

    def test_price_only_does_not_read_finances(self):
        with patch('shopping.load_finance',side_effect=AssertionError('do not access finance')):
            request,report=run_request({'profile':{'income':'private'},'listings':[listing()]},TODAY)
        self.assertNotIn('profile',request)
        output=render(request,report)
        self.assertNotIn('Financial Fit',output)
        self.assertNotIn('private',output)
        self.assertIn('950',output)

    def test_financial_request_reads_pillar1_each_time(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.finance_dir(d)
            with patch('shopping.read_ledger',wraps=__import__('engine').read_ledger) as read:
                for _ in range(2):
                    req,rep=run_request({'include_financial':True,'profile':profile(),'listings':[listing()]},TODAY,root)
                self.assertEqual(read.call_count,2)
            self.assertEqual(rep['results'][0]['financial']['status'],'AFFORDABLE')
            self.assertIn('no_valid_transactions',rep['data_quality']['ledger'])
            self.assertIn('Pillar 1',render(req,rep))

    def test_profile_supported_and_legacy_not_silently_used(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.finance_dir(d);path=root/'financial_profile.json'
            path.write_text(json.dumps({'monthly_net_income':999999}),encoding='utf-8')
            result=load_finance(root,TODAY,path)
            self.assertEqual(result['profile'],{})
            self.assertIn('profile_unavailable_or_unsupported',result['issues'])
            path.write_text(json.dumps({'schema_version':1,'profile':profile()}),encoding='utf-8')
            self.assertEqual(load_finance(root,TODAY,path)['profile']['cash'],'20000')
            with self.assertRaises(ValueError): load_finance(root,TODAY,root.parent/'profile.json')

    def test_missing_rules_prevents_finance_read(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): load_finance(d,TODAY)

    def test_watchlist_requires_consent_and_excludes_finance(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'watchlist.json'
            with self.assertRaises(ValueError): save_watchlist(path,{'model':'A'})
            self.assertFalse(path.exists())
            with self.assertRaises(ValueError): save_watchlist(path,{'model':'A','income':'private'},True)
            result=save_watchlist(path,{'model':'A'},True)
            self.assertFalse(result['monitoring'])
            self.assertNotIn('profile',path.read_text())
            with self.assertRaises(FileExistsError): save_watchlist(path,{'model':'B'},True)
            with self.assertRaises(ValueError): save_watchlist(Path(d)/'database.csv',{'model':'A'},True)

    def test_ineligible_coupon_never_reduces_estimate(self):
        p=listing();p['eligible']=False
        r=effective_price(p,TODAY)
        self.assertIsNone(r['effective']);self.assertEqual(r['estimate'],'1050')

    def test_unknown_discount_explicit(self):
        p=listing();p['discount']=None
        self.assertIn('discount_unknown',effective_price(p,TODAY)['issues'])

    def test_missing_future_not_treated_as_empty(self):
        p=profile();p.pop('future_extra')
        self.assertEqual(financial_fit(p,'1000',TODAY)['status'],'INSUFFICIENT_DATA')

    def test_optional_earmarked_and_inconsistent_earmarked(self):
        p=profile();p.pop('earmarked')
        self.assertEqual(financial_fit(p,'18000',TODAY)['months'],1)
        p['earmarked']='30000'
        self.assertEqual(financial_fit(p,'1000',TODAY)['status'],'INSUFFICIENT_DATA')

    def test_no_zero_division(self):
        p=profile();p['cash']='12000';p['earmarked']='0'
        r=financial_fit(p,'1000',TODAY)
        self.assertEqual(r['status'],'SAVE_FIRST');self.assertIsNone(r['spending_percent'])

    def test_evidence_missing_variant_not_high(self):
        self.assertEqual(confidence({'model':'A','size':'42'},{'model':{'value':'A','source':'label'}})['tier'],'MEDIUM')
        self.assertEqual(confidence({'model':'A'},{'model':{'value':'A','source':' '}})['tier'],'LOW')

    def test_cli_stdin_markdown_end_to_end_no_server(self):
        request={'listings':[listing()]}
        cp=subprocess.run([sys.executable,str(ROOT/'scripts/shopping.py'),'evaluate','--format','markdown'],
                          input=json.dumps(request),text=True,capture_output=True,encoding='utf-8')
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertIn('| สินค้า/รุ่น |',cp.stdout)
        self.assertNotIn('Financial Fit',cp.stdout)

    def test_cli_financial_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            self.finance_dir(d)
            p=profile();p['as_of']=__import__('shopping').today().isoformat()
            l=listing();l['checked']=p['as_of']
            cp=subprocess.run([sys.executable,str(ROOT/'scripts/shopping.py'),'evaluate','--finance-dir',d,'--format','markdown'],
                              input=json.dumps({'include_financial':True,'profile':p,'listings':[l]}),
                              text=True,capture_output=True,encoding='utf-8')
            self.assertEqual(cp.returncode,0,cp.stderr);self.assertIn('AFFORDABLE',cp.stdout)

    def test_cli_bad_json(self):
        with patch('sys.stdin',io.StringIO('{bad')),contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(['evaluate']),2)
        self.assertIn('error',err.getvalue())

    def test_full_pipeline_no_network_or_financial_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.finance_dir(d)
            before={p.name:p.read_bytes() for p in root.iterdir()}
            with patch('socket.socket',side_effect=AssertionError('network forbidden')):
                run_request({'include_financial':True,'profile':profile(),'listings':[listing()]},TODAY,root)
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})

    def test_markdown_untrusted_text_escaped(self):
        l=listing();l.update(name='bad|row\n<script>',url='javascript:alert(1)')
        req,rep=run_request({'listings':[l]},TODAY)
        output=render(req,rep)
        self.assertNotIn('<script>',output);self.assertNotIn('javascript:',output)

if __name__=='__main__': unittest.main()
