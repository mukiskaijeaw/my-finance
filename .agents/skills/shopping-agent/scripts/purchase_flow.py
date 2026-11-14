"""Pure product-session transitions and existing financial/goal orchestration.

No search, network, persistence, purchases or LLM calls. Session is caller-owned.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from urllib.parse import urlsplit
from engine import effective_price, confidence
from planning import fit
from decision_policy import recommend
from goal_engine import plan_goals, target_day, goal_metrics, amount


def https(value):
    if not value:return None
    u=urlsplit(value)
    if u.scheme!='https' or not u.netloc or u.username or u.password:
        raise ValueError('verified_https_product_source_required')
    return value


def new_session(intent=None):
    intent=deepcopy(intent or {})
    if intent.get('budget') not in (None,''):amount(intent['budget'])
    return dict(version=1,stage='SEARCH_REQUIRED' if intent.get('product') or intent.get('image_attached') else 'INTENT',
                intent=intent,candidates=[],selected_product=None,selection_confirmed=False)


def candidates(session, listings, target, current, *, exact=False):
    state=deepcopy(session);found=[];seen=set()
    for listing in listings:
        if not isinstance(listing.get('name'),str) or not listing['name'].strip():
            raise ValueError('sourced_product_name_required')
        https(listing.get('url'))
        if not listing.get('url'):raise ValueError('product_url_required')
        evidence=listing.get('evidence',{})
        match=confidence(target,evidence)
        # Do not let an explicitly conflicting candidate be the exact-match choice.
        if exact and (match['tier']!='HIGH' or match['conflicts']):continue
        identity=tuple(str(evidence.get(k,{}).get('value','')) for k in ('brand','model','sku','color','size'))
        identity=identity if any(identity) else (listing['url'],)
        if identity in seen:continue
        seen.add(identity)
        quote=effective_price(listing,current)
        if listing.get('image_url') and (listing.get('image_verified') is not True or not https(listing.get('image_source'))):
            raise ValueError('verified_product_image_provenance_required')
        ident=sha256((listing['url']+repr(identity)).encode()).hexdigest()[:20]
        found.append(dict(id=ident,name=listing['name'],source=listing['url'],
                          model=evidence.get('model',{}).get('value'),
                          variant=listing.get('variant') or evidence.get('color',{}).get('value'),
                          details=listing.get('details'),image_url=https(listing.get('image_url')),
                          quote=quote,listing=deepcopy(listing),match=match))
        if len(found)==(1 if exact else 4):break
    state.update(stage='CONFIRM' if found else 'CLARIFY_PRODUCT',candidates=found,
                 selected_product=None,selection_confirmed=False)
    return state


def select(session, product_id, confirmed):
    if confirmed is not True:raise ValueError('user_product_confirmation_required')
    choice=next((p for p in session.get('candidates',[]) if p['id']==product_id),None)
    if choice is None:raise ValueError('candidate_not_in_session')
    state=deepcopy(session)
    state.update(stage='DECISION',selected_product=deepcopy(choice),selection_confirmed=True)
    return state


def reject(session, search_again=False):
    state=deepcopy(session)
    state.update(stage='SEARCH_REQUIRED' if search_again else 'CLARIFY_PRODUCT',
                 candidates=[],selected_product=None,selection_confirmed=False)
    return state


def relevant_forecast(goals, options, current, forecast):
    if not forecast or not options.get('next_income_date'):return forecast
    cycle=date.fromisoformat(options['next_income_date'])
    end=max([cycle]+[target_day(g['target_date'],current) for g in goals if g.get('status') not in ('PAUSED','DELETED')])
    if end<=cycle:return None
    return dict(forecast,events=[e for e in forecast.get('events',[]) if cycle<date.fromisoformat(e['date'])<=end])


def evaluate_purchase(session, request, saved_goals, entries, current):
    """Selected fresh quote -> portfolio protection -> existing fit/policy + goal preview."""
    if session.get('selection_confirmed') is not True or not session.get('selected_product'):
        raise ValueError('confirm_product_before_financial_assessment')
    product=session['selected_product'];quote=effective_price(product['listing'],current)
    target=target_day(request.get('target_date') or 'สิ้นเดือน',current)
    if target<current:raise ValueError('purchase_target_is_in_the_past')
    base=dict(stage='DECISION',product=product,current_date=current.isoformat(),
              target_date=target.isoformat(),quote=quote,financial=None,goal_plan=None,
              available_spending=None,remaining_after_purchase=None,existing_goal_commitments=None,
              suggested_purchase_date=None,daily_saving=None,daily_spending=None)
    profile=request.get('profile',{});options=deepcopy(request.get('budget',{}))
    if session.get('intent',{}).get('budget') not in (None,''):
        options.setdefault('user_budget',session['intent']['budget'])
    recorded={e['goal_id'] for e in entries if e['date']==current.isoformat()}
    portfolio=plan_goals(saved_goals,profile,options,current,relevant_forecast(saved_goals,options,current,request.get('forecast')),request.get('coverage'),recorded)
    base['portfolio']=portfolio
    if portfolio['status']=='FEASIBLE':
        available=Decimal(portfolio['remaining_spending_budget'])
        base.update(available_spending=str(available),
                    existing_goal_commitments=str(Decimal(portfolio['budget']['recommended_budget'])-available))
    if portfolio['status']=='INSUFFICIENT_DATA' or quote['effective'] is None:
        financial=dict(status='INSUFFICIENT_DATA',issues=portfolio.get('issues',[])+quote['issues'])
    elif portfolio['status']=='NOT_FEASIBLE':
        financial=dict(status='NOT_AFFORDABLE',issues=['existing_goals_not_feasible'])
    else:
        available=Decimal(portfolio['remaining_spending_budget'])
        # Existing goal savings and cycle contributions were protected by plan_goals.
        # Add ONLY the delta beyond the existing budget's protection before fit.
        extra=max(Decimal(0),Decimal(portfolio['budget']['affordable_budget'])-Decimal(portfolio['budget']['minimum_remaining'])-available)
        adjusted=deepcopy(profile)
        adjusted['reserved']=str(amount(profile['reserved'])+extra)
        financial=fit(adjusted,quote['effective'],options,current)
        if extra>0 and financial.get('status')=='SAVE_FIRST':financial['months']=None
        commitments=Decimal(portfolio['budget']['recommended_budget'])-available
        base.update(available_spending=str(available),remaining_after_purchase=financial.get('remaining_after_purchase'),
                    existing_goal_commitments=str(commitments))
    context=deepcopy(request.get('context',{}))
    listing=product['listing']
    # A confirmed model alone does not prove selected size is in stock.
    if listing.get('stock_verified') is not True or listing.get('stock')!='available':
        context['offer_ready']={'value':False,'source':'selected listing stock not confirmed available'}
    alternatives=[]
    for candidate in request.get('alternatives',[]):
        price=candidate.get('price') if candidate.get('price_confirmed') is True and candidate.get('price_source') else None
        checked=fit(adjusted,price,options,current) if portfolio['status']=='FEASIBLE' and quote['effective'] is not None else {'status':'INSUFFICIENT_DATA'}
        alternatives.append(dict(candidate,financial=checked))
    base.update(financial=financial,decision=recommend(financial,context,alternatives))
    if financial.get('status')=='AFFORDABLE':base['suggested_purchase_date']=current.isoformat()
    if quote['effective'] is not None and Decimal(quote['effective'])>0:
        # Zero here belongs to an UNSAVED new-plan scenario, never an inferred real balance.
        saved=request.get('purchase_saved_amount','0')
        linked=[g for g in saved_goals if g.get('product_ref')==product['id'] and g.get('status')!='DELETED']
        goal=dict(goal_id='purchase-preview',goal_name=product['name'],goal_category='purchase',
                  target_amount=quote['effective'],saved_amount=saved,target_date=target.isoformat(),
                  image_url=product.get('image_url'),funding_source='free_cash',status='DRAFT',
                  product_ref=product['id'],product_url=product['source'])
        if linked:
            goal=dict(linked[0],target_amount=quote['effective'],target_date=target.isoformat())
        proposed=[g for g in saved_goals if g.get('goal_id')!=goal['goal_id']]+[goal]
        plan=plan_goals(proposed,profile,options,current,relevant_forecast(proposed,options,current,request.get('forecast')),request.get('coverage'),recorded)
        metric=next(g for g in plan['goals'] if g['goal_id']==goal['goal_id'])
        base.update(goal_plan=plan,goal_draft=goal,daily_saving=metric['daily_saving'],
                    savings_progress=metric['progress'],
                    goal_status=plan['status'],goal_issues=plan.get('issues',[]),
                    daily_spending=plan.get('daily_spending'),new_plan_zero_assumption=not linked and 'purchase_saved_amount' not in request,
                    linked_goal_id=goal['goal_id'] if linked else None)
        if not base['suggested_purchase_date'] and plan['status']=='FEASIBLE':
            base['suggested_purchase_date']=target.isoformat()
    elif quote['effective'] is not None:
        base.update(goal_status='NOT_REQUIRED',daily_saving='0',new_plan_zero_assumption=False)
    return base


def price_states(report, current):
    """Hypothetical all-in prices, never a replacement for the sourced quote."""
    if report.get('available_spending') is None:return None
    available=Decimal(report['available_spending'])
    actual=report['quote'].get('effective') or report['quote'].get('estimate')
    if actual is None:return None
    actual=Decimal(actual);ceiling=max(actual*2,max(Decimal(0),available)*Decimal('1.25'))
    from calendar import monthrange
    from decimal import ROUND_DOWN
    days=monthrange(current.year,current.month)[1]-current.day+1
    values=sorted(set([(ceiling*i/100).quantize(Decimal('.01')) for i in range(101)]+[actual]))
    states=[]
    for price in values:
        remaining=available-price
        states.append(dict(price=str(price),remaining=str(remaining),
            daily_spending=str((max(Decimal(0),remaining)/days).quantize(Decimal('.01'),rounding=ROUND_DOWN)),
            used_percent=str(min(Decimal(100),price/available*100).quantize(Decimal('.1'))) if available>0 else '100',
            status='WAIT_AND_SAVE' if remaining<0 else 'BUY_WITH_CAUTION' if report['decision']['recommendation']=='BUY_WITH_CAUTION' else 'WITHIN_AVAILABLE_BUDGET'))
    return dict(initial=values.index(actual),states=states,notice='จำลองยอดจ่ายรวม ไม่ใช่ข้อเสนอร้านค้า และไม่เปลี่ยนยอดแผนที่ยืนยัน')


def run_purchase(payload, store, current, consent=False):
    action=payload.get('action','entry');session=payload.get('session') or new_session(payload.get('intent'))
    if action=='entry':return session
    if action=='identify':return new_session(payload.get('intent'))
    if action=='candidates':
        result=candidates(session,payload['listings'],payload.get('target',{}),current,exact=payload.get('exact') is True)
        result['identification']=confidence(payload.get('target',{}),payload.get('identification_evidence',{}))
        return result
    if action=='select':return select(session,payload['product_id'],payload.get('confirmed'))
    if action in ('reject','search_again'):return reject(session,action=='search_again')
    if action=='change_product':return new_session()
    if action=='cheaper':return dict(session,stage='SEARCH_REQUIRED',search_reason='cheaper_same_selected_product')
    if action=='skip':
        return dict(session,stage='SKIPPED',recommendation='SKIP_PURCHASE')
    if action=='select_and_evaluate':
        session=select(session,payload['product_id'],payload.get('confirmed'))
    if action in ('evaluate','change_date','buy_today','goal_preview','select_and_evaluate','start_goal','confirm_goal'):
        request=deepcopy(payload)
        if action=='buy_today':request['target_date']=current.isoformat()
        snapshot=store.read()
        result=evaluate_purchase(session,request,snapshot['goals'],snapshot['entries'],current)
        review=sha256(json.dumps(dict(product=session.get('selected_product'),goal=result.get('goal_draft'),
                        profile=payload.get('profile'),budget=payload.get('budget'),forecast=payload.get('forecast'),
                        coverage=payload.get('coverage'),revision=snapshot['revision'],current=current.isoformat()),
                        ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        result['review_token']=review
        result['reviewed_purchase_saved_amount']=payload.get('purchase_saved_amount')
        if action=='confirm_goal':
            if consent is not True:raise ValueError('explicit_goal_confirmation_required')
            if 'purchase_saved_amount' not in payload or payload.get('funding_source_confirmed') is not True:
                raise ValueError('confirm_actual_saved_amount_and_free_cash_source')
            if payload.get('review_token')!=review:
                raise ValueError('review_updated_goal_and_budget_before_confirmation')
            if result.get('linked_goal_id'):raise ValueError('use_existing_linked_goal_no_duplicate_creation')
            if not result.get('goal_plan') or result['goal_plan']['status']!='FEASIBLE':
                raise ValueError('goal_plan_not_feasible_or_incomplete')
            from goal_planner import run as run_goal
            goal=dict(result['goal_draft'],activate_on_create=True)
            # Existing GoalStore validates again inside its revision-controlled transaction.
            forecast=relevant_forecast(snapshot['goals']+[goal],payload['budget'],current,payload.get('forecast'))
            saved=run_goal(dict(action='create',goal=goal,profile=payload['profile'],budget=payload['budget'],
                               forecast=forecast,coverage=payload.get('coverage'),
                               expected_revision=payload.get('expected_revision'),operation_id=payload.get('operation_id')),
                          store,current,consent=True)
            view=run_goal(dict(action='view',profile=payload['profile'],budget=payload['budget'],
                              forecast=forecast,coverage=payload.get('coverage'),goal_id=saved['goal']['goal_id']),store,current)
            return dict(session,goal_saved=saved,goal_view=view,stage='GOAL_ACTIVE')
        if action in ('start_goal','goal_preview'):result['goal_confirmation_required']=True
        reports={}
        if payload.get('precompute_dates',True) and action not in ('start_goal','buy_today'):
            end=target_day('สิ้นเดือน',current)
            if payload.get('forecast',{}).get('complete') is True:
                end=min(date.fromisoformat(payload['forecast']['through']),current+timedelta(days=93))
            for offset in range(max(0,(end-current).days)+1):
                day=current+timedelta(days=offset)
                reports[day.isoformat()]=evaluate_purchase(session,dict(request,target_date=day.isoformat()),snapshot['goals'],snapshot['entries'],current)
        return dict(session,report=result,price_simulation=price_states(result,current),date_reports=reports,store_revision=snapshot['revision'])
    raise ValueError('unknown_purchase_action')
