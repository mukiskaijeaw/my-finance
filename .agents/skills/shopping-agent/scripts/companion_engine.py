"""Deterministic daily, money-leak and travel functions. No LLM, network or writes."""
from calendar import monthrange
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_DOWN
from itertools import product
from collections import defaultdict
from goal_engine import amount, target_day, plan_goals
from shared_state import build_shared

D=Decimal


def floor_money(n):return n.quantize(D('.01'),rounding=ROUND_DOWN)


def normalize_transactions(rows,current):
    found=[];ids=set();issues=[]
    for row in rows:
        try:
            when=date.fromisoformat(row['date']);value=amount(row['amount_thb']);ident=row['transaction_id']
            if when>current or row.get('year_month',when.strftime('%Y-%m'))!=when.strftime('%Y-%m'):
                raise ValueError('invalid_transaction_date')
            if not ident or ident in ids:raise ValueError('duplicate_transaction_id')
            if row['transaction_type'] not in ('expense','income','transfer','investment'):raise ValueError('invalid_transaction_type')
            ids.add(ident)
            if row.get('data_quality_flag'):issues.append('transaction_needs_review')
            found.append(dict(row,date=when.isoformat(),amount_thb=str(value)))
        except (ValueError,KeyError,TypeError):issues.append('invalid_transaction')
    return found,sorted(set(issues))


def daily_spending(shared,rows,current,*,balance_includes_today=None,extra='0'):
    portfolio=shared['portfolio'];rows,issues=normalize_transactions(rows,current)
    spent=sum((amount(r['amount_thb']) for r in rows if r['date']==current.isoformat() and r['transaction_type']=='expense'),D(0))
    end=current.replace(day=monthrange(current.year,current.month)[1]);days=(end-current).days
    result=dict(kind='daily',current_date=current.isoformat(),days_remaining=days,saving_days=days+1,
                today_recorded=str(spent),status='INSUFFICIENT_DATA',issues=issues,
                today_budget=None,today_remaining=None,available_month=None,tomorrow_daily=None,spending_progress=None)
    if balance_includes_today is not True:
        result['issues']+=['confirm_balance_includes_today_expenses'];return result
    if portfolio['status']=='INSUFFICIENT_DATA':result['issues']+=portfolio['issues'];return result
    if issues: return result
    available=D(portfolio['remaining_spending_budget'])
    # Current balance already reflects today's confirmed expenses; never subtract twice.
    before_today=available+spent
    today_budget=floor_money(max(D(0),before_today)/(days+1))
    additional=amount(extra);remaining=available-additional
    today_left=today_budget-spent-additional
    tomorrow=floor_money(max(D(0),remaining)/days) if days else None
    progress=min(D(100),(spent+additional)/today_budget*100) if today_budget else None
    status='INSUFFICIENT_FUNDS' if remaining<0 or portfolio['status']=='NOT_FEASIBLE' else 'CAUTION' if today_left<0 else 'ON_TRACK'
    if additional>0:
        adjusted=deepcopy(shared['profile']);cash=amount(adjusted['cash'])-additional
        if cash<0:status='INSUFFICIENT_FUNDS'
        else:
            adjusted['cash']=str(cash)
            changed=build_shared(adjusted,shared['budget_options'],shared['snapshot'],current,shared.get('forecast'),shared.get('coverage'))
            if changed['portfolio']['status']!='FEASIBLE':status='INSUFFICIENT_FUNDS'
    message='วันนี้ยังอยู่ในงบครับ ใช้ได้ แต่อย่าเพิ่งใช้ชีวิตเหมือนเงินเดือนออก'
    if status=='CAUTION':message='เกินงบวันนี้ไป '+str(-today_left)+' บาทครับ วันต่อไปต้องเบาลงหน่อย'
    if status=='INSUFFICIENT_FUNDS':message='ยอดนี้กระทบเงินที่ต้องกันไว้ครับ ลองลดรายจ่ายหรือทบทวนแผนก่อน'
    commitments=D(portfolio['budget']['recommended_budget'])-available
    result.update(status=status,today_budget=str(today_budget),today_remaining=str(today_left),
                  available_month=str(remaining),tomorrow_daily=str(tomorrow) if tomorrow is not None else None,
                  active_goal_allocations=str(commitments),simulated_extra=str(additional),
                  spending_progress=str(progress.quantize(D('.1'))) if progress is not None else None,message=message)
    return result


