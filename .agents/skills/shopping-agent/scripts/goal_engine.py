"""Pure goal/date/cash-flow calculations. No storage, network, or LLM."""
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from urllib.parse import urlsplit
from planning import budget

CATEGORIES = ('purchase', 'travel', 'general', 'education', 'future_expense')
ACTIVE = ('ACTIVE',)


def today_bangkok():
    # Bangkok has no DST. Fixed UTC+7 also works without Windows tzdata.
    return datetime.now(timezone(timedelta(hours=7))).date()


def amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('amount_required')
    try:n = Decimal(str(value))
    except InvalidOperation:raise ValueError('invalid_amount')
    if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
        raise ValueError('invalid_amount')
    return n


def target_day(value, current):
    if value in ('สิ้นเดือน', 'end_of_month'):
        return current.replace(day=monthrange(current.year, current.month)[1])
    if value in ('สิ้นปี', 'end_of_year'):
        return date(current.year, 12, 31)
    return date.fromisoformat(value)


def normalize_goal(raw, current):
    g = deepcopy(raw)
    for key in ('goal_name', 'goal_category', 'funding_source'):
        if not isinstance(g.get(key), str) or not g[key].strip() or len(g[key])>200:
            raise ValueError(key+'_required')
    if g['goal_category'] not in CATEGORIES:
        raise ValueError('invalid_goal_category')
    # Never silently select emergency/protected savings as a funding pool.
    if g['funding_source'] != 'free_cash':
        raise ValueError('funding_source_requires_confirmed_free_cash')
    g['target_amount'] = str(amount(g.get('target_amount')))
    if amount(g['target_amount']) <= 0:
        raise ValueError('positive_target_required')
    # Missing savings are unknown, not an implicit zero.
    g['saved_amount'] = str(amount(g.get('saved_amount')))
    g['target_date'] = target_day(g.get('target_date'), current).isoformat()
    if (date.fromisoformat(g['target_date'])-current).days > 3660:
        raise ValueError('target_horizon_exceeds_10_years')
    if g.get('image_url'):
        u = urlsplit(g['image_url'])
        if u.scheme != 'https' or not u.netloc or u.username or u.password:
            raise ValueError('invalid_image_url')
    if g.get('priority') is not None and g['priority'] not in ('low', 'normal', 'high'):
        raise ValueError('invalid_priority')
    if g.get('status', 'DRAFT') not in ('DRAFT', 'ACTIVE', 'PAUSED', 'DELETED'):
        raise ValueError('invalid_goal_status')
    g.setdefault('status', 'DRAFT')
    g.setdefault('goal_id', None)
    return g


def goal_metrics(raw, current, recorded_today=False):
    g = normalize_goal(raw, current)
    target, saved = amount(g['target_amount']), amount(g['saved_amount'])
    gap = max(Decimal(0), target-saved)
    days = (date.fromisoformat(g['target_date'])-current).days
    count = max(0, days+1)
    available_days=max(0,count-int(recorded_today))
    daily = (gap/available_days).quantize(Decimal('.01'), rounding=ROUND_CEILING) if available_days else None
    state = g['status'] if g['status'] in ('PAUSED','DELETED') else 'FUNDED' if gap == 0 else 'OVERDUE' if days < 0 else 'NO_SAVING_DAYS' if not available_days else g['status']
    return dict(g, plan_status=g['status'], current_date=current.isoformat(), days_remaining=days,
                saving_days_including_today=count, remaining_target_amount=str(gap),
                available_saving_days=available_days,recorded_today=recorded_today,
                daily_saving=str(daily) if daily is not None else None,
                progress=str((min(saved,target)/target*100).quantize(Decimal('.01'))),
                status=state)


def demo_progress_states(g, current):
    """Transient future checkmarks; no store mutation or actual savings."""
    future=sum(1 for row in calendar_rows(g,current) if row['state']=='upcoming')
    daily=amount(g['daily_saving']) if g.get('daily_saving') is not None else Decimal(0)
    target=amount(g['target_amount']);saved=amount(g['saved_amount'])
    return [dict(saved_amount=str(min(target,saved+daily*n)),progress=str((min(target,saved+daily*n)/target*100).quantize(Decimal('.01')))) for n in range(future+1)]


def calendar_rows(g, current, entries=()):
    """Calendar is generated only for an explicitly activated plan."""
    if g.get('plan_status',g.get('status'))=='DELETED' or not g.get('activated_on'):
        return []
    start = date.fromisoformat(g['activated_on'])
    end = date.fromisoformat(g['target_date'])
    if end < start or (end-start).days > 3660:
        return []
    by_day = {e['date']:e['amount'] for e in entries}
    rows=[]
    first=start.replace(day=1)
    last=end.replace(day=monthrange(end.year,end.month)[1])
    for offset in range((last-first).days+1):
        day=first+timedelta(days=offset)
        rows.append(dict(date=day.isoformat(), weekday=day.weekday(),saved_amount=by_day.get(day.isoformat()),
                         target=day==end, state='inactive' if day<start or day>end else 'recorded' if day.isoformat() in by_day else 'past' if day<current else 'today' if day==current else 'upcoming'))
    return rows


