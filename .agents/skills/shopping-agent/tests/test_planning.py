import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from planning import budget, fit, opportunity, installment, what_if, readiness, run
from shopping import run_request, render, save_purchase_goals
from engine import read_ledger, SCHEMA

DAY = date(2026, 11, 12)


def profile(**kw):
    p = dict(income='30000', essential='15000', debt='2000', saving='3000', cash='20000',
             emergency='10000', reserved='2000', as_of=DAY.isoformat(), complete=True,
             future_complete=True, future_extra=[], income_kind='stable')
    p.update(kw)
    return p


def cycle(**kw):
    b = dict(cycle_complete=True, next_income_date='2026-11-30', minimum_remaining='500', obligations=[])
    b.update(kw)
    return b


def bill(**kw):
    b = dict(id='rent', due='2026-11-15', amount='3000', certainty='confirmed', state='unpaid', covered_by='none')
    b.update(kw)
    return b


def listing(price='1000', day=None):
    return dict(name='Synthetic item', price=price, shipping='0', shipping_verified=True, discount='0',
                verified=True, url='https://example.org/item', checked=(day or DAY).isoformat())


def plan(**kw):
    p = dict(verified=True, checked=DAY.isoformat(), source='https://example.org/terms', down_payment='0',
             periods=2, payments=['500', '500'], interest_total='0', fees='0', total_payable='1000',
             cashflows_complete=True,
             cashflows=[dict(month=m, income='30000', outflow='20000', pre_income_outflow='0', protected_floor='12500')
                        for m in ('2026-11', '2026-12')])
    p.update(kw)
    return p