def daily_states(shared,rows,current,*,balance_includes_today):
    initial=daily_spending(shared,rows,current,balance_includes_today=balance_includes_today)
    if initial['today_budget'] is None:return dict(initial=initial,values=[],states=[])
    ceiling=max(D(initial['today_budget'])*3,D(initial['available_month']),D(0))
    values=sorted(set([str(floor_money(ceiling*i/100)) for i in range(101)]+['0']),key=D)
    # Each state is computed locally once; the UI only looks up a chosen step.
    states=[daily_spending(shared,rows,current,balance_includes_today=True,extra=v) for v in values]
    return dict(initial=initial,values=values,states=states)


def money_leaks(rows,current,subscriptions=()):
    rows,issues=normalize_transactions(rows,current)
    groups=defaultdict(list);duplicate_groups=defaultdict(list);recurring=defaultdict(set)
    for row in rows:
        if row['transaction_type']!='expense':continue
        when=date.fromisoformat(row['date'])
        description=(row.get('description') or '').strip()
        recurring[description.casefold()].add(when.strftime('%Y-%m'))
        if when.strftime('%Y-%m')!=current.strftime('%Y-%m'):continue
        category=row.get('category') or 'ยังไม่จัดหมวด'
        groups[category].append(row)
        duplicate_groups[(row['date'],row['amount_thb'],description.casefold())].append(row['transaction_id'])
    categories=[]
    for category,items in groups.items():
        total=sum((amount(x['amount_thb']) for x in items),D(0))
        sub_names={s['name'].casefold() for s in subscriptions if s.get('name')}
        is_sub=category.casefold() in ('subscriptions','subscription','สมาชิก') or any((r.get('description') or '').casefold() in sub_names for r in items)
        categories.append(dict(name=category,amount=str(total),count=len(items),is_subscription=is_sub,
                               average=str(floor_money(total/len(items))),
                               small_frequent=len(items)>=3 and total/len(items)<=D(200)))
    categories.sort(key=lambda x:D(x['amount']),reverse=True)
    largest=max((D(x['amount']) for x in categories),default=D(0))
    for item in categories:item['bar_percent']=str((D(item['amount'])/largest*100).quantize(D('.1'))) if largest else '0'
    services=[]
    for sub in subscriptions:
        if not sub.get('name'):raise ValueError('subscription_name_required')
        value=amount(sub.get('amount'));period=sub.get('period')
        monthly=value if period=='monthly' else value/12 if period=='annual' else None
        services.append(dict(name=sub['name'],amount=str(value),period=period,monthly=str(floor_money(monthly)) if monthly is not None else None,annual=str(value if period=='annual' else value*12) if monthly is not None else None,
                             notice='ธุรกรรมไม่ได้บอกว่าใช้บริการบ่อยแค่ไหน ต้องถามผู้ใช้'))
    unusual=[]
    for row in rows:
        if row['transaction_type']!='expense' or not row['date'].startswith(current.strftime('%Y-%m')):continue
        baseline=[amount(r['amount_thb']) for r in rows if r['transaction_type']=='expense' and r.get('category')==row.get('category') and r['date']<row['date']]
        if len(baseline)>=3:
            average=sum(baseline,D(0))/len(baseline)
            if average>0 and amount(row['amount_thb'])>average*2:
                unusual.append(dict(transaction_id=row['transaction_id'],category=row.get('category'),amount=row['amount_thb'],baseline_average=str(floor_money(average)),rule='more_than_2x_prior_category_average_min_3_records'))
    return dict(kind='leaks',current_date=current.isoformat(),categories=categories,subscriptions=services,unusual_candidates=unusual,
                duplicate_candidates=[ids for ids in duplicate_groups.values() if len(ids)>1],
                recurring_candidates=[name for name,months in recurring.items() if name and len(months)>1],issues=issues,
                notice='วิเคราะห์จากรายการที่บันทึก ไม่ใช่หลักฐานว่ารายจ่ายไม่จำเป็นหรือ Subscription ไม่ได้ใช้')


