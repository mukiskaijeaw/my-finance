"""Read-only financial companion state. All features protect the same goal store."""
import csv
from pathlib import Path
from goal_engine import plan_goals
from engine import SCHEMA


def build_shared(profile, options, snapshot, current, forecast=None, coverage=None):
    from purchase_flow import relevant_forecast
    recorded={e['goal_id'] for e in snapshot.get('entries',[]) if e['date']==current.isoformat()}
    report=plan_goals(snapshot.get('goals',[]),profile,options,current,relevant_forecast(snapshot.get('goals',[]),options,current,forecast),coverage,recorded)
    return dict(profile=profile,budget_options=options,portfolio=report,
                revision=snapshot.get('revision',0),snapshot=snapshot,
                forecast=forecast,coverage=coverage)


def load_transactions(finance_dir, month, history_months=1):
    """Read only requested month range; never infer balances or contact a network."""
    if type(history_months) is not int or not 1<=history_months<=3:raise ValueError('history_limit_three_months')
    year,number=map(int,month.split('-'));ordinal=year*12+number-1
    months={f'{(ordinal-i)//12:04d}-{(ordinal-i)%12+1:02d}' for i in range(history_months)}
    path=Path(finance_dir).resolve()/'database.csv'
    rows=[]
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames not in (SCHEMA,SCHEMA[:11]):raise ValueError('schema_mismatch')
        for row in reader:
            if row.get('year_month') in months:rows.append(row)
    return rows
