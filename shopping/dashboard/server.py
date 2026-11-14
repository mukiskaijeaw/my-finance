"""Loopback-only dashboard; reuses Shopping's local engines. No external APIs."""
import argparse
import hashlib
import json
import secrets
import sys
import threading
import time
import webbrowser
from copy import deepcopy
from decimal import Decimal
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
# In my-finance the skill sits at the repo root and this dashboard in shopping/dashboard.
SCRIPTS=ROOT.parents[1]/'.agents/skills/shopping-agent/scripts'
sys.path.insert(0,str(SCRIPTS))
from companion import demo_input,run_companion
from goal_storage import GoalStore
from goal_planner import run as goal_run
from goal_engine import today_bangkok,plan_goals,amount,target_day
from shared_state import build_shared
from planning import fit
from purchase_flow import price_states
from companion_engine import user_expense_analysis


class Dashboard:
    def __init__(self,store=None):
        # Browser demo has its own store, distinct from chat demo and real goals.
        self.store=GoalStore(store or ROOT.parent/'local/dashboard-demo.sqlite3')
        self.token=secrets.token_urlsafe(32)
        self.reviews={};self.lock=threading.RLock()
        self.expense_summaries=[]

    def inputs(self):return demo_input(today_bangkok())

    def state(self):
        current=today_bangkok();data=self.inputs()
        goals=goal_run(dict(data,action='view'),self.store,current)
        return dict(mode='DEMO',date=current.isoformat(),revision=goals['revision'],
            daily=run_companion(dict(data,action='daily'),self.store,current)['report'],
            leaks=user_expense_analysis(self.expense_summaries,current),
            goals=goals,csrf=self.token)

    def expense_summary(self,payload):
        # In-memory, user-submitted analysis inputs; never a ledger or goal write.
        action=payload.get('action','add');items=deepcopy(self.expense_summaries)
        if action=='add':
            raw=payload['item']
            items.append(dict(id=secrets.token_hex(8),name=raw.get('name',''),amount=raw.get('amount'),kind=raw.get('kind'),period=raw.get('period')))
        elif action=='remove':items=[x for x in items if x['id']!=payload.get('id')]
        else:raise ValueError('unsupported_expense_summary_action')
        result=user_expense_analysis(items,today_bangkok())
        self.expense_summaries=items
        return result

    def purchase(self,payload):
        current=today_bangkok();data=self.inputs();snapshot=self.store.read()
        name=str(payload.get('name','')).strip()
        if not name:raise ValueError('กรอกชื่อสินค้าก่อนครับ')
        price=amount(payload.get('price'))
        shipping=amount(payload.get('shipping'))
        # Only a self-entered scenario, never advertised as a merchant quote.
        total=price+shipping
        shared=build_shared(data['profile'],data['budget'],snapshot,current)
        portfolio=shared['portfolio'];available=portfolio.get('remaining_spending_budget')
        financial={'status':'INSUFFICIENT_DATA','issues':portfolio.get('issues',[])}
        if portfolio['status']=='FEASIBLE':
            extra=max(Decimal(0),Decimal(portfolio['budget']['affordable_budget'])-Decimal(portfolio['budget']['minimum_remaining'])-Decimal(available))
            adjusted=deepcopy(data['profile']);adjusted['reserved']=str(amount(adjusted['reserved'])+extra)
            financial=fit(adjusted,str(total),data['budget'],current)
        target=target_day(payload.get('target_date') or 'สิ้นเดือน',current)
        goal=dict(goal_name=name,goal_category='purchase',target_amount=str(total),saved_amount='0',target_date=target.isoformat(),funding_source='free_cash')
        report=goal_run(dict(data,action='preview',goal=goal),self.store,current) if total>0 else None
        scenario=dict(available_spending=available,quote=dict(effective=str(total)),decision=dict(recommendation='NEED_MORE_INFO'))
        return dict(name=name,total=str(total),shipping=str(shipping),price_type='USER_ESTIMATE',financial=financial,
            available=available,remaining=str(Decimal(available)-total) if available is not None else None,
            simulation=price_states(scenario,current),goal=goal,plan=report,
            notice='ราคาที่กรอกเป็นสมมติฐาน ไม่ใช่ราคาหรือสต็อกที่ตรวจจากร้านค้า')

    def review(self,payload):
        action=payload.get('action','create');data=self.inputs();current=today_bangkok()
        if action not in ('create','record_savings','pause','activate','delete','edit'):raise ValueError('unsupported_action')
        goal=deepcopy(payload['goal']);snapshot=self.store.read()
        if action=='create':
            goal['activate_on_create']=True
            report=goal_run(dict(data,action='preview',goal=goal),self.store,current)
        else:
            goals=deepcopy(snapshot['goals']);selected=next((g for g in goals if g['goal_id']==goal.get('goal_id')),None)
            if not selected:raise ValueError('goal_not_found')
            if action=='record_savings':
                if any(e['goal_id']==selected['goal_id'] and e['date']==current.isoformat() for e in snapshot['entries']):raise ValueError('วันนี้บันทึกแล้วครับ ตรวจรายการเดิมก่อน')
                value=amount(goal['amount'])
                if value<=0:raise ValueError('positive_savings_required')
                selected['saved_amount']=str(amount(selected['saved_amount'])+value)
                goal['date']=current.isoformat()
            elif action in ('pause','activate','delete'):selected['status']={'pause':'PAUSED','activate':'ACTIVE','delete':'DELETED'}[action]
            else:
                allowed={'goal_name','goal_category','target_amount','target_date','image_url','priority','funding_source'}
                if set(goal)-allowed-{'goal_id'}:raise ValueError('unsupported_edit_field')
                selected.update({k:v for k,v in goal.items() if k in allowed})
            report=plan_goals(goals,data['profile'],data['budget'],current,recorded_today={e['goal_id'] for e in snapshot['entries'] if e['date']==current.isoformat()}|({goal['goal_id']} if action=='record_savings' else set()))
        body=dict(action=action,goal=goal,revision=snapshot['revision'],date=current.isoformat(),profile=data['profile'],budget=data['budget'])
        fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        token=secrets.token_urlsafe(24)
        # Short-lived in-memory review, never private files or cookies.
        self.reviews={k:v for k,v in self.reviews.items() if v['expires']>time.monotonic()}
        self.reviews[token]=dict(body=body,hash=fingerprint,expires=time.monotonic()+600)
        return dict(review=token,action=action,goal=goal,report=report,revision=snapshot['revision'],requires_confirmation=True)

    def commit(self,payload):
        if payload.get('confirmed') is not True:raise ValueError('explicit_confirmation_required')
        token=payload.get('review');review=self.reviews.get(token)
        if not review or review['expires']<time.monotonic():raise ValueError('review_expired_refresh')
        body=review['body'];data=self.inputs();current=today_bangkok()
        fresh=dict(body,profile=data['profile'],budget=data['budget'],revision=self.store.read()['revision'],date=current.isoformat())
        if hashlib.sha256(json.dumps(fresh,sort_keys=True).encode()).hexdigest()!=review['hash']:raise ValueError('ข้อมูลเปลี่ยนแล้วครับ กรุณาตรวจแผนอีกครั้ง')
        result=goal_run(dict(data,action=body['action'],goal=body['goal'],expected_revision=body['revision'],operation_id=token),self.store,current,True)
        self.reviews.pop(token,None)
        return result