def reduction_states(analysis):
    # At most two observed small-purchase categories, plus three subscription toggles.
    # Keep the product of local states bounded instead of emitting unbounded UI data.
    controls=[]
    if analysis.get('issues'):return dict(controls=[],states={'':dict(monthly='0',annual='0')},notice='ข้อมูลธุรกรรมมีข้อผิดพลาด ต้องตรวจรายการก่อนประเมินเงินที่ลดได้')
    for item in sorted(analysis['categories'],key=lambda x:D(x['amount']),reverse=True):
        if not item['small_frequent'] or item.get('is_subscription') or len(controls)>=2:continue
        maximum=min(item['count'],20)
        controls.append(dict(id='category:'+item['name'],label='ลด '+item['name']+' (ครั้ง/เดือน)',
                             values=list(range(maximum+1)),unit_cost=item['average'],unit_annual=str(D(item['average'])*12),type='range'))
    for index,sub in enumerate(analysis['subscriptions'][:3]):
        if sub['monthly'] is not None:
            controls.append(dict(id='subscription:'+str(index),label=sub['name']+' · '+sub['amount']+' / '+str(sub['period']),values=[0,1],unit_cost=sub['monthly'],unit_annual=sub['annual'],type='checkbox'))
    size=1
    for control in controls:size*=len(control['values'])
    if size>5000:raise ValueError('too_many_reduction_combinations_select_fewer_categories')
    states={}
    for choices in product(*(c['values'] for c in controls)):
        monthly=sum((D(str(n))*D(c['unit_cost']) for n,c in zip(choices,controls)),D(0))
        annual=sum((D(str(n))*D(c['unit_annual']) for n,c in zip(choices,controls)),D(0))
        states[','.join(map(str,choices))]=dict(monthly=str(monthly),annual=str(annual))
    return dict(controls=controls,states=states,notice='Potential savings ไม่ใช่เงินสด ค่าส่งที่ลดได้ไม่รวมค่าอาหารทดแทน รายปีสมมติทำได้ต่อเนื่อง 12 เดือน')


def potential_goal_draft(snapshot,goal_id,monthly):
    value=amount(monthly)
    goal=next((g for g in snapshot['goals'] if g['goal_id']==goal_id and g['status']=='ACTIVE'),None)
    if goal is None:raise ValueError('active_goal_required')
    return dict(goal_id=goal_id,status='HYPOTHETICAL_DRAFT',potential_monthly=str(value),
                saved_amount=goal['saved_amount'],cash_change='0',requires_confirmation=True,
                notice='ยังไม่เพิ่ม saved_amount หรือเงินพร้อมใช้ ต้องเกิดการประหยัดจริงและยืนยันการกันเงินก่อน')


