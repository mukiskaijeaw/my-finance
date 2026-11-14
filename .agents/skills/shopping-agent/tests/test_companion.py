"""Synthetic-only acceptance tests for the final interactive MVP."""
import sys,tempfile,unittest,copy,json
from pathlib import Path
from datetime import date
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from companion import demo_input,run_companion,render_companion
from companion_engine import daily_spending,money_leaks,reduction_states,travel_report,potential_goal_draft
from shared_state import build_shared
from goal_storage import GoalStore,default_store
from goal_planner import run
from goal_engine import calendar_rows
from purchase_flow import price_states
DAY=date(2026,11,14)

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=GoalStore(Path(self.temp.name)/'local'/'goals.sqlite3');self.data=demo_input(DAY)
    def shared(self):return build_shared(self.data['profile'],self.data['budget'],self.store.read(),DAY)
    def call(self,action,**fields):return run_companion(dict(action=action,synthetic=True,**fields),self.store,DAY)
    def test_demo_reconciles_without_default_goal(self):
        rows=self.data['transactions'];spent=sum((D(r['amount_thb']) for r in rows if r['transaction_type']=='expense'),D(0))
        self.assertEqual(spent,D(13000));self.assertEqual(D(30000)-spent-D(5000),D(12000))
        p=self.shared()['portfolio'];self.assertEqual(D(p['remaining_spending_budget']),D(6500))
        self.assertEqual(self.store.read()['goals'],[]);self.assertFalse(self.store.path.exists())
    def test_daily_does_not_subtract_today_twice(self):
        r=self.call('daily')['report']['initial'];self.assertEqual(D(r['available_month']),D(6500))
        self.assertEqual(D(r['today_budget']),((D(6500)+D(r['today_recorded']))/17).quantize(D('.01'),rounding='ROUND_DOWN'))
    def test_balance_coverage_must_be_confirmed(self):
        r=daily_spending(self.shared(),self.data['transactions'],DAY)
        self.assertEqual(r['status'],'INSUFFICIENT_DATA')
    def test_month_last_day_has_no_tomorrow_division(self):
        end=date(2026,11,30)
        r=run_companion(dict(action='daily',synthetic=True),self.store,end)['report']['initial']
        self.assertIsNone(r['tomorrow_daily']);self.assertEqual(r['saving_days'],1)
    def test_daily_simulation_has_no_writes(self):
        report=self.call('daily')['report'];self.assertGreater(len(report['states']),1)
        self.assertLess(D(report['states'][-1]['available_month']),D(report['initial']['available_month']))
        self.assertFalse(self.store.path.exists())
    def test_leaks_observed_counts_and_reductions(self):
        report=self.call('leaks')['report'];cats={x['name']:x for x in report['analysis']['categories']}
        self.assertEqual(cats['Coffee']['count'],15);self.assertEqual(cats['Delivery Fees']['amount'],'550')
        states=report['simulation']['states'];self.assertEqual(D(states['5,3,1']['monthly']),D(959))
        self.assertEqual(D(states['5,3,1']['annual']),D(11508))
    def test_full_meal_not_inferred_as_shipping(self):
        rows=[dict(transaction_id='x',date=DAY.isoformat(),transaction_type='expense',amount_thb='240',description='food delivery',category='Food')]
        r=money_leaks(rows,DAY);self.assertEqual(r['categories'][0]['name'],'Food')
        self.assertFalse(any('fee' in x['name'].lower() for x in r['categories']))
    def test_subscription_unknown_cycle_is_not_monthly(self):
        r=money_leaks([],DAY,[dict(name='Spotify',amount='149')]);self.assertIsNone(r['subscriptions'][0]['monthly'])
        self.assertEqual(reduction_states(r)['controls'],[])
    def test_annual_subscription_preserves_annual_amount(self):
        r=money_leaks([],DAY,[dict(name='test',amount='100',period='annual')])
        self.assertEqual(reduction_states(r)['states']['1']['annual'],'100')
    def test_possible_duplicate_and_recurring_are_not_deletions(self):
        row=dict(transaction_id='a',date='2026-11-01',transaction_type='expense',amount_thb='100',description='fee',category='Fees')
        r=money_leaks([row,dict(row,transaction_id='b'),dict(row,transaction_id='c',date='2026-10-01')],DAY)
        self.assertEqual(len(r['duplicate_candidates']),1);self.assertEqual(r['recurring_candidates'],['fee'])
    def trip(self):return dict(destination='เมืองทดสอบ',departure='ต้นทางทดสอบ',travel_date='2026-11-28',days=3,nights=2,travelers=2,costs=[dict(name='ที่พัก',amount='500',unit='per_person_night',certainty='estimated',source='user estimate'),dict(name='เดินทาง',amount='1000',unit='per_person',certainty='estimated',source='user estimate')])
    def test_travel_uses_units_and_same_goal_engine(self):
        r=travel_report(self.shared(),self.trip(),DAY);self.assertEqual(r['total'],'4000')
        self.assertEqual(r['financial_fit'],'AFFORDABLE');self.assertEqual(r['goal_draft']['goal_category'],'travel')
        self.assertEqual(r['price_type'],'ESTIMATED')
    def test_travel_missing_source_rejected(self):
        trip=self.trip();trip['costs'][0].pop('source')
        with self.assertRaisesRegex(ValueError,'cost_provenance'):travel_report(self.shared(),trip,DAY)
    def test_travel_sliders_precomputed_no_images(self):
        r=self.call('travel',trip=self.trip());self.assertEqual(len(r['report']['states']),25)
        html=render_companion(r);self.assertNotIn('<img',html);self.assertNotIn('fetch(',html)
        self.assertEqual(r['report']['states']['0,0']['total'],'0.00')
    def test_goal_reduces_daily_budget_and_potential_is_not_cash(self):
        before=self.call('daily')['report']['initial'];g=dict(goal_name='เป้าหมายทดสอบ',goal_category='general',target_amount='1000',saved_amount='0',target_date='2026-11-28',funding_source='free_cash',activate_on_create=True)
        request=dict(action='create',goal=g,profile=self.data['profile'],budget=self.data['budget'],expected_revision=0,operation_id='test-create')
        with self.assertRaises(ValueError):run(request,self.store,DAY,consent=False)
        saved=run(request,self.store,DAY,consent=True)
        after=self.call('daily')['report']['initial'];self.assertEqual(D(before['available_month'])-D(after['available_month']),D(1000))
        snapshot=self.store.read();draft=potential_goal_draft(snapshot,saved['goal']['goal_id'],'959')
        self.assertEqual(draft['cash_change'],'0');self.assertEqual(self.store.read(),snapshot)
        trip=travel_report(self.shared(),self.trip(),DAY);self.assertEqual(trip['total'],'4000')
    def test_full_month_calendar_and_future_record_denied(self):
        g=dict(goal_id='x',goal_name='test',target_date='2026-11-28',activated_on='2026-11-14',status='ACTIVE')
        rows=calendar_rows(g,DAY);self.assertEqual(len(rows),30);self.assertEqual(rows[0]['weekday'],6);self.assertEqual(rows[0]['state'],'inactive');self.assertTrue(rows[27]['target'])
    def test_demo_store_separate(self):self.assertNotEqual(default_store(True),default_store(False))
    def test_price_simulation_does_not_replace_quote(self):
        report=dict(available_spending='6500',quote=dict(effective='3200'),decision=dict(recommendation='BUY_WITH_CAUTION'))
        original=copy.deepcopy(report);r=price_states(report,DAY)
        self.assertEqual(r['states'][r['initial']]['remaining'],'3300');self.assertEqual(report,original)
        self.assertEqual(r['states'][-1]['status'],'WAIT_AND_SAVE')
    def test_no_profile_or_zero_template_does_not_buy(self):
        r=run_companion(dict(action='daily',profile={},budget={}),self.store,DAY)['report']['initial']
        self.assertEqual(r['status'],'INSUFFICIENT_DATA');self.assertIsNone(r['today_remaining'])
    def test_end_to_end_shopping_leaks_goal_daily_and_travel(self):
        from welcome import CHOICES
        from purchase_flow import new_session,candidates,select,run_purchase
        self.assertEqual(len(CHOICES),5)
        original=self.call('daily')['report']['initial']
        listing=dict(name='สินค้าทดสอบ E2E',url='https://example.org/fixture',price='5000',shipping='0',discount='0',verified=True,shipping_verified=True,checked=DAY.isoformat(),stock='available',stock_verified=True,evidence={'model':{'value':'Test Model','source':'https://example.org/fixture'}})
        confirm=candidates(new_session(dict(product='สินค้าทดสอบ')),[listing],{'model':'Test Model'},DAY,exact=True)
        self.assertEqual(confirm['stage'],'CONFIRM');session=select(confirm,confirm['candidates'][0]['id'],True)
        context={k:dict(value=v,source='user-confirmed fixture') for k,v in dict(purpose='ใช้ส่วนตัว',necessity='wanted',value_suitable=True,offer_ready=True,planned=False).items()}
        request=dict(action='evaluate',session=session,profile=self.data['profile'],budget=self.data['budget'],context=context)
        decision=run_purchase(request,self.store,DAY)
        self.assertEqual(decision['report']['decision']['recommendation'],'BUY_WITH_CAUTION')
        self.assertEqual(decision['report']['remaining_after_purchase'],'1500')
        potential=self.call('leaks')['report']['simulation']['states']['5,3,1']
        self.assertEqual(D(potential['monthly']),D(959));self.assertFalse(self.store.path.exists())
        preview=run_purchase(dict(request,action='start_goal',purchase_saved_amount='0'),self.store,DAY)
        self.assertTrue(preview['report']['goal_confirmation_required'])
        confirm_request=dict(request,action='confirm_goal',purchase_saved_amount='0',funding_source_confirmed=True,expected_revision=0,operation_id='e2e-create',review_token=preview['report']['review_token'])
        created=run_purchase(confirm_request,self.store,DAY,True)
        self.assertEqual(created['stage'],'GOAL_ACTIVE')
        ident=created['goal_saved']['goal']['goal_id'];self.assertEqual(len(created['goal_view']['calendar'][ident]),30)
        self.assertEqual(potential_goal_draft(self.store.read(),ident,potential['monthly'])['saved_amount'],'0')
        after=self.call('daily')['report']['initial'];self.assertLess(D(after['available_month']),D(original['available_month']))
        trip=self.trip();trip['costs']=[dict(name='ทริปทดสอบ',amount='1000',unit='group_total',certainty='estimated',source='fixture')]
        draft=travel_report(self.shared(),trip,DAY)['goal_draft']
        view=run(dict(action='preview',goal=draft,profile=self.data['profile'],budget=self.data['budget']),self.store,DAY)
        self.assertEqual(view['status'],'FEASIBLE')
        saved=run(dict(action='create',goal=dict(draft,activate_on_create=True),profile=self.data['profile'],budget=self.data['budget'],expected_revision=1,operation_id='e2e-travel'),self.store,DAY,True)
        self.assertEqual(len(self.store.read()['goals']),2)
        self.assertEqual(saved['goal']['goal_category'],'travel')
    def test_future_savings_and_duplicate_day_rejected(self):
        g=dict(goal_name='Test',goal_category='general',target_amount='1000',saved_amount='0',target_date='2026-11-28',funding_source='free_cash',activate_on_create=True)
        saved=run(dict(action='create',goal=g,profile=self.data['profile'],budget=self.data['budget'],expected_revision=0,operation_id='create'),self.store,DAY,True)
        ident=saved['goal']['goal_id']
        request=dict(action='record_savings',goal=dict(goal_id=ident,date='2026-11-15',amount='10'),profile=self.data['profile'],budget=self.data['budget'],expected_revision=1,operation_id='future')
        with self.assertRaises(ValueError):run(request,self.store,DAY,True)
        request['goal']['date']=DAY.isoformat();run(dict(request,operation_id='today'),self.store,DAY,True)
        with self.assertRaisesRegex(ValueError,'duplicate_savings_day'):run(dict(request,operation_id='again',expected_revision=2),self.store,DAY,True)
    def test_personality_static_templates_use_male_particles(self):
        from goal_renderer import personality
        self.assertIn('ครับ',personality(dict(status='FUNDED'),'FEASIBLE'))
        for filename in ('purchase-flow-inline.html','companion-inline.html','welcome-inline.html'):
            raw=(Path(__file__).resolve().parents[1]/'assets'/filename).read_text(encoding='utf-8')
            self.assertNotIn('ค่ะ',raw);self.assertNotIn('นะคะ',raw)
    def test_outlier_is_evidence_based_candidate(self):
        rows=[dict(transaction_id=str(i),date=f'2026-11-{i+1:02d}',transaction_type='expense',amount_thb=str(value),category='Fees',description='test') for i,value in enumerate([10,10,10,30])]
        result=money_leaks(rows,DAY);self.assertEqual(len(result['unusual_candidates']),1)
        self.assertEqual(result['unusual_candidates'][0]['baseline_average'],'10.00')
    def test_invalid_transactions_disable_reduction_suggestion(self):
        result=money_leaks([dict(date='bad')],DAY)
        self.assertEqual(reduction_states(result)['controls'],[])
    def test_five_travel_categories_fit_inline_limit(self):
        trip=self.trip();trip['costs']=[dict(name='หมวด '+str(i),amount=str(100*(i+1)),unit='group_total',certainty='estimated',source='fixture') for i in range(5)]
        result=self.call('travel',trip=trip)
        self.assertEqual(len(result['report']['states']),3125)
        self.assertLess(len(render_companion(result).encode('utf-8')),1000000)
    def test_demo_future_progress_is_calculated_not_persisted(self):
        from goal_engine import goal_metrics,demo_progress_states
        raw=dict(goal_id='x',goal_name='test',goal_category='general',target_amount='300',saved_amount='0',target_date='2026-11-16',funding_source='free_cash',status='ACTIVE',activated_on=DAY.isoformat())
        result=demo_progress_states(goal_metrics(raw,DAY),DAY)
        self.assertEqual(result[-1]['saved_amount'],'200.00');self.assertEqual(raw['saved_amount'],'0');self.assertFalse(self.store.path.exists())
    def test_cli_demo_profile_is_shared_with_goals(self):
        import subprocess
        script=Path(__file__).resolve().parents[1]/'scripts/shopping.py'
        result=subprocess.run([sys.executable,str(script),'goals','--store',str(self.store.path)],input=json.dumps(dict(action='view',synthetic=True)),capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr);report=json.loads(result.stdout)
        self.assertEqual(report['status'],'FEASIBLE');self.assertEqual(report['remaining_spending_budget'],'6500')
        self.assertEqual(report['goals'],[]);self.assertFalse(self.store.path.exists())
    def test_cli_demo_daily_ignores_real_provider(self):
        import subprocess
        script=Path(__file__).resolve().parents[1]/'scripts/shopping.py'
        result=subprocess.run([sys.executable,str(script),'companion','--finance-dir','does-not-exist','--store',str(self.store.path)],input=json.dumps(dict(action='daily',synthetic=True)),capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr);report=json.loads(result.stdout)
        self.assertEqual(report['report']['initial']['available_month'],'6500');self.assertTrue(report['synthetic'])

if __name__=='__main__':unittest.main()