def make_server(port=8877,app=None):
    app=app or Dashboard()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def valid_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def respond(self,status,body,content_type='application/json; charset=utf-8'):
            raw=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.valid_host():return self.respond(403,{'error':'invalid_host'})
            path=urlsplit(self.path).path
            if path=='/api/state':return self.respond(200,app.state())
            static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/chat.js':('chat.js','text/javascript; charset=utf-8'),'/chat.css':('chat.css','text/css; charset=utf-8'),'/expense-ui.js':('expense-ui.js','text/javascript; charset=utf-8'),'/assets/wallet-normal.png':('assets/wallet-normal.png','image/png'),'/assets/wallet-angry.png':('assets/wallet-angry.png','image/png')}
            if path not in static:return self.respond(404,{'error':'not_found'})
            name,kind=static[path];self.respond(200,(ROOT/name).read_bytes(),kind)
        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('Origin')!=origin or self.headers.get('X-Dashboard-Token')!=app.token:return self.respond(403,{'error':'invalid_local_request'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=65536:raise ValueError('request_size_limit')
                if self.headers.get('Content-Type')!='application/json':raise ValueError('json_required')
                payload=json.loads(self.rfile.read(size));path=urlsplit(self.path).path
                with app.lock:
                    if path=='/api/purchase':result=app.purchase(payload)
                    elif path=='/api/chat':
                        from chat import respond
                        result=respond(app,payload)
                    elif path=='/api/expense-summary':result=app.expense_summary(payload)
                    elif path=='/api/travel':result=run_companion(dict(app.inputs(),action='travel',trip=payload['trip']),app.store,today_bangkok())['report']
                    elif path=='/api/review':result=app.review(payload)
                    elif path=='/api/commit':result=app.commit(payload)
                    else:return self.respond(404,{'error':'not_found'})
                self.respond(200,result)
            except (ValueError,KeyError,TypeError) as exc:self.respond(400,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8877);parser.add_argument('--open',action='store_true')
    args=parser.parse_args();server=make_server(args.port)
    url=f'http://127.0.0.1:{server.server_port}'
    print('Financial Companion DEMO: '+url,flush=True)
    if args.open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