def user_expense_analysis(items,current):
    """Confirmed monthly summaries, not manufactured transaction rows or defaults."""
    categories=[];subscriptions=[];controls=[];names=set()
    for item in items:
        if not isinstance(item.get('name'),str):raise ValueError('กรุณาระบุชื่อรายจ่ายเป็นข้อความ')
        name=item['name'].strip()
        if not name or len(name)>100 or name.casefold() in names:raise ValueError('ชื่อรายจ่ายต้องไม่ซ้ำและยาวไม่เกิน 100 ตัวอักษร')
        names.add(name.casefold());value=amount(item.get('amount'))
        if value<=0:raise ValueError('กรอกยอดรายจ่ายมากกว่า 0 ครับ')
        if item.get('kind')=='expense':
            if item.get('period')!='monthly':raise ValueError('ยอดรวมหมวดรายจ่ายต้องระบุเป็นรายเดือน')
            categories.append(dict(name=name,amount=str(value),count=None,source='user_summary'))
            controls.append(dict(id=item['id'],label='ทดลองลด '+name,values=list(range(0,101,10)),type='range',unit='percent',monthly=str(value),annual=str(value*12)))
        elif item.get('kind')=='subscription':
            period=item.get('period')
            if period not in ('monthly','annual'):raise ValueError('ยืนยันรอบเรียกเก็บบริการก่อนครับ')
            monthly=floor_money(value if period=='monthly' else value/12)
            annual=value*12 if period=='monthly' else value
            subscriptions.append(dict(name=name,amount=str(value),period=period,monthly=str(monthly),annual=str(annual),source='user_summary'))
            controls.append(dict(id=item['id'],label='ทดลองหยุด '+name,values=[0,1],type='checkbox',unit='subscription',monthly=str(monthly),annual=str(annual)))
        else:raise ValueError('ประเภทต้องเป็นหมวดรายจ่ายหรือบริการสมาชิก')
    if len(categories)>2 or len(subscriptions)>3:raise ValueError('จำลองได้ครั้งละ 2 หมวดรายจ่ายและ 3 บริการครับ ลบหรือเปลี่ยนรายการก่อน')
    largest=max((D(c['amount']) for c in categories),default=D(0))
    for item in categories:item['bar_percent']=str((D(item['amount'])/largest*100).quantize(D('.1'))) if largest else '0'
    states={}
    for choices in product(*(c['values'] for c in controls)):
        monthly=D(0);annual=D(0)
        for value,control in zip(choices,controls):
            fraction=D(value)/100 if control['unit']=='percent' else D(value)
            monthly+=floor_money(D(control['monthly'])*fraction);annual+=floor_money(D(control['annual'])*fraction)
        states[','.join(map(str,choices))]=dict(monthly=str(monthly),annual=str(annual))
    if not items:states={}
    return dict(source='user_summary' if items else 'none',status='SCENARIO' if items else 'INSUFFICIENT_DATA',items=deepcopy(items),
        analysis=dict(kind='leaks',categories=categories,subscriptions=subscriptions,duplicate_candidates=[],recurring_candidates=[],unusual_candidates=[],issues=[]),
        simulation=dict(controls=controls,states=states,notice='คำนวณเฉพาะยอดที่ผู้ใช้ระบุ ไม่มีการสมมติหมวดอื่น เงินที่อาจประหยัดได้ยังไม่ใช่เงินสด'),
        notice='ข้อมูลสรุปเพื่อจำลองเท่านั้น ไม่ใช่ธุรกรรม ไม่เพิ่มเงินพร้อมใช้หรือยอดออม')


def normalize_trip(raw,current):
    trip=deepcopy(raw)
    if not trip.get('destination') or not trip.get('departure'):raise ValueError('destination_and_departure_required')
    start=target_day(trip['travel_date'],current)
    if start<current:raise ValueError('travel_date_in_past')
    days=trip.get('days');nights=trip.get('nights');travelers=trip.get('travelers')
    if any(type(v) is not int for v in (days,nights,travelers)) or not 1<=days<=366 or not 0<=nights<=days or not 1<=travelers<=100:
        raise ValueError('invalid_trip_duration_or_travelers')
    categories=trip.get('costs',[])
    if not categories:raise ValueError('trip_costs_required')
    seen=set();costs=[]
    for item in categories:
        if not item.get('name') or item['name'] in seen:raise ValueError('distinct_cost_names_required')
        seen.add(item['name'])
        value=amount(item.get('amount'))
        if item.get('unit') not in ('group_total','per_person','per_person_day','group_night','per_person_night'):
            raise ValueError('cost_unit_required')
        factor={'group_total':1,'per_person':travelers,'per_person_day':travelers*days,'group_night':nights,'per_person_night':travelers*nights}[item['unit']]
        if item.get('certainty') not in ('estimated','verified') or not item.get('source'):
            raise ValueError('cost_provenance_required')
        costs.append(dict(item,total=str(value*factor)))
    if len(costs)>5:raise ValueError('group_trip_costs_into_at_most_five_categories')
    return dict(trip,travel_date=start.isoformat(),costs=costs)


