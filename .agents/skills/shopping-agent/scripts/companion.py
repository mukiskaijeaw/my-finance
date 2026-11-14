"""Financial companion router. Local data, reused engines and template rendering."""
import json
from pathlib import Path
from datetime import timedelta
from goal_engine import target_day,amount
from shared_state import build_shared
from companion_engine import daily_states,money_leaks,reduction_states,travel_states,potential_goal_draft


def demo_input(current):
    raw=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/companion-demo.json').read_text(encoding='utf-8'))
    profile=dict(raw['profile'],as_of=current.isoformat())
    end=target_day('สิ้นเดือน',current)
    # The next receipt date must be strictly after today for the existing cycle engine.
    receipt=end if end>current else end+timedelta(days=1)
    options=dict(raw['budget'],next_income_date=receipt.isoformat(),obligations=[
        dict(id='demo-unpaid-bills',amount=raw['upcoming_expenses'],due=end.isoformat(),certainty='confirmed',state='unpaid',covered_by='reserved')])
    rows=[]
    for group in raw['transaction_groups']:
        for index in range(group['count']):
            day=current.replace(day=1+index%current.day)
            rows.append(dict(transaction_id='DEMO-'+str(len(rows)+1),date=day.isoformat(),year_month=day.strftime('%Y-%m'),transaction_type='expense',amount_thb=group['amount'],category=group['category'],description=group['description'],data_quality_flag=''))
    for kind,value,description in [('income',profile['income'],'รายได้สุทธิจำลอง'),('transfer',raw['savings_transferred'],'โอนเข้าบัญชีออมของตัวเองจำลอง')]:
        rows.append(dict(transaction_id='DEMO-'+str(len(rows)+1),date=current.replace(day=1).isoformat(),year_month=current.strftime('%Y-%m'),transaction_type=kind,amount_thb=value,description=description,category=kind,data_quality_flag=''))
    return dict(profile=profile,budget=options,transactions=rows,subscriptions=raw['subscriptions'],balance_includes_today_expenses=True,synthetic=True)


def run_companion(request,store,current):
    data=dict(request)
    if request.get('synthetic') is True:
        fixture=demo_input(current)
        # Explicit inputs can override fixture values; never mix with the real provider.
        data=dict(fixture,**request)
    snapshot=store.read()
    action=data.get('action','daily');rows=data.get('transactions',[])
    shared=build_shared(data.get('profile',{}),data.get('budget',{}),snapshot,current,data.get('forecast'),data.get('coverage')) if action in ('daily','travel') else None
    if action=='daily':
        report=daily_states(shared,rows,current,balance_includes_today=data.get('balance_includes_today_expenses'))
    elif action in ('leaks','subscriptions'):
        analysis=money_leaks(rows,current,data.get('subscriptions',[]))
        report=dict(analysis=analysis,simulation=reduction_states(analysis))
    elif action=='potential_goal':
        # A potential reduction is only a draft. Actual money and savings stay unchanged.
        report=potential_goal_draft(snapshot,data['goal_id'],data['potential_monthly'])
    elif action=='travel':
        report=travel_states(shared,data['trip'],current)
    else:raise ValueError('unknown_companion_action')
    return dict(kind=action,current_date=current.isoformat(),synthetic=data.get('synthetic') is True,
                revision=snapshot['revision'],goals=[dict(goal_id=g['goal_id'],goal_name=g['goal_name']) for g in snapshot['goals'] if g['status']=='ACTIVE'],
                report=report)


def render_companion(result):
    template=Path(__file__).resolve().parents[1]/'assets/companion-inline.html'
    encoded=json.dumps(result,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    raw=template.read_text(encoding='utf-8').replace('__COMPANION_DATA__',encoded)
    if len(raw.encode('utf-8'))>1000000:raise ValueError('companion_ui_too_large_narrow_simulation')
    return raw
