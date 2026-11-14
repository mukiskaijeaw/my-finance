import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from purchase_flow import new_session,candidates,select,reject,run_purchase
from purchase_renderer import render_purchase
from goal_storage import GoalStore
from test_goal_planner import inputs,goal,DAY


def listing(model='Model A',price='300'):
    source='https://example.org/'+model.replace(' ','-')
    return dict(name=model,url=source,price=price,shipping='20',discount='0',
                verified=True,shipping_verified=True,checked=DAY.isoformat(),
                stock='available',stock_verified=True,evidence={'model':{'value':model,'source':source}})


def selected():
    state=candidates(new_session(),[listing()],{'model':'Model A'},DAY,exact=True)
    return select(state,state['candidates'][0]['id'],True)


def context():
    return {k:dict(value=v,source='user-confirmed test fixture') for k,v in
            dict(purpose='ใช้เรียน',necessity='required',value_suitable=True,offer_ready=True,planned=True).items()}


class PurchaseFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=GoalStore(Path(self.tmp.name)/'local/goals.sqlite3')
        self.p,self.b=inputs()

    def tearDown(self):self.tmp.cleanup()

    def request(self,action='evaluate',**extra):
        return dict(action=action,session=selected(),profile=self.p,budget=self.b,context=context(),precompute_dates=False,**extra)

    def test_empty_entry_and_supplied_input_skip_form(self):
        self.assertEqual(new_session()['stage'],'INTENT')
        self.assertIsNone(new_session()['selected_product'])
        self.assertEqual(new_session({'product':'ชื่อที่ผู้ใช้ระบุ'})['stage'],'SEARCH_REQUIRED')
        self.assertEqual(new_session({'image_attached':True})['stage'],'SEARCH_REQUIRED')

    def test_broad_input_limited_to_four_exact_only_one(self):
        offers=[listing('Model '+str(i)) for i in range(8)]
        self.assertEqual(len(candidates(new_session(),offers,{},DAY)['candidates']),4)
        self.assertEqual(len(candidates(new_session(),offers,{'model':'Model 3'},DAY,exact=True)['candidates']),1)

    def test_confirmation_required_and_rejection_clears_state(self):
        state=candidates(new_session(),[listing()],{},DAY)
        with self.assertRaises(ValueError):run_purchase(dict(action='evaluate',session=state),self.store,DAY)
        chosen=select(state,state['candidates'][0]['id'],True)
        self.assertIsNone(reject(chosen)['selected_product'])
        self.assertEqual(reject(chosen,True)['stage'],'SEARCH_REQUIRED')

    def test_default_month_end_affordable_no_goal_created(self):
        r=run_purchase(self.request(),self.store,DAY)['report']
        self.assertEqual(r['target_date'],'2028-02-29')
        self.assertEqual(r['financial']['status'],'AFFORDABLE')
        self.assertEqual(r['remaining_after_purchase'],'2680')
        self.assertEqual(r['decision']['recommendation'],'BUY_NOW')
        self.assertFalse(self.store.path.exists())

    def test_existing_goals_protected_once(self):
        from goal_planner import run
        run(dict(action='create',goal=goal(target_amount='600',saved_amount='100'),profile=self.p,budget=self.b,
                 operation_id='existing',expected_revision=0),self.store,DAY,True)
        r=run_purchase(self.request(),self.store,DAY)['report']
        self.assertEqual(r['available_spending'],'2400.00')
        self.assertEqual(r['remaining_after_purchase'],'2080.00')

    def test_missing_shipping_not_affordable_and_price_refresh(self):
        request=self.request();request['session']['selected_product']['listing']['shipping']=None
        r=run_purchase(request,self.store,DAY)['report']
        self.assertEqual(r['decision']['recommendation'],'NEED_MORE_INFO')
        request=self.request();request['session']['selected_product']['listing']['checked']='2020-01-01'
        self.assertIsNone(run_purchase(request,self.store,DAY)['report']['quote']['effective'])

    def test_user_budget_is_respected(self):
        request=self.request();request['session']['intent']['budget']='100'
        r=run_purchase(request,self.store,DAY)['report']
        self.assertEqual(r['financial']['status'],'SAVE_FIRST')
        self.assertEqual(r['available_spending'],'100')

    def test_local_date_precomputation_and_cross_month_forecast(self):
        request=self.request();request['precompute_dates']=True
        r=run_purchase(request,self.store,DAY)
        self.assertEqual(len(r['date_reports']),3)
        self.assertEqual(r['date_reports'][DAY.isoformat()]['daily_saving'],'320.00')
        request=self.request('change_date',target_date='2028-03-02')
        self.assertEqual(run_purchase(request,self.store,DAY)['report']['goal_plan']['status'],'INSUFFICIENT_DATA')
        request['forecast']=dict(complete=True,through='2028-03-02',events=[dict(date='2028-03-01',income='1000',outflow='100',confirmed=True)])
        self.assertEqual(run_purchase(request,self.store,DAY)['report']['goal_plan']['status'],'FEASIBLE')

    def test_start_preview_then_review_consent_and_calendar(self):
        request=self.request('start_goal',purchase_saved_amount='0')
        preview=run_purchase(request,self.store,DAY)
        self.assertFalse(self.store.path.exists())
        confirm=dict(request,action='confirm_goal',review_token=preview['report']['review_token'],
                     funding_source_confirmed=True,expected_revision=0,operation_id='start')
        with self.assertRaises(ValueError):run_purchase(confirm,self.store,DAY)
        saved=run_purchase(confirm,self.store,DAY,True)
        self.assertEqual(saved['stage'],'GOAL_ACTIVE')
        self.assertEqual(len(saved['goal_view']['calendar'][saved['goal_saved']['goal']['goal_id']]),29)
        self.assertEqual(len(self.store.read()['goals']),1)

    def test_revised_budget_invalidates_confirmation(self):
        request=self.request('start_goal',purchase_saved_amount='0')
        preview=run_purchase(request,self.store,DAY)
        request.update(action='confirm_goal',review_token=preview['report']['review_token'],funding_source_confirmed=True,expected_revision=0,operation_id='start')
        request['profile']=dict(self.p,cash='6000')
        with self.assertRaisesRegex(ValueError,'review_updated'):run_purchase(request,self.store,DAY,True)

    def test_skip_does_not_write_and_ui_source_is_reused(self):
        r=run_purchase(dict(action='skip',session=selected()),self.store,DAY)
        self.assertEqual(r['recommendation'],'SKIP_PURCHASE')
        self.assertFalse(self.store.path.exists())
        raw=render_purchase(new_session())
        self.assertNotIn('Model A',raw)
        self.assertNotIn('__PURCHASE_PAYLOAD__',raw)
        self.assertIn('ช่วยดูให้หน่อยว่าควรซื้อไหม',raw)

    def test_zero_total_does_not_force_a_savings_goal(self):
        request=self.request()
        request['session']['selected_product']['listing'].update(price='0',shipping='0')
        r=run_purchase(request,self.store,DAY)['report']
        self.assertEqual(r['financial']['status'],'AFFORDABLE')
        self.assertEqual(r['goal_status'],'NOT_REQUIRED')
        self.assertFalse(self.store.path.exists())


if __name__=='__main__':unittest.main()
