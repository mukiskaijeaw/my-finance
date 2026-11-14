"""Local transactional goal store. Never writes the Pillar 1 transaction ledger."""
import json
import sqlite3
import hashlib
import os
from contextlib import closing
from datetime import date
from pathlib import Path
from uuid import uuid4
from goal_engine import normalize_goal, amount


def default_store(synthetic=False):
    return Path(os.environ.get('SHOPPING_WORKSPACE',str(Path.cwd()))).resolve()/'local'/('demo-goals.sqlite3' if synthetic else 'goals.sqlite3')


class GoalStore:
    def __init__(self, path):
        self.path=Path(path).resolve()
        if self.path.suffix!='.sqlite3' or self.path.parent.name!='local':
            raise ValueError('goals_require_separate_local_sqlite3')

    def read(self):
        if not self.path.exists():return dict(revision=0,goals=[],entries=[])
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
                return dict(revision=0,goals=[],entries=[])
            return self._read(db)

    @staticmethod
    def _read(db):
        revision=db.execute('SELECT value FROM meta WHERE key="revision"').fetchone()[0]
        goals=[json.loads(r[0]) for r in db.execute('SELECT data FROM goals ORDER BY id')]
        entries=[dict(goal_id=r[0],date=r[1],amount=r[2]) for r in db.execute('SELECT goal_id,day,amount FROM savings ORDER BY day,goal_id')]
        return dict(revision=int(revision),goals=goals,entries=entries)

    def mutate(self, action, data, *, consent, expected_revision, operation_id, current, validate):
        if consent is not True:raise ValueError('explicit_confirmation_required')
        if type(expected_revision) is not int or not isinstance(operation_id,str) or not operation_id.strip():
            raise ValueError('revision_and_operation_id_required')
        if action not in ('create','edit','activate','pause','delete','record_savings'):
            raise ValueError('unknown_goal_action')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO meta VALUES("revision","0")')
            db.execute('CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY,data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS savings(goal_id TEXT,day TEXT,amount TEXT,PRIMARY KEY(goal_id,day))')
            db.execute('CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,response TEXT NOT NULL,request_hash TEXT NOT NULL)')
            fingerprint=hashlib.sha256(json.dumps([action,data],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            prior=db.execute('SELECT response,request_hash FROM operations WHERE id=?',(operation_id,)).fetchone()
            if prior:
                if prior[1]!=fingerprint:raise ValueError('operation_id_reused_for_different_request')
                db.execute('ROLLBACK');return json.loads(prior[0])
            snapshot=self._read(db)
            if snapshot['revision']!=expected_revision:raise ValueError('stale_revision_refresh_and_confirm')
            goals=snapshot['goals'];entry=None
            if action=='create':
                goal=normalize_goal(data,current)
                goal.update(goal_id=str(uuid4()),status='DRAFT')
                if goal.pop('activate_on_create',False) is True:
                    goal.update(status='ACTIVE',activated_on=current.isoformat())
                goals.append(goal)
            else:
                goal=next((g for g in goals if g['goal_id']==data.get('goal_id')),None)
                if not goal or goal['status']=='DELETED':raise ValueError('goal_not_found')
                if action=='edit':
                    allowed={'goal_name','goal_category','target_amount','target_date','image_url','priority','funding_source'}
                    if set(data)-allowed-{'goal_id'}:raise ValueError('unsupported_edit_field')
                    goal.update({k:v for k,v in data.items() if k in allowed})
                    goal.update(normalize_goal(goal,current))
                elif action=='activate':
                    goal['status']='ACTIVE';goal.setdefault('activated_on',current.isoformat())
                elif action=='pause':goal['status']='PAUSED'
                elif action=='delete':goal['status']='DELETED'
                else:
                    if goal['status']!='ACTIVE':raise ValueError('activate_goal_before_recording')
                    day=date.fromisoformat(data.get('date',current.isoformat()))
                    if not date.fromisoformat(goal['activated_on'])<=day<=current:
                        raise ValueError('savings_date_outside_active_history')
                    value=amount(data.get('amount'))
                    if value<=0:raise ValueError('positive_savings_required')
                    if db.execute('SELECT 1 FROM savings WHERE goal_id=? AND day=?',(goal['goal_id'],day.isoformat())).fetchone():
                        raise ValueError('duplicate_savings_day_review_existing_entry')
                    goal['saved_amount']=str(amount(goal['saved_amount'])+value)
                    entry=(goal['goal_id'],day.isoformat(),str(value))
            # Full portfolio evaluation runs inside the same transaction/version.
            report=validate(goals)
            if not isinstance(report,dict) or report.get('status') not in ('FEASIBLE','NOT_FEASIBLE','INSUFFICIENT_DATA'):
                raise ValueError('portfolio_validation_required')
            if action not in ('pause','delete','record_savings') and report['status']!='FEASIBLE':
                raise ValueError('plan_not_feasible_or_incomplete_review_before_save')
            db.execute('INSERT OR REPLACE INTO goals VALUES(?,?)',(goal['goal_id'],json.dumps(goal,ensure_ascii=False)))
            if entry:db.execute('INSERT INTO savings VALUES(?,?,?)',entry)
            revision=snapshot['revision']+1
            db.execute('UPDATE meta SET value=? WHERE key="revision"',(str(revision),))
            response=dict(revision=revision,goal=goal,portfolio_status=report['status'])
            db.execute('INSERT INTO operations VALUES(?,?,?)',(operation_id,json.dumps(response,ensure_ascii=False),fingerprint))
            db.execute('COMMIT');return response
        except Exception:
            if db.in_transaction:db.execute('ROLLBACK')
            raise
        finally:db.close()
