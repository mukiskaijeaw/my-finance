import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import evaluate
from shopping import listing_details,render
from test_engine import listing,profile,TODAY

class ProductDetailsTests(unittest.TestCase):
    def test_unknown_fields_remain_visible(self):
        text=listing_details({})
        for label in ('ตัวเลือกสินค้า','ส่วนลดเพิ่มเติม','ค่าจัดส่ง','ยังไม่ยืนยัน'):
            self.assertIn(label,text)
        self.assertNotIn('ส่งฟรี',text)

    def test_verified_values(self):
        item=listing();item.update(variants=['สีขาว','สีดำ'],variants_verified=True)
        text=listing_details(item)
        self.assertIn('สีขาว, สีดำ',text)
        self.assertIn('ลด 100.00 บาท',text)
        self.assertIn('50.00 บาท',text)

    def test_ineligible_discount_not_presented_as_usable(self):
        item=listing();item['eligible']=False
        self.assertNotIn('ลด 100',listing_details(item))

    def test_unverified_variant_and_shipping_not_claimed(self):
        item=listing();item.update(variants=['สีที่ยังไม่ยืนยัน'],variants_verified=False,shipping='0',shipping_verified=False)
        text=listing_details(item)
        self.assertNotIn('สีที่ยังไม่ยืนยัน',text)
        self.assertNotIn('ส่งฟรี',text)

    def test_verified_free_shipping(self):
        item=listing();item.update(shipping='0',shipping_verified=True)
        self.assertIn('ส่งฟรี (ยืนยันแล้ว)',listing_details(item))

    def test_each_search_or_financial_card_has_identical_fields(self):
        for financial in (False,True):
            payload={'include_financial':financial,'profile':profile(),'listings':[listing(),listing()]}
            output=render(payload,evaluate(payload,TODAY))
            self.assertEqual(output.count('| ตัวเลือกสินค้า | ส่วนลดเพิ่มเติม | ค่าจัดส่ง |'),2)

if __name__=='__main__':unittest.main()
