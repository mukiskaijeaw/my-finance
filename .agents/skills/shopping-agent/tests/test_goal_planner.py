import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from goal_engine import target_day,goal_metrics,plan_goals,calendar_rows,today_bangkok
from goal_storage import GoalStore
from goal_planner import run
from goal_renderer import render_inline,render_markdown

DAY=date(2028,2,27)


def goal(**updates):
    g=dict(goal_id='a',goal_name='ค่าเรียน',goal_category='education',target_amount='300',
           saved_amount='0',target_date='2028-02-29',funding_source='free_cash',status='ACTIVE')
    return dict(g,**updates)


def inputs():
    p=dict(income='10000',essential='1000',debt='0',saving='1000',cash='5000',
           emergency='1000',reserved='500',future_extra=[],income_kind='stable',
           as_of=DAY.isoformat(),complete=True,future_complete=True)
    b=dict(cycle_complete=True,next_income_date='2028-02-29',minimum_remaining='500',obligations=[])
    return p,b


class GoalEngineTests(unittest.TestCase):
    def test_month_end_leap_year_and_year_end(self):
        self.assertEqual(target_day('สิ้นเดือน',DAY),date(2028,2,29))
        self.assertEqual(target_day('สิ้นเดือน',date(2027,2,1)),date(2027,2,28))
        self.assertEqual(target_day('สิ้นปี',DAY),date(2028,12,31))

    def test_all_categories_and_dynamic_prices_names_dates(self):
        for category in ('purchase','travel','general','education','future_expense'):
            g=goal(goal_name=category,goal_category=category,target_amount='100.01')
            r=goal_metrics(g,DAY)
            self.assertEqual(r['goal_name'],category)
            self.assertEqual(r['saving_days_including_today'],3)
            self.assertEqual(r['days_remaining'],2)
            self.assertEqual(r['daily_saving'],'33.34')

    def test_today_and_overdue_and_funded(self):
        self.assertEqual(goal_metrics(goal(target_date=DAY.isoformat()),DAY)['daily_saving'],'300.00')
        self.assertIsNone(goal_metrics(goal(target_date='2028-02-26'),DAY)['daily_saving'])
        r=goal_metrics(goal(saved_amount='400'),DAY)
        self.assertEqual((r['status'],r['progress'],r['remaining_target_amount']),('FUNDED','100.00','0'))

    def test_missing_savings_and_protected_source_rejected(self):
        for changes in ({'saved_amount':None},{'funding_source':'emergency'}, {'target_amount':'NaN'}, {'target_amount':'-1'}):
            with self.assertRaises(ValueError):goal_metrics(goal(**changes),DAY)

    def test_multiple_goals_joint_budget_and_no_mutation(self):
        p,b=inputs();before=copy.deepcopy(p)
        r=plan_goals([goal(),goal(goal_id='b',target_amount='600')],p,b,DAY)
        self.assertEqual(r['status'],'FEASIBLE')
        self.assertEqual(r['remaining_spending_budget'],'2100.00')
        self.assertEqual(r['daily_spending'],'700.00')
        self.assertEqual(p,before)

    def test_double_reservation_coverage(self):
        p,b=inputs();g=goal(saved_amount='100')
        a=plan_goals([g],p,b,DAY,coverage={'a':'100'})
        c=plan_goals([g],p,b,DAY)
        self.assertEqual(float(a['remaining_spending_budget'])-float(c['remaining_spending_budget']),100)
        with self.assertRaises(ValueError):plan_goals([g],p,b,DAY,coverage={'a':'501'})

    def test_cross_month_requires_complete_forecast(self):
        p,b=inputs();g=goal(target_date='2028-03-02')
        self.assertEqual(plan_goals([g],p,b,DAY)['status'],'INSUFFICIENT_DATA')
        f=dict(complete=True,through='2028-03-02',events=[dict(date='2028-03-01',income='1000',outflow='500',confirmed=True)])
        r=plan_goals([g],p,b,DAY,forecast=f)
        self.assertEqual(r['status'],'FEASIBLE')
        self.assertEqual(len(r['forecast']),5)

    def test_later_income_does_not_cover_early_shortfall(self):
        p,b=inputs();g=goal(target_amount='10000',target_date='2028-03-02')
        f=dict(complete=True,through='2028-03-02',events=[dict(date='2028-03-01',income='10000',outflow='0',confirmed=True)])
        r=plan_goals([g],p,b,DAY,forecast=f)
        self.assertEqual(r['status'],'NOT_FEASIBLE')
        self.assertEqual(r['first_shortfall'],'2028-02-28')

    def test_rounding_caps_last_day_not_overfunded(self):
        p,b=inputs();r=plan_goals([goal(target_amount='100.01')],p,b,DAY)
        self.assertEqual(r['total_goal_allocation'],'100.01')

    def test_calendar_only_after_activation(self):
        g=goal();self.assertEqual(calendar_rows(g,DAY),[])
        g['activated_on']=DAY.isoformat()
        rows=calendar_rows(g,DAY,[dict(date=DAY.isoformat(),amount='50')])
        self.assertEqual(len(rows),29);self.assertEqual(rows[26]['state'],'recorded');self.assertEqual(rows[0]['state'],'inactive');self.assertTrue(rows[-1]['target'])

    def test_paused_and_deleted_saved_money_stays_protected(self):
        p,b=inputs()
        r=plan_goals([goal(status='PAUSED',saved_amount='200')],p,b,DAY)
        self.assertEqual(r['remaining_spending_budget'],'2800')
        r=plan_goals([goal(status='DELETED',saved_amount='200')],p,b,DAY)
        self.assertEqual(r['remaining_spending_budget'],'2800')

    def test_insufficient_financial_data_not_affordable(self):
        p,b=inputs();p.pop('cash')
        self.assertEqual(plan_goals([goal()],p,b,DAY)['status'],'INSUFFICIENT_DATA')


class GoalStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=GoalStore(Path(self.temp.name)/'local/goals.sqlite3')
        self.p,self.b=inputs()

    def tearDown(self):self.temp.cleanup()

    def mutate(self,action,g,revision,operation,consent=True):
        return run(dict(action=action,goal=g,expected_revision=revision,operation_id=operation,
                        profile=self.p,budget=self.b),self.store,DAY,consent)

    def test_create_activate_record_duplicate_and_idempotency(self):
        with self.assertRaises(ValueError):self.mutate('create',goal(),0,'a',False)
        self.assertFalse(self.store.path.exists())
        r=self.mutate('create',goal(),0,'a');ident=r['goal']['goal_id']
        self.assertEqual(self.mutate('create',goal(),0,'a'),r)
        self.mutate('activate',{'goal_id':ident},1,'b')
        r=self.mutate('record_savings',dict(goal_id=ident,amount='50'),2,'c')
        self.assertEqual(r['goal']['saved_amount'],'50')
        view=run(dict(action='view',profile=self.p,budget=self.b),self.store,DAY)
        self.assertEqual(view['goals'][0]['progress'],'16.67')
        self.assertEqual(view['goals'][0]['daily_saving'],'125.00')
        self.assertEqual(view['calendar'][ident][26]['state'],'recorded')
        with self.assertRaisesRegex(ValueError,'duplicate_savings_day'):
            self.mutate('record_savings',dict(goal_id=ident,amount='20'),3,'d')
        self.assertEqual(len(self.store.read()['entries']),1)

    def test_edit_pause_resume_delete_and_revision(self):
        r=self.mutate('create',goal(),0,'a');ident=r['goal']['goal_id']
        with self.assertRaisesRegex(ValueError,'stale_revision'):
            self.mutate('pause',{'goal_id':ident},0,'stale')
        self.mutate('edit',dict(goal_id=ident,goal_name='ทริปใหม่',target_amount='500'),1,'b')
        self.mutate('pause',dict(goal_id=ident),2,'c')
        self.mutate('activate',dict(goal_id=ident),3,'d')
        self.mutate('delete',dict(goal_id=ident),4,'e')
        self.assertEqual(self.store.read()['goals'][0]['status'],'DELETED')

    def test_infeasible_edit_rolls_back(self):
        r=self.mutate('create',goal(),0,'a');ident=r['goal']['goal_id']
        with self.assertRaises(ValueError):self.mutate('edit',dict(goal_id=ident,target_amount='999999'),1,'b')
        self.assertEqual(self.store.read()['revision'],1)

    def test_preview_does_not_create_store(self):
        r=run(dict(action='preview',goal=goal(),profile=self.p,budget=self.b),self.store,DAY)
        self.assertEqual(r['status'],'FEASIBLE');self.assertFalse(self.store.path.exists())

    def test_changed_operation_id_payload_is_rejected(self):
        self.mutate('create',goal(),0,'same')
        with self.assertRaisesRegex(ValueError,'different_request'):
            self.mutate('create',goal(goal_name='ชื่อใหม่'),0,'same')

    def test_edit_target_date_recomputes_daily_saving(self):
        r=self.mutate('create',goal(),0,'a');ident=r['goal']['goal_id']
        self.mutate('edit',dict(goal_id=ident,target_date=DAY.isoformat()),1,'b')
        view=run(dict(action='view',profile=self.p,budget=self.b),self.store,DAY)
        self.assertEqual(view['goals'][0]['daily_saving'],'300.00')


class GoalRenderTests(unittest.TestCase):
    def test_dynamic_safe_inline_no_network_or_finance_math(self):
        p,b=inputs();r=plan_goals([goal(goal_name='เป้าหมาย </script>')],p,b,DAY)
        raw=render_inline(r)
        self.assertIn('\\u003c/script\\u003e',raw)
        self.assertNotIn('__GOAL_PAYLOAD__',raw)
        self.assertNotIn('fetch(',raw)
        self.assertNotIn('Nike',raw)
        self.assertIn('ค่า',render_markdown(plan_goals([goal()],p,b,DAY)))


if __name__=='__main__':unittest.main()