def plan_goals(goals, profile, options, current, forecast=None, coverage=None, recorded_today=()):
    """Allocate all active goals against existing cycle-aware budget.

    coverage maps each goal to its saved money already excluded in profile.reserved.
    Uncovered saved balances are protected exactly once here. Future forecast events
    affect free cash only AFTER the current protected cycle, with complete outflows.
    """
    all_metrics=[goal_metrics(g,current,g.get('goal_id') in recorded_today) for g in goals]
    if len(all_metrics)>100:raise ValueError('too_many_goals_for_mvp')
    metrics=[g for g in all_metrics if g['status']!='DELETED']
    ids=[g['goal_id'] for g in all_metrics]
    if len(ids)!=len(set(ids)):
        raise ValueError('duplicate_goal_id')
    b=budget(profile,options,current)
    result=dict(current_date=current.isoformat(), goals=metrics, budget=b,
                status='INSUFFICIENT_DATA', issues=[], remaining_spending_budget=None,
                daily_spending=None, calendar=[], forecast=[])
    if b['status']=='INSUFFICIENT_DATA':
        result['issues']=b['issues'];return result
    coverage=coverage or {}
    if set(coverage)-set(ids):
        raise ValueError('unknown_coverage_goal')
    reserved=amount(profile['reserved'])
    covered=sum((amount(x) for x in coverage.values()),Decimal(0))
    if covered>reserved:
        raise ValueError('goal_coverage_exceeds_reserved')
    saved=sum((amount(g['saved_amount']) for g in all_metrics),Decimal(0))
    for g in all_metrics:
        if amount(coverage.get(g['goal_id'],'0'))>amount(g['saved_amount']):
            raise ValueError('goal_coverage_exceeds_saved')
    available=Decimal(b['recommended_budget'])-(saved-covered)
    participating=[g for g in metrics if g.get('status') in ('ACTIVE','DRAFT','OVERDUE','NO_SAVING_DAYS')]
    end=max([date.fromisoformat(b['cycle_end'])]+[date.fromisoformat(g['target_date']) for g in participating])
    events={}
    cycle_end=date.fromisoformat(b['cycle_end'])
    if end>cycle_end:
        if not forecast or forecast.get('complete') is not True or date.fromisoformat(forecast['through'])<end:
            result['issues']=['complete_future_cashflow_required'];return result
        # The whole current cycle (including its receipt day) is already protected.
        # Explicit future events must follow it; no double subtraction or imaginary income.
        for event in forecast.get('events',[]):
            day=date.fromisoformat(event['date'])
            if not cycle_end<day<=end:
                raise ValueError('forecast_event_outside_future_window')
            if event.get('confirmed') is not True:
                result['issues']=['unconfirmed_future_cashflow'];return result
            net=amount(event['income'])-amount(event['outflow'])
            events[day]=events.get(day,Decimal(0))+net
    elif forecast and forecast.get('events'):
        raise ValueError('unnecessary_forecast_events')
    balance=available;allocated=Decimal(0);shortfall=None;timeline=[]
    for offset in range((end-current).days+1):
        day=current+timedelta(days=offset)
        balance+=events.get(day,Decimal(0))
        due=Decimal(0)
        for g in participating:
            if day==current and g['recorded_today']:continue
            if day<=date.fromisoformat(g['target_date']) and g['daily_saving'] is not None:
                need=amount(g['remaining_target_amount'])
                prior=min(need,amount(g['daily_saving'])*max(0,offset-int(g['recorded_today'])))
                due+=min(amount(g['daily_saving']),max(Decimal(0),need-prior))
        balance-=due;allocated+=due
        if balance<0 and shortfall is None:shortfall=day.isoformat()
        timeline.append(dict(date=day.isoformat(), goal_allocation=str(due), remaining_free_cash=str(balance)))
    # Current-cycle spending ceiling reserves contributions needed before next income.
    current_cost=sum((Decimal(row['goal_allocation']) for row in timeline if date.fromisoformat(row['date'])<=cycle_end),Decimal(0))
    remaining=available-current_cost
    spending_days=(cycle_end-current).days+1
    daily=(max(Decimal(0),remaining)/spending_days).quantize(Decimal('.01'),rounding='ROUND_DOWN')
    overdue=any(g['status'] in ('OVERDUE','NO_SAVING_DAYS') for g in participating)
    result.update(status='NOT_FEASIBLE' if shortfall or overdue else 'FEASIBLE',
                  issues=['deadline_passed'] if overdue else [], first_shortfall=shortfall,
                  remaining_spending_budget=str(remaining), daily_spending=str(daily),
                  total_goal_allocation=str(allocated), forecast=timeline)
    return result
