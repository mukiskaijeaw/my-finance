"""Local, deterministic calculations. All monetary outputs are decimal strings."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

SCHEMA = 'transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag,model,token_input,token_output'.split(',')
FIELDS = ('income', 'essential', 'debt', 'saving', 'cash', 'emergency', 'reserved')

def money(value):
    if isinstance(value, bool) or value is None or str(value).strip() == '':
        raise ValueError('missing amount')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('invalid amount')
    if not n.is_finite() or n < 0 or n > Decimal('1000000000000000') or n.as_tuple().exponent < -2:
        raise ValueError('amount must be nonnegative, finite, with at most two decimals')
    return n

def fresh(value, today, days):
    try:
        age = (today - date.fromisoformat(value)).days
        return 0 <= age <= days
    except (TypeError, ValueError):
        return False

def read_ledger(path, today=None):
    today = today or date.today()
    result = {'issues': [], 'monthly': {}, 'cash_inferred': False}
    try:
        with open(path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames not in (SCHEMA, SCHEMA[:11]):
                return {**result, 'issues': ['schema_mismatch']}
            result['schema_columns'] = len(reader.fieldnames)
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error):
        return {**result, 'issues': ['ledger_unavailable']}
    ids, dates = set(), []
    for row in rows:
        try:
            d = date.fromisoformat(row['date'])
            amount = money(row['amount_thb'])
            if None in row or None in row.values() or row['transaction_id'] in ids or not row['transaction_id']:
                raise ValueError()
            if d > today or row['year_month'] != d.strftime('%Y-%m'):
                raise ValueError()
            kind = row['transaction_type']
            if kind not in ('income', 'expense', 'transfer', 'investment'):
                raise ValueError()
            if kind == 'investment' and row['action'] not in ('Buy', 'Sell'):
                raise ValueError()
            ids.add(row['transaction_id'])
            dates.append(d)
            if row['data_quality_flag']:
                result['issues'].append('transaction_needs_review')
            month = result['monthly'].setdefault(row['year_month'], {'income': Decimal(0), 'expense': Decimal(0)})
            if kind in month:
                month[kind] += amount
        except (ValueError, TypeError):
            result['issues'].append('invalid_or_duplicate_transaction')
    if not dates:
        result['issues'].append('no_valid_transactions')
    elif (today - max(dates)).days > 45:
        result['issues'].append('ledger_outdated')
    result['monthly'] = {k: {a: str(b) for a, b in v.items()} for k, v in result['monthly'].items()}
    result['issues'] = sorted(set(result['issues']))
    result['note'] = 'Recorded totals only; not a complete budget or account balance.'
    return result

def effective_price(listing, today):
    issues = []
    try:
        base = money(listing.get('price'))
    except ValueError:
        return {'effective': None, 'estimate': None, 'issues': ['price_missing_or_invalid']}
    if listing.get('verified') is not True or not fresh(listing.get('checked'), today, 7) or not str(listing.get('url', '')).startswith('https://'):
        issues.append('price_evidence_unverified_or_outdated')
    try:
        shipping = money(listing.get('shipping'))
        if listing.get('shipping_verified') is not True:
            issues.append('shipping_unverified')
    except ValueError:
        shipping = None
        issues.append('shipping_unknown')
    discount = Decimal(0)
    if listing.get('discount') in (None, ''):
        issues.append('discount_unknown')
    elif listing.get('discount') not in ('0', 0):
        try:
            discount = money(listing['discount'])
        except ValueError:
            issues.append('discount_invalid')
        if listing.get('discount_verified') is not True or listing.get('eligible') is not True:
            issues.append('discount_unverified_or_ineligible')
    # Never subtract an ineligible/unverified coupon even from the estimate.
    applied_discount = discount if listing.get('discount_verified') is True and listing.get('eligible') is True else Decimal(0)
    estimate = base + (shipping if shipping is not None else Decimal(0)) - applied_discount
    if estimate < 0:
        issues.append('discount_exceeds_total')
    return {'effective': str(estimate) if not issues else None, 'estimate': str(estimate) if estimate >= 0 else None, 'issues': issues}

def confidence(target, evidence):
    """Evidence completeness tiers, never probabilities. Values require source references."""
    if not isinstance(target, dict) or not isinstance(evidence, dict):
        raise ValueError('target and evidence must be objects')
    matched, missing, conflicts = [], [], []
    for key, expected in target.items():
        if key not in ('brand', 'model', 'sku', 'color', 'size', 'features') or not expected:
            continue
        item = evidence.get(key, {})
        if not isinstance(item, dict):
            raise ValueError('evidence attributes require value and source')
        actual = item.get('value')
        if not actual or not str(item.get('source', '')).strip():
            missing.append(key)
        elif str(actual).strip().casefold() == str(expected).strip().casefold():
            matched.append(key)
        else:
            conflicts.append(key)
    tier = 'LOW'
    if not conflicts and ('model' in matched or 'sku' in matched):
        tier = 'HIGH' if not missing else 'MEDIUM'
    elif matched and not conflicts:
        tier = 'MEDIUM'
    return {'tier': tier, 'matched': matched, 'missing': missing, 'conflicts': conflicts, 'meaning': 'evidence completeness, not probability'}

def financial_fit(profile, price, today):
    issues, p = [], {}
    for key in FIELDS:
        try:
            p[key] = money(profile.get(key))
        except ValueError:
            issues.append(key + '_missing_or_invalid')
    if not fresh(profile.get('as_of'), today, 30):
        issues.append('profile_outdated_or_undated')
    if profile.get('complete') is not True:
        issues.append('confirm_budget_complete')
    if profile.get('future_complete') is not True:
        issues.append('confirm_future_obligations')
    if profile.get('income_kind') not in ('stable', 'variable'):
        issues.append('income_kind_missing')
    if profile.get('income_kind') == 'variable':
        try:
            history = [money(x) for x in profile.get('income_history', [])]
            if len(history) < 3:
                raise ValueError()
            p['income'] = min(p.get('income', min(history)), min(history))
        except (TypeError, ValueError):
            issues.append('need_three_complete_income_months')
    try:
        cost = money(price)
    except ValueError:
        issues.append('verified_effective_price_required')
    if issues:
        return {'status': 'INSUFFICIENT_DATA', 'issues': issues, 'months': None}
    if profile.get('earmarked') not in (None, ''):
        try:
            p['earmarked'] = money(profile['earmarked'])
        except ValueError:
            return {'status': 'INSUFFICIENT_DATA', 'issues': ['earmarked_invalid'], 'months': None}
        if p['earmarked'] > p['cash']:
            return {'status': 'INSUFFICIENT_DATA', 'issues': ['earmarked_exceeds_total_cash'], 'months': None}
    if p['emergency'] + p['reserved'] > p['cash']:
        return {'status': 'NOT_AFFORDABLE', 'issues': ['protected_cash_not_covered'], 'months': None}
    surplus = p['income'] - p['essential'] - p['debt'] - p['saving']
    available = p['cash'] - p['emergency'] - p['reserved']
    # reserved covers current obligations; future_extra contains ONLY additional future costs.
    try:
        future = profile.get('future_extra')
        if not isinstance(future, list):
            raise ValueError()
        extras = {}
        for item in future:
            month = item['month']
            if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 600:
                raise ValueError()
            extras[month] = extras.get(month, Decimal(0)) + money(item['amount'])
    except (ValueError, KeyError, TypeError):
        return {'status': 'INSUFFICIENT_DATA', 'issues': ['invalid_future_obligation'], 'months': None}
    available -= sum(extras.values(), Decimal(0))
    if available < 0:
        return {'status': 'NOT_AFFORDABLE', 'issues': ['future_obligations_not_covered'], 'months': None}
    allocated = min(available, p.get('earmarked', available))
    gap = max(Decimal(0), cost - allocated)
    funded = min(cost, allocated)
    progress_percent = (funded / cost * 100).quantize(Decimal('.01'), rounding=ROUND_FLOOR) if cost else Decimal(100)
    progress = {'allocated': str(allocated), 'funded': str(funded), 'goal': str(cost), 'remaining': str(gap),
                'percent': str(progress_percent), 'filled_segments': int(progress_percent // 10), 'total_segments': 10}
    months = None
    if surplus >= 0 and cost <= available:
        status, months = 'AFFORDABLE', 0
    elif surplus <= 0:
        status = 'NOT_AFFORDABLE'
    else:
        status = 'SAVE_FIRST'
        # Include every declared future extra conservatively before estimating the date.
        months = int((gap / surplus).to_integral_value(rounding=ROUND_CEILING))
    return {'status': status, 'issues': [], 'monthly_surplus': str(surplus), 'available': str(available),
            'remaining_after_purchase': str(available - cost), 'cash_after_purchase': str(p['cash'] - cost),
            'spending_percent': str((cost / available * 100).quantize(Decimal('.01'))) if available else None,
            'months': months, 'savings_progress': progress,
            'goal_impact': 'protected' if status == 'AFFORDABLE' else 'wait_to_protect_goals',
            'assumptions': ['Cash includes emergency, reserved and earmarked funds; these are not added again.',
                'Essential, debt and saving are non-overlapping monthly amounts.',
                'Reserved covers unpaid current obligations once; future_extra excludes those and monthly obligations.',
                'Variable income uses minimum of at least three confirmed complete months.',
                'All declared future extra expenses are reserved now, even if far away: conservative, not a due-date simulation.',
                'Without an explicit earmarked amount, all unprotected cash is available for the savings plan.',
                'Projected surplus stays unchanged; prices and income may change.']}

def when_can_afford(profile, price, today):
    result = financial_fit(profile, price, today)
    return {key: result.get(key) for key in ('status', 'months', 'monthly_surplus', 'available', 'issues', 'assumptions')}

def compare_financial_impact(profile, prices, today):
    results = [financial_fit(profile, price, today) for price in prices]
    valid = []
    for price in prices:
        try:
            valid.append(money(price))
        except ValueError:
            pass
    for price, result in zip(prices, results):
        try:
            result['difference_from_lowest_verified'] = str(money(price) - min(valid))
        except (ValueError, TypeError):
            result['difference_from_lowest_verified'] = None
    return results

def evaluate(payload, today):
    if not isinstance(payload, dict) or not isinstance(payload.get('profile', {}), dict):
        raise ValueError('payload and profile must be objects')
    listings = payload.get('listings', [])
    if not isinstance(listings, list) or len(listings) > 6:
        raise ValueError('provide at most six listings')
    results = []
    for listing in listings:
        if not isinstance(listing, dict):
            raise ValueError('listing must be an object')
        price = effective_price(listing, today)
        results.append({'name': str(listing.get('name', '')), 'price': price,
            'identification': confidence(payload.get('target', {}), payload.get('identification_evidence', {})),
            'listing_match': confidence(payload.get('target', {}), listing.get('evidence', {})),
            'financial': financial_fit(payload.get('profile', {}), price['effective'], today)})
    verified = [money(r['price']['effective']) for r in results if r['price']['effective'] is not None]
    for r in results:
        r['difference_from_lowest_verified'] = str(money(r['price']['effective']) - min(verified)) if verified and r['price']['effective'] is not None else None
    return {'results': results, 'cheapest_claim_supported': bool(results) and all(r['price']['effective'] is not None and r['listing_match']['tier'] == 'HIGH' and listing.get('stock') == 'available' and listing.get('stock_verified') is True for r, listing in zip(results, listings)),
            'recommendation': 'ตรวจรุ่นและหลักฐานร้านค้า แล้วพิจารณาสถานะการเงิน คุณภาพ และการใช้งานร่วมกัน',
            'monitoring': 'ไม่มี background monitoring; ตรวจราคาและข้อมูลการเงินใหม่เมื่อกลับมาถามในแชท'}
