import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import financial_fit,evaluate
from shopping import render
from test_engine import profile, listing, TODAY

class CardTests(unittest.TestCase):
    def result(self, cost='10000', **changes):
        p=profile();p.update(changes)
        return financial_fit(p,cost,TODAY)

    def test_partial_progress_uses_plan_allocation(self):
        r=self.result(earmarked='5000')
        self.assertEqual(r['savings_progress']['percent'],'50.00')
        self.assertEqual(r['savings_progress']['filled_segments'],5)
        self.assertEqual(r['savings_progress']['remaining'],'5000')

    def test_zero_progress_is_known_zero(self):
        self.assertEqual(self.result(earmarked='0')['savings_progress']['percent'],'0.00')

    def test_complete_overfunded_and_free_item(self):
        for cost in ('500','1000','0'):
            p=self.result(cost)['savings_progress']
            self.assertEqual(p['percent'],'100' if cost=='0' else '100.00')
            self.assertEqual(p['filled_segments'],10)
            self.assertEqual(p['remaining'],'0')

    def test_progress_never_rounds_incomplete_to_full(self):
        p=self.result('10000',cash='30000',earmarked='9999.99')['savings_progress']
        self.assertEqual(p['percent'],'99.99')
        self.assertEqual(p['filled_segments'],9)

    def test_missing_profile_or_unverified_price_no_progress(self):
        for result in (financial_fit({},'500',TODAY),self.result(None)):
            self.assertEqual(result['status'],'INSUFFICIENT_DATA')
            self.assertNotIn('savings_progress',result)

    def test_card_structure_and_calculated_values(self):
        payload={'include_financial':True,'profile':profile(),'listings':[listing()]}
        text=render(payload,evaluate(payload,TODAY))
        for expected in ('## Financial Fit','### 950.00 บาท','AFFORDABLE','เงินพร้อมใช้','เหลือต่อเดือน',
                         'งบเหลือหลังซื้อ','ซื้อได้เมื่อไร','ความคืบหน้าแผนเก็บเงิน','คำแนะนำ','สมมติฐาน','ข้อจำกัด'):
            self.assertIn(expected,text)
        self.assertIn('██████████',text)
        self.assertNotIn('<div',text)

    def test_insufficient_card_no_fake_zero_or_bar(self):
        payload={'include_financial':True,'listings':[listing()]}
        text=render(payload,evaluate(payload,TODAY))
        self.assertIn('INSUFFICIENT_DATA',text)
        self.assertIn('ยังระบุเวลาไม่ได้',text)
        self.assertNotIn('0%',text)
        self.assertNotIn('░',text)

    def test_status_recommendations_and_no_invented_eta(self):
        for changes,status,phrase in [({},'SAVE_FIRST','เก็บเงินเพิ่ม'),({'income':'20000'},'NOT_AFFORDABLE','ชะลอซื้อ')]:
            p=profile();p.update(changes)
            item=listing();item.update(price='20000',discount='0',shipping='0')
            payload={'include_financial':True,'profile':p,'listings':[item]}
            text=render(payload,evaluate(payload,TODAY))
            self.assertIn(status,text);self.assertIn(phrase,text)
            if status=='NOT_AFFORDABLE': self.assertIn('ยังระบุเวลาไม่ได้',text)

    def test_price_only_keeps_product_table(self):
        payload={'listings':[listing()]}
        text=render(payload,evaluate(payload,TODAY))
        self.assertIn('| สินค้า/รุ่น |',text)
        self.assertNotIn('Financial Fit',text)
        self.assertNotIn('ความคืบหน้า',text)

if __name__=='__main__': unittest.main()
