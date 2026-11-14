"""Render the explicitly synthetic monthly example; no provider reads."""
from pathlib import Path
from datetime import date
from decimal import Decimal
from planning import budget
from simulator import currency


def payload():
    day = date(2026, 11, 12)
    profile = dict(income='30000', essential='14500', debt='0', saving='3000',
                   cash='90000', emergency='60000', reserved='3000', future_extra=[],
                   income_kind='stable', as_of=day.isoformat(), complete=True, future_complete=True)
    options = dict(cycle_complete=True, next_income_date='2026-11-30', minimum_remaining='1500',
                   obligations=[dict(id='demo-living', due='2026-11-29', amount='14500',
                                     certainty='confirmed', state='unpaid', covered_by='none')])
    result = budget(profile, options, day)
    values = dict(SPENDABLE=currency(result['recommended_budget']), INCOME=currency(profile['income']),
                  ESSENTIAL=currency(profile['essential']), SAVING=currency(profile['saving']),
                  BUFFER=currency(options['minimum_remaining']), PAID=currency(0),
                  SURPLUS=currency(result['monthly_surplus']), EMERGENCY=currency(profile['emergency']),
                  CASH=currency(profile['cash']), DAYS=str((date(2026,11,30)-day).days))
    allocations = dict(ESSENTIAL=profile['essential'], SAVING=profile['saving'],
                       BUFFER=options['minimum_remaining'], SPENDABLE=result['recommended_budget'])
    assert sum(map(Decimal, allocations.values())) == Decimal(profile['income'])
    for key, amount in allocations.items():
        values[key+'_PCT'] = str((Decimal(amount)/Decimal(profile['income'])*100).quantize(Decimal('.1')))
    values['ALLOCATION_LABEL'] = 'ค่าใช้ชีวิต '+values['ESSENTIAL_PCT']+'% ออมและลงทุน '+values['SAVING_PCT']+'% เงินเผื่อ '+values['BUFFER_PCT']+'% ใช้เพิ่มได้ '+values['SPENDABLE_PCT']+'%'
    return profile, options, result, values


def render():
    raw = (Path(__file__).resolve().parents[1]/'assets/monthly-inline.html').read_text(encoding='utf-8')
    for key, value in payload()[3].items():
        raw = raw.replace('__'+key+'__', value)
    return raw
