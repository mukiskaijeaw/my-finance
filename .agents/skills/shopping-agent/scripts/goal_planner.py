"""Goal workflow adapter: explicit input -> pure engine -> consent-only storage."""
import argparse
import json
import sys
from pathlib import Path
from goal_engine import today_bangkok, plan_goals, goal_metrics, calendar_rows
from goal_storage import GoalStore


def run(request, store, current=None, consent=False):
    current=current or today_bangkok()
    snapshot=store.read()
    action=request.get('action','view')
    if action=='list':return snapshot
    recorded_today={e['goal_id'] for e in snapshot['entries'] if e['date']==current.isoformat()}
    if action=='record_savings' and request.get('goal',{}).get('date',current.isoformat())==current.isoformat():
        recorded_today.add(request['goal']['goal_id'])
    def evaluate(goals):
        return plan_goals(goals,request.get('profile',{}),request.get('budget',{}),
                          current,request.get('forecast'),request.get('coverage'),recorded_today)
    if action in ('preview','view'):
        goals=snapshot['goals']
        if action=='preview':
            candidate=dict(request['goal'],status='DRAFT',goal_id=request['goal'].get('goal_id') or 'preview')
            goals=[g for g in goals if g['goal_id']!=candidate['goal_id']]+[candidate]
        report=evaluate(goals)
        report['revision']=snapshot['revision']
        report['calendar']={g['goal_id']:calendar_rows(goal_metrics(g,current),current,
                            [e for e in snapshot['entries'] if e['goal_id']==g['goal_id']])
                            for g in goals if g.get('status')!='DELETED'}
        if request.get('goal_id'):
            report['goals']=[g for g in report['goals'] if g['goal_id']==request['goal_id']]
            report['calendar']={key:rows for key,rows in report['calendar'].items() if key==request['goal_id']}
        return report
    return store.mutate(action,request['goal'],consent=consent,
                        expected_revision=request.get('expected_revision'),
                        operation_id=request.get('operation_id'),current=current,validate=evaluate)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consent',action='store_true')
    parser.add_argument('--store')
    args=parser.parse_args()
    try:
        raw=sys.stdin.read(1000001)
        if len(raw)>1000000:raise ValueError('request_too_large')
        from goal_storage import default_store
        request=json.loads(raw)
        if request.get('synthetic') is True:
            from companion import demo_input
            request={**demo_input(today_bangkok()),**request}
        result=run(request,GoalStore(args.store or default_store(request.get('synthetic') is True)),consent=args.consent)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps(dict(error=str(exc)),ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