def travel_report(shared,raw,current,totals=None):
    trip=normalize_trip(raw,current)
    values=[amount(x['total']) for x in trip['costs']] if totals is None else list(map(amount,totals))
    if len(values)!=len(trip['costs']):raise ValueError('cost_count_mismatch')
    total=sum(values,D(0));portfolio=shared['portfolio']
    available=D(portfolio['remaining_spending_budget']) if portfolio.get('remaining_spending_budget') is not None else None
    fit='INSUFFICIENT_DATA' if portfolio['status']=='INSUFFICIENT_DATA' else 'NOT_AFFORDABLE' if portfolio['status']=='NOT_FEASIBLE' else 'AFFORDABLE' if available is not None and total<=available else 'SAVE_FIRST'
    goal=None;plan=None
    if total>0:
        goal=dict(goal_id='travel-preview',goal_name=trip['destination'],goal_category='travel',target_amount=str(total),saved_amount='0',target_date=trip['travel_date'],funding_source='free_cash',status='DRAFT')
        from purchase_flow import relevant_forecast
        all_goals=shared['snapshot']['goals']+[goal]
        plan=plan_goals(all_goals,shared['profile'],shared['budget_options'],current,relevant_forecast(all_goals,shared['budget_options'],current,shared.get('forecast')),shared.get('coverage'))
    metric=next((g for g in (plan or {}).get('goals',[]) if g['goal_id']=='travel-preview'),{})
    widths=[str((v/total*100).quantize(D('.1'))) if total else '0' for v in values]
    return dict(kind='travel',trip=trip,total=str(total),cost_totals=list(map(str,values)),distribution=widths,
                financial_fit=fit,goal_status=(plan or {}).get('status','NOT_REQUIRED'),
                required_savings=str(max(D(0),total-available)) if available is not None else None,
                daily_saving=metric.get('daily_saving'),daily_spending=(plan or {}).get('daily_spending'),
                goal_draft=goal,price_type='VERIFIED' if all(x['certainty']=='verified' for x in trip['costs']) else 'ESTIMATED',
                notice='ต้นทุนรวมทั้งกลุ่ม ปรับ Slider เป็นประมาณการ ไม่ใช่ราคาจองจริง ไม่มีการค้น/โหลดภาพหรือจองทริป')


def travel_states(shared,raw,current):
    initial=travel_report(shared,raw,current);controls=[]
    for item in initial['trip']['costs']:
        base=amount(item['total'])
        values=sorted(set(str(floor_money(base*factor)) for factor in (D(0),D('.5'),D(1),D('1.5'),D(2))),key=D)
        controls.append(dict(label=item['name'],values=values,initial=values.index(str(floor_money(base)))))
    cache={};states={}
    for indexes in product(*(range(len(c['values'])) for c in controls)):
        values=[c['values'][i] for c,i in zip(controls,indexes)];total=sum(map(D,values),D(0))
        if total not in cache:cache[total]=travel_report(shared,raw,current,values)
        report=cache[total]
        # Widths depend on composition, while affordability depends on the total.
        widths=[str((D(v)/total*100).quantize(D('.1'))) if total else '0' for v in values]
        states[','.join(map(str,indexes))]=dict(total=str(total),distribution=widths,
                financial_fit=report['financial_fit'],goal_status=report['goal_status'],
                required_savings=report['required_savings'],daily_saving=report['daily_saving'],daily_spending=report['daily_spending'])
    return dict(initial=initial,controls=controls,states=states)