class BudgetTests(unittest.TestCase):
    def test_unspecified_budget(self):
        r = budget(profile(), cycle(), DAY)
        self.assertEqual((r['user_budget'], r['affordable_budget'], r['recommended_budget']), (None, '8000', '7500'))

    def test_budget_conflict_preserves_original(self):
        r = budget(profile(), cycle(user_budget='9000'), DAY)
        self.assertEqual((r['user_budget'], r['recommended_budget'], r['budget_difference'], r['budget_conflict']), ('9000', '7500', '1500', True))

    def test_lower_user_budget(self):
        self.assertEqual(budget(profile(), cycle(user_budget='1000'), DAY)['recommended_budget'], '1000')

    def test_rent_due_despite_current_cash(self):
        c = cycle(obligations=[bill(amount='7000')])
        self.assertEqual(fit(profile(), '3000', c, DAY)['status'], 'SAVE_FIRST')
        self.assertEqual(budget(profile(), c, DAY)['recommended_budget'], '500')

    def test_subscription_due(self):
        c = cycle(obligations=[bill(id='subscription', amount='299')])
        self.assertEqual(budget(profile(), c, DAY)['recommended_budget'], '7201')

    def test_paid_bill_not_deducted_twice(self):
        self.assertEqual(budget(profile(), cycle(obligations=[bill(state='paid', due='2026-11-10')]), DAY)['recommended_budget'], '7500')

    def test_reserved_bill_not_deducted_twice(self):
        self.assertEqual(budget(profile(), cycle(obligations=[bill(amount='2000', covered_by='reserved')]), DAY)['recommended_budget'], '7500')

    def test_future_reserved_not_deducted_twice(self):
        p = profile(future_extra=[{'month': 1, 'amount': '1000'}])
        self.assertEqual(budget(p, cycle(obligations=[bill(amount='1000', covered_by='future_extra')]), DAY)['recommended_budget'], '6500')

    def test_duplicate_or_invalid_coverage(self):
        for bills in ([bill(), bill()], [bill(covered_by='reserved')]):
            self.assertEqual(budget(profile(), cycle(obligations=bills), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_predictions_need_confirmation(self):
        self.assertEqual(budget(profile(), cycle(obligations=[bill(certainty='projected')]), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_missing_buffer_not_zero(self):
        c = cycle(); c.pop('minimum_remaining')
        self.assertEqual(budget(profile(), c, DAY)['status'], 'INSUFFICIENT_DATA')

    def test_missing_profile_and_stale(self):
        for p in ({}, profile(as_of='2026-01-01'), profile(cash=None)):
            self.assertEqual(budget(p, cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_invalid_cycle_dates(self):
        for d in ('2026-11-12', '2027-11-12', 'bad'):
            self.assertEqual(budget(profile(), cycle(next_income_date=d), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_freelancer_conservative_income(self):
        p = profile(income_kind='variable', income_history=['22000', '30000', '35000'])
        self.assertEqual(budget(p, cycle(), DAY)['monthly_surplus'], '2000')
        p['income_history'] = ['22000']
        self.assertEqual(budget(p, cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_monthly_deficit_not_affordable(self):
        r = budget(profile(income='19000'), cycle(), DAY)
        self.assertEqual((r['status'], r['recommended_budget']), ('NOT_AFFORDABLE', '0'))


class ScenarioTests(unittest.TestCase):
    def opportunity(self, draw='0', free='1000', diversion='0'):
        return opportunity(profile(), '1000', dict(confirmed=True, free_cash_used=free,
            goals=[dict(id='travel', target='10000', saved='2000', monthly_contribution='1000',
                        purchase_draw=draw, monthly_diversion=diversion, approved_change=True)]), cycle(), DAY)

    def test_separate_money_zero_delay(self):
        self.assertEqual(self.opportunity()['scenarios'][0]['delay_months'], 0)

    def test_goal_cash_draw_delay(self):
        r = self.opportunity(draw='1000', free='0')['scenarios'][0]
        self.assertEqual((r['before_months'], r['after_months'], r['delay_months'], r['savings_reduced']), (8, 9, 1, '1000'))

    def test_stop_contributing_not_fake_zero_eta(self):
        self.assertIsNone(self.opportunity(diversion='1000')['scenarios'][0]['after_months'])

    def test_unapproved_goal_change(self):
        spec = dict(confirmed=True, free_cash_used='0', goals=[dict(id='g', target='5000', saved='1000', monthly_contribution='1000', purchase_draw='1000', monthly_diversion='0')])
        self.assertEqual(opportunity(profile(), '1000', spec, cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_cash_vs_installment_full_term(self):
        r = installment(profile(), '1000', plan(), cycle(), DAY)
        self.assertEqual((r['status'], r['additional_cost'], len(r['schedule'])), ('AFFORDABLE', '0', 2))
        self.assertEqual(r['schedule'][1]['cash_after'], '39000')

    def test_hidden_fee_visible(self):
        r = installment(profile(), '1000', plan(fees='100', total_payable='1100'), cycle(), DAY)
        self.assertEqual((r['additional_cost'], r['fees']), ('100', '100'))

    def test_later_month_liquidity_failure(self):
        p = plan(); p['cashflows'][1].update(outflow='40000')
        self.assertEqual(installment(profile(), '1000', p, cycle(), DAY)['status'], 'NOT_AFFORDABLE')

    def test_unverified_or_missing_terms(self):
        for p in (plan(verified=False), plan(fees=None), plan(cashflows=[]), plan(total_payable='900'), plan(checked='2026-01-01')):
            self.assertEqual(installment(profile(), '1000', p, cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_duplicate_month_and_missing_debt_rejected(self):
        for key, value in [('month', '2026-11'), ('outflow', '100')]:
            p = plan(); p['cashflows'][1][key] = value
            self.assertEqual(installment(profile(), '1000', p, cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_cycle_bill_not_omitted_from_installments(self):
        self.assertEqual(installment(profile(), '1000', plan(), cycle(obligations=[bill()]), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_hypothetical_no_mutation_basket(self):
        p, c = profile(), cycle()
        before = copy.deepcopy((p, c))
        r = what_if(p, {'changes': {'income': '33000'}, 'prices': ['5000', '5000']}, c, DAY)
        self.assertEqual((p, c), before)
        self.assertEqual(r['basket_total'], '10000')
        self.assertEqual((r['actual']['monthly_surplus'], r['hypothetical']['monthly_surplus']), ('10000', '13000'))
        self.assertEqual(r['data_mode'], 'hypothetical')

    def test_hypothetical_cannot_refresh_profile(self):
        r = what_if(profile(), {'changes': {'as_of': DAY.isoformat()}, 'prices': ['1']}, cycle(), DAY)
        self.assertEqual(r['status'], 'INSUFFICIENT_DATA')


class ReadinessTests(unittest.TestCase):
    def goal(self, **kw):
        g = dict(id='one', allocated_savings='500', allocation_confirmed=True,
                 planned_monthly_contribution='500', latest_listing=listing(), product_name='Synthetic item', target_price='900')
        g.update(kw)
        return g

    def test_recheck_changed_price(self):
        a = readiness(profile(), [self.goal()], cycle(), DAY)['goals'][0]
        b = readiness(profile(), [self.goal(latest_listing=listing('2000'))], cycle(), DAY)['goals'][0]
        self.assertEqual((a['months'], b['months']), (1, 3))

    def test_multiple_goals_same_cash_pool(self):
        r = readiness(profile(), [self.goal(allocated_savings='5000'), self.goal(id='two', allocated_savings='5000')], cycle(), DAY)
        self.assertEqual(r['status'], 'INSUFFICIENT_DATA')

    def test_multiple_goals_monthly_overcommit(self):
        r = readiness(profile(), [self.goal(planned_monthly_contribution='11000')], cycle(), DAY)
        self.assertEqual(r['status'], 'INSUFFICIENT_DATA')

    def test_stale_price_and_planned_not_saved(self):
        for g in (self.goal(allocation_confirmed=False), self.goal(latest_listing=listing(day=date(2026, 1, 1)))):
            self.assertEqual(readiness(profile(), [g], cycle(), DAY)['status'], 'INSUFFICIENT_DATA')

    def test_consent_and_exclusive_separate_storage(self):
        req = dict(profile=profile(), planning=dict(action='readiness', budget=cycle(), goals=[self.goal()]))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'local' / 'goals-v1.json'
            with self.assertRaises(ValueError): save_purchase_goals(path, req, False, DAY)
            data = save_purchase_goals(path, req, True, DAY)
            self.assertFalse(data['monitoring'])
            self.assertNotIn('profile', data)
            with self.assertRaises(FileExistsError): save_purchase_goals(path, req, True, DAY)
            with self.assertRaises(ValueError): save_purchase_goals(Path(d) / 'database.csv', req, True, DAY)


class IntegrationTests(unittest.TestCase):
    def test_selected_provider_fresh_reads_and_no_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'AGENTS.md').write_text('Local synthetic provider', encoding='utf-8')
            ledger = root / 'database.csv'
            ledger.write_text(','.join(SCHEMA) + '\n', encoding='utf-8')
            path = root / 'profile.json'
            path.write_text(json.dumps({'schema_version': 1, 'profile': profile()}), encoding='utf-8')
            req = dict(include_financial=True, profile_path=str(path), planning=dict(action='budget', budget=cycle()))
            before = ledger.read_bytes()
            a = run_request(req, DAY, root)[1]['planning_result']['recommended_budget']
            path.write_text(json.dumps({'schema_version': 1, 'profile': profile(cash='21000')}), encoding='utf-8')
            b = run_request(req, DAY, root)[1]['planning_result']['recommended_budget']
            self.assertEqual((a, b), ('7500', '8500'))
            self.assertEqual(ledger.read_bytes(), before)

    def test_legacy_zero_profile_never_confirms_affordability(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'AGENTS.md').write_text('Synthetic provider', encoding='utf-8')
            (root / 'database.csv').write_text(','.join(SCHEMA) + '\n', encoding='utf-8')
            path = root / 'profile.json'
            path.write_text('{"monthly_net_income":0}', encoding='utf-8')
            req = dict(include_financial=True, profile_path=str(path), planning=dict(action='budget', budget=cycle()))
            _, rep = run_request(req, DAY, root)
            self.assertEqual(rep['planning_result']['status'], 'INSUFFICIENT_DATA')
            self.assertIn('profile_unavailable_or_unsupported', rep['data_quality']['profile'])

    def test_price_only_never_loads_profile_or_planning(self):
        with patch('shopping.load_finance', side_effect=AssertionError('private read')):
            req, rep = run_request(dict(include_financial=False, profile=profile(), planning={'action': 'budget'}, listings=[listing()]), DAY)
        self.assertNotIn('planning_result', rep)
        self.assertNotIn('Smart Budget', render(req, rep))

    def test_network_forbidden_end_to_end(self):
        with patch('socket.socket', side_effect=AssertionError('network')):
            req, rep = run_request(dict(include_financial=True, profile=profile(), planning=dict(action='budget', budget=cycle())), DAY)
            self.assertEqual(rep['planning_result']['recommended_budget'], '7500')
            self.assertIn('7,500.00', render(req, rep))

    def test_product_cards_use_dated_bills(self):
        req, rep = run_request(dict(include_financial=True, profile=profile(), listings=[listing('3000')],
                              planning=dict(action='budget', budget=cycle(obligations=[bill(amount='7000')]))), DAY)
        self.assertEqual(rep['results'][0]['financial']['status'], 'SAVE_FIRST')

    def test_all_templates(self):
        from planning_cards import render_planning
        inputs = [dict(action='budget', budget=cycle()), dict(action='fit', budget=cycle(), price='1000'),
                  dict(action='installment', budget=cycle(), price='1000', installment=plan()),
                  dict(action='what_if', budget=cycle(), scenario=dict(changes={'income': '33000'}, prices=['1000'])),
                  dict(action='readiness', budget=cycle(), goals=[ReadinessTests().goal()]),
                  dict(action='opportunity', budget=cycle(), price='1000', opportunity=dict(confirmed=True, free_cash_used='1000', goals=[]))]
        for req in inputs:
            text = render_planning(req, run(profile(), req, DAY))
            self.assertIn('##', text)
            self.assertIn('**คำแนะนำ:**', text)
            self.assertNotIn('<html', text)

    def test_cli_plan_stdin_markdown(self):
        from shopping import today
        p = profile(as_of=today().isoformat())
        from datetime import timedelta
        c = cycle(next_income_date=(today() + timedelta(days=10)).isoformat())
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'shopping.py'
        r = subprocess.run([sys.executable, str(path), 'plan', '--format', 'markdown'], input=json.dumps(dict(profile=p, planning=dict(action='budget', budget=c))), text=True, capture_output=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('7,500.00', r.stdout)

    def test_finance_adapter_read_only_11_columns(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'database.csv'
            raw = ','.join(SCHEMA[:11]) + '\nTXN000001,2026-11-10,expense,Synthetic,100,Other,,2026-11,manual_entry,manual_entry,\n'
            p.write_text(raw, encoding='utf-8')
            self.assertEqual(read_ledger(p, DAY)['schema_columns'], 11)
            self.assertEqual(p.read_text(encoding='utf-8'), raw)

    def test_query_never_accepts_planning_data(self):
        from shopping import product_query
        for key in ('planning', 'cash', 'income', 'obligations', 'recommended_budget'):
            with self.assertRaises(ValueError): product_query({'model': 'Synthetic', key: '1000'})


if __name__ == '__main__':
    unittest.main()
