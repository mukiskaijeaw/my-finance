import copy
import json
import subprocess
import sys
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from decision_policy import recommend,evaluate_decision
from shopping import run_request,render,today


def evidence(value):
    return dict(value=value,source='explicit synthetic user statement')


def context(**kw):
    c=dict(purpose='ใช้ประชุมทำงาน',necessity='required',timing='flexible',value_suitable=True,
           planned=True,promotion=False,current_usable=False,offer_ready=True)
    c.update(kw)
    return {k:evidence(v) for k,v in c.items()}


def fixture():
    day=today()
    profile=dict(income='30000',essential='20000',debt='2000',saving='6500',cash='13000',
                 emergency='10000',reserved='0',as_of=day.isoformat(),complete=True,future_complete=True,
                 future_extra=[],income_kind='stable')
    decision=dict(price='4500',price_confirmed=True,price_source='explicit synthetic checkout',
                  budget=dict(cycle_complete=True,next_income_date=(day+timedelta(days=20)).isoformat(),
                              minimum_remaining='0',obligations=[]),context=context(current_usable=True))
    return profile,decision


class ConversationTests(unittest.TestCase):
    def test_expected_headphone_conversation(self):
        p,d=fixture(); r=evaluate_decision(p,d,today())
        self.assertEqual((r['financial']['available'],r['financial']['monthly_surplus'],r['financial']['months']),('3000','1500',1))
        self.assertEqual(r['financial']['savings_progress']['remaining'],'1500')
        self.assertEqual(r['decision']['recommendation'],'WAIT_AND_SAVE')
        self.assertIn('ใช้ของเดิมต่อ',r['decision']['alternative_actions'][1])

    def test_affordable_not_automatic_buy(self):
        r=recommend(dict(status='AFFORDABLE'),{})
        self.assertEqual(r['recommendation'],'NEED_MORE_INFO')

    def test_planned_necessary_suitable_buy_now(self):
        self.assertEqual(recommend(dict(status='AFFORDABLE'),context())['recommendation'],'BUY_NOW')

    def test_flash_sale_with_enough_money_caution(self):
        r=recommend(dict(status='AFFORDABLE'),context(promotion=True,planned=False,necessity='wanted'))
        self.assertEqual(r['recommendation'],'BUY_WITH_CAUTION')
        self.assertTrue(any('โปรโมชัน' in x for x in r['reasons']))

    def test_user_priority_keep_money_skip(self):
        self.assertEqual(recommend(dict(status='AFFORDABLE'),context(prefer_skip=True))['recommendation'],'SKIP_PURCHASE')

    def test_urgent_broken_phone_affordable_alternative(self):
        p,d=fixture();d['context']=context(timing='urgent',repair_possible=True)
        d['alternatives']=[dict(id='replacement',action='cheaper',price='2500',price_confirmed=True,
                                price_source='synthetic checkout',suitable=evidence(True))]
        r=evaluate_decision(p,d,today())
        self.assertEqual(r['decision']['recommendation'],'CHOOSE_ALTERNATIVE')
        self.assertEqual(r['decision']['verified_alternatives'][0]['id'],'replacement')

    def test_unverified_cheaper_not_viable(self):
        p,d=fixture();d['context']=context(timing='urgent')
        d['alternatives']=[dict(id='cheap',action='cheaper',price='200',price_confirmed=False,
                                price_source='snippet',suitable=evidence(True))]
        self.assertEqual(evaluate_decision(p,d,today())['decision']['recommendation'],'WAIT_AND_SAVE')

    def test_missing_finances_not_affordable(self):
        _,d=fixture()
        self.assertEqual(evaluate_decision({},d,today())['decision']['recommendation'],'NEED_MORE_INFO')

    def test_unverified_price_not_buy(self):
        p,d=fixture();d['price_confirmed']=False
        self.assertEqual(evaluate_decision(p,d,today())['decision']['financial_fit'],'INSUFFICIENT_DATA')

    def test_no_source_no_necessity_inference(self):
        c=context();c['necessity']={'value':'required'}
        self.assertEqual(recommend(dict(status='AFFORDABLE'),c)['recommendation'],'NEED_MORE_INFO')

    def test_not_needed_does_not_mean_moral_skip(self):
        self.assertEqual(recommend(dict(status='AFFORDABLE'),context(necessity='not_needed'))['recommendation'],'BUY_WITH_CAUTION')

    def test_unsuitable_does_not_buy_despite_cash(self):
        self.assertEqual(recommend(dict(status='AFFORDABLE'),context(value_suitable=False))['recommendation'],'NEED_MORE_INFO')

    def test_new_information_changes_recommendation(self):
        p,d=fixture()
        before=evaluate_decision(p,d,today())
        more=copy.deepcopy(p);more['cash']='15000'
        after=evaluate_decision(more,d,today())
        self.assertEqual((before['decision']['recommendation'],after['decision']['recommendation']),('WAIT_AND_SAVE','BUY_NOW'))
        self.assertEqual(p['cash'],'13000')

    def test_necessary_questions_only(self):
        self.assertEqual(recommend(dict(status='AFFORDABLE'),context())['follow_up_questions'],[])

    def test_sourced_alternative_actions_only(self):
        r=recommend(dict(status='SAVE_FIRST',months=1),context())
        self.assertFalse(any('ยืม' in x or 'มือสอง' in x or 'ซ่อม' in x for x in r['alternative_actions']))

    def test_price_only_reads_no_finances(self):
        p,d=fixture()
        with patch('shopping.load_finance',side_effect=AssertionError('private read')):
            _,r=run_request(dict(include_financial=False,profile=p,decision=d),today())
        self.assertNotIn('decision_report',r)

    def test_no_network_and_no_input_mutation(self):
        p,d=fixture();before=copy.deepcopy((p,d))
        with patch('socket.socket',side_effect=AssertionError('network')):
            evaluate_decision(p,d,today())
        self.assertEqual((p,d),before)

    def test_stdin_cli_to_policy_to_response(self):
        p,d=fixture()
        script=Path(__file__).resolve().parents[1]/'scripts/shopping.py'
        r=subprocess.run([sys.executable,str(script),'decision','--format','markdown'],input=json.dumps(dict(profile=p,decision=d)),
                         text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('WAIT_AND_SAVE',r.stdout)
        self.assertIn('1,500.00',r.stdout)

    def test_not_affordable_no_fake_timeline(self):
        r=recommend(dict(status='NOT_AFFORDABLE',months=None),context())
        self.assertEqual(r['recommendation'],'WAIT_AND_SAVE')
        self.assertTrue(any('ยังระบุวัน' in x for x in r['alternative_actions']))


if __name__=='__main__': unittest.main()
