import tempfile
import unittest
from pathlib import Path
from server import Dashboard
from chat import respond

class ChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Dashboard(Path(self.temp.name)/'local/test.sqlite3')
    def test_goal_request_creates_only_uncommitted_draft(self):
        from goal_engine import target_day,today_bangkok
        r=respond(self.app,dict(message='อยากได้รองเท้า ก่อนสิ้นเดือน กันงบให้หน่อย'))
        self.assertEqual(r['kind'],'goal_draft');self.assertEqual(r['data']['goal_name'],'รองเท้า')
        self.assertEqual(r['data']['target_date'],target_day('สิ้นเดือน',today_bangkok()).isoformat())
        self.assertNotIn('target_amount',r['data']);self.assertFalse(self.app.store.path.exists())
    def test_name_followup_price_shipping_same_context(self):
        first=respond(self.app,dict(message='อยากซื้อ Puma Cali Court Match'))
        self.assertEqual(first['context']['name'],'Puma Cali Court Match');self.assertEqual(first['kind'],'message')
        second=respond(self.app,dict(message='ราคา 4,500',context=first['context']))
        self.assertEqual(second['context']['price'],'4500');self.assertNotIn('shipping',second['context'])
        last=respond(self.app,dict(message='ส่งฟรี',context=second['context']))
        self.assertEqual(last['kind'],'purchase');self.assertEqual(last['data']['total'],'4500')
        self.assertEqual(last['data']['remaining'],'2000');self.assertFalse(self.app.store.path.exists())
    def test_single_message_price_not_confused_with_model_number(self):
        r=respond(self.app,dict(message='อยากซื้อ Redmi Buds 6 ราคา 500 ค่าส่ง 50'))
        self.assertEqual(r['data']['total'],'550');self.assertEqual(r['context']['name'],'Redmi Buds 6')
    def test_budget_is_not_product_price(self):
        r=respond(self.app,dict(message='อยากได้หูฟัง งบไม่เกิน 500'))
        self.assertNotIn('price',r['context']);self.assertEqual(r['kind'],'message')
    def test_new_product_drops_old_price(self):
        r=respond(self.app,dict(message='อยากได้กระเป๋า',context=dict(name='shoes',price='500',shipping='20')))
        self.assertEqual(r['context'],{'name':'กระเป๋า'})
    def test_daily_goals_leaks_travel_routes(self):
        for text,kind in [('เช็กงบวันนี้','daily'),('ดูเป้าหมายของฉัน','goals'),('ช่วยลดรายจ่าย','leaks'),('อยากไปเที่ยว','travel_setup')]:
            self.assertEqual(respond(self.app,dict(message=text))['kind'],kind)
        self.assertFalse(self.app.store.path.exists())
    def test_unknown_live_price_has_honest_limit(self):
        r=respond(self.app,dict(message='Puma ราคาเท่าไหร่'))
        self.assertEqual(r['kind'],'message');self.assertIn('ยังค้นหาราคาสด',r['reply']);self.assertIsNone(r['data'])
    def test_new_chat_clears_context_and_no_write_from_confirmation(self):
        r=respond(self.app,dict(message='เริ่มใหม่',context=dict(name='test',price='500')));self.assertEqual(r['context'],{})
        respond(self.app,dict(message='ยืนยันซื้อเลย'));self.assertFalse(self.app.store.path.exists())
    def test_invalid_and_overlong_input(self):
        for payload in (dict(message=''),dict(message='a'*2001),dict(message='test',context=['bad'])):
            with self.assertRaises(ValueError):respond(self.app,payload)
    def test_malformed_money_is_not_silently_reinterpreted(self):
        for message in ('รองเท้า ราคา 1,2 ส่งฟรี','รองเท้า ราคา 25.555 ส่งฟรี','รองเท้า ราคา 500 ค่าส่ง 1,2'):
            with self.assertRaises(ValueError):respond(self.app,dict(message=message))
    def test_budget_followup_does_not_change_existing_price(self):
        r=respond(self.app,dict(message='งบไม่เกิน 500',context=dict(name='Test',price='1000',shipping='0')))
        self.assertEqual(r['kind'],'message');self.assertEqual(r['context']['price'],'1000')

if __name__=='__main__':unittest.main()
