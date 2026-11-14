import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from simulator import demo_profile,compute_state,build_payload,write_preview
from welcome import native_question,route_answer,is_trigger,CHOICES

DAY=date(2026,11,12)


class SimulatorTests(unittest.TestCase):
    def test_acceptance_a_to_e(self):
        expected=[('3200','3300','49.2','AFFORDABLE'),('5500','1000','84.6','BUY_WITH_CAUTION'),
                  ('8000','-1500','123.1','WAIT_AND_SAVE'),('5000','1500','76.9','AFFORDABLE'),
                  ('6500','0','100.0','BUY_WITH_CAUTION')]
        for price,remaining,percent,status in expected:
            with self.subTest(price=price):
                r=compute_state(demo_profile(DAY),price,'1500',DAY)
                self.assertEqual((r['remainingMoney'],r['spendingPercentage'],r['demoFinancialStatus']),(remaining,percent,status))

    def test_separate_accounts_and_no_double_deduction(self):
        p=demo_profile(DAY)
        self.assertEqual((p['cash'],p['emergency'],p['reserved']),('77000','60000','10500'))
        r=compute_state(p,'3200','1500',DAY)
        self.assertEqual((r['availableMoney'],r['remainingMoney']),('6500','3300'))

    def test_clamp_over_100_and_exact_shortfall(self):
        r=compute_state(demo_profile(DAY),'8000','1500',DAY)
        self.assertEqual((r['progressBarWidth'],r['shortfall']),('100','1500'))

    def test_earmarked_zero_does_not_replace_cash_shortfall(self):
        p=demo_profile(DAY);p['earmarked']='0'
        self.assertEqual(compute_state(p,'8000','1500',DAY)['shortfall'],'1500')

    def test_safety_demo_policy_does_not_change_core_fit(self):
        r=compute_state(demo_profile(DAY),'5500','1500',DAY)
        self.assertEqual((r['engineFinancialFit'],r['demoFinancialStatus']),('AFFORDABLE','BUY_WITH_CAUTION'))

    def test_every_slider_step_precomputed(self):
        p=build_payload(demo_profile(DAY),dict(productName='Synthetic headphones',productPrice='3200'),DAY,minimum=1000,maximum=12000,step=100)
        self.assertEqual(len(p['states']),111)
        self.assertIn('1000',p['states']);self.assertIn('12000',p['states'])

    def test_other_product_and_safe_markup(self):
        product=dict(productName='Other product </script><script>BAD()</script>',productPrice='5500')
        p=build_payload(demo_profile(DAY),product,DAY)
        with tempfile.TemporaryDirectory() as d:
            path=write_preview(p,Path(d)/'preview.html')
            raw=path.read_text(encoding='utf-8')
            self.assertNotIn('</script><script>BAD()',raw)
            self.assertNotIn('__SIMULATOR_PAYLOAD__',raw)
        self.assertIsNone(p['productImageUrl'])

    def test_no_network_no_mutation(self):
        p=demo_profile(DAY);before=copy.deepcopy(p)
        with patch('socket.socket',side_effect=AssertionError('network')):
            build_payload(p,dict(productName='Synthetic',productPrice='3200'),DAY)
        self.assertEqual(p,before)

    def test_missing_financial_values_not_zero(self):
        p=demo_profile(DAY);p.pop('cash')
        self.assertEqual(compute_state(p,'3200','1500',DAY)['demoFinancialStatus'],'INSUFFICIENT_DATA')

    def test_zero_cash_denominator_not_fake_percentage(self):
        p=demo_profile(DAY);p['cash']='70500'
        self.assertIsNone(compute_state(p,'3200','1500',DAY)['spendingPercentage'])

    def test_grid_image_and_real_mode_validation(self):
        for kw in (dict(step=0),dict(step=300),dict(demo_mode=False)):
            with self.assertRaises(ValueError):build_payload(demo_profile(DAY),dict(productName='Demo',productPrice='3200'),DAY,**kw)
        with self.assertRaises(ValueError):
            build_payload(demo_profile(DAY),dict(productName='Demo',productPrice='3200',productImageUrl='https://example.org/img'),DAY)


class WelcomeTests(unittest.TestCase):
    def test_welcome_cli_never_reads_financial_provider(self):
        import subprocess,json
        script=Path(__file__).resolve().parents[1]/'scripts/shopping.py'
        r=subprocess.run([sys.executable,'-B',str(script),'welcome','--finance-dir','nonexistent-finance-provider'],
                         text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(len(json.loads(r.stdout)['questions'][0]['options']),5)
    def test_eight_native_options(self):
        q=native_question()['questions'][0]
        self.assertEqual(len(q['options']),5)
        self.assertIn('วันนี้อยากปรึกษาเรื่องเงินอะไร?',q['title'])

    def test_supported_text_triggers(self):
        for t in ('/shopping-agent','/shopping','shopping agent','เริ่ม shopping agent'):
            self.assertTrue(is_trigger(t))
        self.assertFalse(is_trigger('อยากซื้อของ'))

    def test_all_eight_routes_and_real_observed_reply(self):
        for icon,description,intent,_ in CHOICES:
            r=route_answer(icon+' '+description)
            self.assertEqual(r['intent'],intent)
            self.assertFalse(r['record_transaction'])
        self.assertEqual(route_answer('💰 เดือนนี้เหลือเงินใช้ได้อีกเท่าไหร่')['intent'],'monthly_overview')

    def test_limited_options_fallback_groups(self):
        self.assertEqual(len(native_question(2)['questions'][0]['options']),2)
        self.assertEqual(len(native_question(3)['questions'][0]['options']),3)


if __name__=='__main__':unittest.main()
