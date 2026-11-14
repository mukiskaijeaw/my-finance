"""Opt-in financial planning. Pure Decimal calculations; no LLM, files or network.

Contracts and provenance rules: references/planning-contract.md.
"""
from copy import deepcopy
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from engine import financial_fit, money, fresh


def insufficient(*issues):
    return {'status': 'INSUFFICIENT_DATA', 'issues': list(issues)}


def months_to(target, balance, contribution):
    gap = max(Decimal(0), target - balance)
    return 0 if not gap else (int((gap / contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution > 0 else None)


def budget(profile, options, today):
    """Protect outstanding obligations until next income; never infer paid bills."""
    base = financial_fit(profile, '0', today)
    if base['status'] == 'INSUFFICIENT_DATA':
        return base
    try:
        if options.get('cycle_complete') is not True:
            return insufficient('confirm_cycle_obligations_complete')
        end = date.fromisoformat(options['next_income_date'])
        if not today < end <= today + timedelta(days=93):
            raise ValueError('invalid_next_income_date')
        minimum = money(options.get('minimum_remaining'))
        obligations = options['obligations']
        if not isinstance(obligations, list):
            raise ValueError('obligations_required')
        seen, totals, rows = set(), {'none': Decimal(0), 'reserved': Decimal(0), 'future_extra': Decimal(0)}, []
        for item in obligations:
            ident = item['id']
            if not isinstance(ident, str) or not ident.strip() or ident in seen:
                raise ValueError('duplicate_or_invalid_obligation_id')
            seen.add(ident)
            due = date.fromisoformat(item['due'])
            amount = money(item['amount'])
            if item.get('certainty') != 'confirmed':
                return insufficient('projected_obligation_requires_confirmation')
            if item.get('state') not in ('paid', 'unpaid') or item.get('covered_by') not in totals:
                raise ValueError('obligation_state_or_coverage_required')
            if due > end:
                raise ValueError('obligation_outside_cycle_use_future_extra')
            if item['state'] == 'paid':
                if due > today:
                    raise ValueError('future_bill_marked_paid')
                rows.append({**item, 'additional_reserve': '0'})
                continue
            totals[item['covered_by']] += amount
            rows.append({**item, 'additional_reserve': str(amount if item['covered_by'] == 'none' else 0)})
        if totals['reserved'] > money(profile['reserved']) or totals['future_extra'] > sum((money(x['amount']) for x in profile['future_extra']), Decimal(0)):
            raise ValueError('coverage_exceeds_declared_reserves')
        # Base engine already protects emergency, reserved and all future_extra.
        raw = money(profile['cash']) - money(profile['emergency']) - money(profile['reserved']) - sum((money(x['amount']) for x in profile['future_extra']), Decimal(0)) - totals['none']
        surplus = money(profile['income']) - money(profile['essential']) - money(profile['debt']) - money(profile['saving'])
        if profile['income_kind'] == 'variable':
            surplus = min(money(profile['income']), *(money(x) for x in profile['income_history'])) - money(profile['essential']) - money(profile['debt']) - money(profile['saving'])
        affordable = max(Decimal(0), raw) if surplus >= 0 else Decimal(0)
        recommended = max(Decimal(0), affordable - minimum)
        user = money(options['user_budget']) if options.get('user_budget') is not None else None
        if user is not None:
            recommended = min(recommended, user)
        return {'status': 'AFFORDABLE' if recommended > 0 else 'NOT_AFFORDABLE', 'issues': [],
                'user_budget': str(user) if user is not None else None,
                'affordable_budget': str(affordable), 'recommended_budget': str(recommended),
                'budget_conflict': user is not None and user > recommended,
                'budget_difference': str(user - recommended) if user is not None else None,
                'current_balance': str(profile['cash']), 'upcoming_additional': str(totals['none']),
                'protected_savings': str(money(profile['emergency']) + money(profile['reserved'])),
                'available_spending_cash': str(raw), 'minimum_remaining': str(minimum),
                'monthly_surplus': str(surplus), 'cycle_end': end.isoformat(), 'obligations': rows,
                'assumptions': ['No arbitrary buffer percentage; minimum_remaining is user-confirmed.',
                    'No new income credited before next_income_date; same-day bills protected first.',
                    'Monthly budget is a flow; only unpaid cash obligations reduce cash.',
                    'Legacy future_extra remains reserved in full; not added twice.']}
    except (ValueError, TypeError, KeyError) as exc:
        return insufficient(str(exc))


def fit(profile, price, options, today):
    b = budget(profile, options, today)
    if b['status'] == 'INSUFFICIENT_DATA':
        return b
    adjusted = deepcopy(profile)
    adjusted['reserved'] = str(money(profile['reserved']) + money(b['upcoming_additional']) + money(b['minimum_remaining']))
    result = financial_fit(adjusted, price, today)
    result['budget'] = b
    return result


def opportunity(profile, price, spec, options, today):
    b = budget(profile, options, today)
    if b['status'] == 'INSUFFICIENT_DATA':
        return b
    try:
        cost = money(price)
        if spec.get('confirmed') is not True:
            return insufficient('confirm_funding_and_goals')
        free = money(spec['free_cash_used'])
        if free > money(b['recommended_budget']):
            raise ValueError('free_cash_exceeds_recommended_budget')
        goals, ids, total_draw, contributions, rows = spec['goals'], set(), Decimal(0), Decimal(0), []
        for goal in goals:
            ident = goal['id']
            if not isinstance(ident, str) or not ident.strip() or ident in ids:
                raise ValueError('duplicate_goal')
            ids.add(ident)
            target, saved, monthly, draw, diverted = [money(goal[k]) for k in ('target', 'saved', 'monthly_contribution', 'purchase_draw', 'monthly_diversion')]
            if draw > saved or diverted > monthly:
                raise ValueError('goal_funding_inconsistent')
            if (draw or diverted) and goal.get('approved_change') is not True:
                return insufficient('explicit_goal_change_permission_required')
            before, after = months_to(target, saved, monthly), months_to(target, saved - draw, monthly - diverted)
            total_draw += draw
            contributions += monthly
            rows.append({'id': ident, 'before_months': before, 'after_months': after,
                         'delay_months': after - before if after is not None and before is not None else None,
                         'savings_reduced': str(draw), 'monthly_diversion': str(diverted)})
        if contributions > money(profile['saving']) or total_draw + free != cost:
            raise ValueError('purchase_funding_or_goal_contributions_inconsistent')
        # Goal balances must be part of protected reserved cash, never extra assets.
        if sum((money(g['saved']) for g in goals), Decimal(0)) > money(profile['reserved']):
            raise ValueError('goal_balances_not_in_protected_cash')
        return {'status': 'AFFORDABLE' if not total_draw else 'SAVE_FIRST', 'issues': [], 'scenarios': rows,
                'scenario_a_cash_change': '0', 'scenario_b_cash_change': str(-cost),
                'monthly_cashflow_change': '0', 'funding': {'free_cash': str(free), 'goal_cash': str(total_draw)},
                'assumptions': ['Explicit scenario only; no goal or balance is changed.',
                    'Monthly diversion reallocates the existing savings flow; total cash flow unchanged.',
                    'No investment return or interest assumed; emergency cash never funds purchases.']}
    except (ValueError, TypeError, KeyError) as exc:
        return insufficient(str(exc))


def installment(profile, cash_price, plan, options, today):
    b = budget(profile, options, today)
    if b['status'] == 'INSUFFICIENT_DATA':
        return b
    try:
        if plan.get('verified') is not True or not fresh(plan.get('checked'), today, 7) or not str(plan.get('source', '')).startswith('https://'):
            return insufficient('installment_terms_unverified_or_outdated')
        cost, down, fees, interest = [money(v) for v in (cash_price, plan['down_payment'], plan['fees'], plan['interest_total'])]
        n = plan['periods']
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 120:
            raise ValueError('invalid_periods')
        payments = [money(x) for x in plan['payments']]
        flows = plan['cashflows']
        if len(payments) != n or len(flows) != n or plan.get('cashflows_complete') is not True:
            return insufficient('complete_term_cashflows_required')
        total = down + sum(payments, Decimal(0)) + fees
        if total != cost + interest + fees or money(plan['total_payable']) != total:
            raise ValueError('installment_total_inconsistent')
        # Down payment and fee upfront; recurring obligations/savings are in outflow.
        balance = money(profile['cash']) - down - fees
        rows, periods, safe = [], set(), down + fees <= money(b['recommended_budget'])
        bills = sum((money(x['amount']) for x in b['obligations'] if x['state'] == 'unpaid'), Decimal(0))
        covered_bills = sum((money(x['amount']) for x in b['obligations'] if x['state'] == 'unpaid' and x['covered_by'] == 'reserved'), Decimal(0))
        protected = money(profile['emergency']) + money(options['minimum_remaining']) + max(Decimal(0), money(profile['reserved']) - covered_bills)
        baseline_outflow = money(profile['essential']) + money(profile['debt']) + money(profile['saving'])
        income_limit = money(profile['income'])
        if profile['income_kind'] == 'variable':
            income_limit = min(income_limit, *(money(x) for x in profile['income_history']))
        start = date.fromisoformat(options['next_income_date'])
        for index, (payment, flow) in enumerate(zip(payments, flows)):
            month = flow['month']
            expected = (start.year + (start.month - 1 + index) // 12, (start.month - 1 + index) % 12 + 1)
            if month != f'{expected[0]:04d}-{expected[1]:02d}' or month in periods:
                raise ValueError('cashflows_must_cover_consecutive_months')
            periods.add(month)
            inflow, outflow, floor, pre_income = [money(flow[k]) for k in ('income', 'outflow', 'protected_floor', 'pre_income_outflow')]
            if pre_income > outflow or floor < protected or outflow < baseline_outflow or inflow > income_limit:
                raise ValueError('cashflow_floor_or_order_inconsistent')
            if index == 0 and pre_income < bills:
                raise ValueError('current_cycle_bills_missing_before_income')
            # Conservative ordering: payment and specified bills before income.
            trough = balance - pre_income - payment
            net = inflow - outflow - payment
            balance += net
            safe = safe and trough >= floor and balance >= floor and net >= 0
            rows.append({'month': month, 'payment': str(payment), 'cash_after': str(balance),
                         'cash_before_income': str(trough), 'monthly_remaining': str(net), 'protected_floor': str(floor)})
        return {'status': 'AFFORDABLE' if safe else 'NOT_AFFORDABLE', 'issues': [], 'cash_fit': fit(profile, str(cost), options, today),
                'cash_total': str(cost), 'installment_total': str(total), 'additional_cost': str(total - cost),
                'down_payment': str(down), 'fees': str(fees), 'interest_total': str(interest), 'schedule': rows,
                'assumptions': ['Cashflows include existing debts, essentials, savings and dated extras once.',
                    'protected_floor includes remaining protected assets, not bills already in outflow.',
                    'Payment precedes income conservatively; 0% does not imply no fees or no risk.']}
    except (ValueError, TypeError, KeyError) as exc:
        return insufficient(str(exc))


def what_if(profile, spec, options, today):
    try:
        changes = spec['changes']
        allowed = {'income', 'essential', 'debt', 'saving', 'cash', 'earmarked', 'future_extra', 'income_history'}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError('unsupported_scenario_change')
        costs = [money(x) for x in spec['prices']]
        if not costs:
            raise ValueError('scenario_prices_required')
        candidate = deepcopy(profile)
        candidate.update(deepcopy(changes))
        scenario_options = deepcopy(options)
        # One explicitly stated purchase basket, no changes written to source.
        total = str(sum(costs, Decimal(0)))
        return {'data_mode': 'hypothetical', 'status': 'SIMULATION', 'issues': [],
                'basket_total': total, 'actual': fit(profile, total, options, today),
                'hypothetical': fit(candidate, total, scenario_options, today),
                'changed_fields': sorted(changes), 'assumptions': ['Simulation only; no actual profile, goal or transaction is changed.']}
    except (ValueError, TypeError, KeyError) as exc:
        return insufficient(str(exc))


def readiness(profile, goals, options, today):
    b = budget(profile, options, today)
    if b['status'] == 'INSUFFICIENT_DATA':
        return b
    try:
        if not isinstance(goals, list) or not goals:
            return insufficient('purchase_goals_required')
        ids, allocated, contributions, results = set(), Decimal(0), Decimal(0), []
        for goal in goals:
            if goal['id'] in ids:
                raise ValueError('duplicate_purchase_goal')
            ids.add(goal['id'])
            saved = money(goal['allocated_savings'])
            monthly = money(goal['planned_monthly_contribution'])
            allocated += saved
            contributions += monthly
            if goal.get('allocation_confirmed') is not True:
                return insufficient('planned_savings_are_not_actual_allocations')
            # Latest listing must be reverified externally, never copied from stored goal.
            from engine import effective_price
            price = effective_price(goal['latest_listing'], today)
            if price['effective'] is None:
                return insufficient('latest_goal_price_not_verified')
            cost = money(price['effective'])
            eta = months_to(cost, saved, monthly)
            estimated_date = None
            if eta is not None:
                start = today if eta == 0 else date.fromisoformat(options['next_income_date'])
                offset = max(0, eta - 1)
                year, month = start.year + (start.month - 1 + offset) // 12, (start.month - 1 + offset) % 12 + 1
                if year <= 9999:
                    estimated_date = date(year, month, min(start.day, monthrange(year, month)[1])).isoformat()
            results.append({'id': goal['id'], 'latest_verified_price': str(cost), 'allocated_savings': str(saved),
                            'planned_monthly_contribution': str(monthly), 'months': eta,
                            'status': 'AFFORDABLE' if saved >= cost else ('SAVE_FIRST' if eta is not None else 'NOT_AFFORDABLE'),
                            'remaining': str(max(Decimal(0), cost - saved)),
                            'estimated_purchase_date': estimated_date,
                            'last_checked': today.isoformat()})
        if allocated > money(b['recommended_budget']) or contributions > max(Decimal(0), Decimal(b['monthly_surplus'])):
            return insufficient('purchase_goals_double_allocation_or_overcommitted')
        return {'status': 'AFFORDABLE' if all(x['status'] == 'AFFORDABLE' for x in results) else 'SAVE_FIRST',
                'issues': [], 'goals': results, 'total_allocated': str(allocated),
                'assumptions': ['Allocated savings are slices of one available cash pool; no amounts added to cash.',
                    'Planned monthly contributions are future intentions, not cash already saved.',
                    'Estimated date assumes monthly receipts on the next_income_date day; later dates are hypothetical.',
                    'Rechecked on request only; no background monitoring.']}
    except (ValueError, TypeError, KeyError) as exc:
        return insufficient(str(exc))


def run(profile, request, today):
    """Explicit action chosen by Codex intent reasoning; calculations stay here."""
    action, options = request.get('action'), request.get('budget', {})
    if action == 'budget':
        return budget(profile, options, today)
    if action == 'fit':
        return fit(profile, request.get('price'), options, today)
    if action == 'opportunity':
        return opportunity(profile, request.get('price'), request.get('opportunity', {}), options, today)
    if action == 'installment':
        return installment(profile, request.get('price'), request.get('installment', {}), options, today)
    if action == 'what_if':
        return what_if(profile, request.get('scenario', {}), options, today)
    if action == 'readiness':
        return readiness(profile, request.get('goals', []), options, today)
    return insufficient('unknown_planning_action')
