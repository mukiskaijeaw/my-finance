import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from server import Dashboard,make_server
from goal_engine import target_day,today_bangkok

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Dashboard(Path(self.temp.name)/'local/demo.sqlite3')
        self.server=make_server(0,self.app);threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown();self.server.server_close()
    def request(self,path,data=None,token=True,origin=None):
        headers={}
        if data is not None:headers={'Content-Type':'application/json','Origin':origin or self.url,'X-Dashboard-Token':self.app.token if token else ''}
        request=Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        return urlopen(request,timeout=10)
    def test_state_is_demo_no_default_goal_no_writes(self):
        with self.request('/api/state') as r:state=json.load(r)
        self.assertEqual(state['mode'],'DEMO');self.assertEqual(state['goals']['goals'],[])
        self.assertEqual(state['daily']['initial']['available_month'],'6500');self.assertFalse(self.app.store.path.exists())
    def test_static_assets_and_private_files_denied(self):
        for path in ('/','/app.js','/style.css','/chat.js','/chat.css','/expense-ui.js'):
            with self.request(path) as r:self.assertEqual(r.status,200);self.assertIn("connect-src 'self'",r.headers['Content-Security-Policy'])
        for path in ('/assets/wallet-normal.png','/assets/wallet-angry.png'):
            with self.request(path) as r:
                self.assertEqual(r.status,200);self.assertEqual(r.headers['Content-Type'],'image/png');self.assertEqual(r.read(8),b'\x89PNG\r\n\x1a\n')
        for path in ('/../database.csv','/api/../financial_profile.json','/server.py'):
            with self.assertRaises(HTTPError) as e:self.request(path)
            self.assertEqual(e.exception.code,404)
    def test_cross_origin_and_missing_token_rejected(self):
        for options in (dict(token=False),dict(origin='https://example.org')):
            with self.assertRaises(HTTPError) as e:self.request('/api/review',{},**options)
            self.assertEqual(e.exception.code,403)
    def goal(self):return dict(goal_name='Dashboard test',goal_category='general',target_amount='300',saved_amount='0',target_date=target_day('สิ้นเดือน',today_bangkok()).isoformat(),funding_source='free_cash')
    def test_review_confirm_shared_budget(self):
        review=self.app.review(dict(action='create',goal=self.goal()))
        self.assertFalse(self.app.store.path.exists())
        with self.assertRaisesRegex(ValueError,'explicit_confirmation'):self.app.commit(dict(review=review['review']))
        result=self.app.commit(dict(review=review['review'],confirmed=True))
        self.assertEqual(result['goal']['status'],'ACTIVE')
        state=self.app.state();self.assertEqual(state['daily']['initial']['available_month'],'6200.00')
    def test_stale_review_cannot_overwrite(self):
        a=self.app.review(dict(action='create',goal=self.goal()));b=self.app.review(dict(action='create',goal=self.goal()))
        self.app.commit(dict(review=a['review'],confirmed=True))
        with self.assertRaises(ValueError):self.app.commit(dict(review=b['review'],confirmed=True))
        self.assertEqual(len(self.app.store.read()['goals']),1)
    def test_purchase_estimate_no_goal_or_transaction_write(self):
        result=self.app.purchase(dict(name='Any product',price='4500',shipping='50'))
        self.assertEqual(result['total'],'4550');self.assertEqual(result['remaining'],'1950')
        self.assertEqual(result['price_type'],'USER_ESTIMATE');self.assertFalse(self.app.store.path.exists())
        with self.assertRaises(ValueError):self.app.purchase(dict(name='Any product',price='4500',shipping=None))
    def test_travel_endpoint_and_missing_provenance(self):
        trip=dict(departure='Start',destination='Destination',travel_date=target_day('สิ้นเดือน',today_bangkok()).isoformat(),days=2,nights=1,travelers=1,costs=[dict(name='Travel',amount='1000',unit='group_total',certainty='estimated',source='user')])
        with self.request('/api/travel',dict(trip=trip)) as r:report=json.load(r)
        self.assertEqual(report['initial']['total'],'1000');self.assertFalse(self.app.store.path.exists())
        trip['costs'][0].pop('source')
        with self.assertRaises(HTTPError) as e:self.request('/api/travel',dict(trip=trip))
        self.assertEqual(e.exception.code,400)
    def test_chat_endpoint_is_local_and_read_only(self):
        with self.request('/api/chat',dict(message='รองเท้า ราคา 2500 ส่งฟรี')) as r:reply=json.load(r)
        self.assertEqual(reply['kind'],'purchase');self.assertEqual(reply['data']['remaining'],'4000')
        self.assertEqual(reply['mode'],'LOCAL_RULES_DEMO');self.assertFalse(self.app.store.path.exists())
    def test_expense_summary_endpoint_uses_custom_input_only(self):
        payload=dict(item=dict(name='Custom category',amount='700',kind='expense',period='monthly'))
        with self.request('/api/expense-summary',payload) as r:report=json.load(r)
        self.assertEqual(report['analysis']['categories'][0]['name'],'Custom category')
        self.assertEqual(report['simulation']['states']['10']['monthly'],'70.00')
        self.assertFalse(self.app.store.path.exists())

if __name__=='__main__':unittest.main()
