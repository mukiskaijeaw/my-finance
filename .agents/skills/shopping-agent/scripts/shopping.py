"""Codex chat helper: stdin JSON -> JSON or Markdown; no server or network."""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal
from urllib.parse import quote, urlparse

from engine import evaluate, read_ledger, SCHEMA, money

PRODUCT_KEYS = ('brand', 'model', 'sku', 'color', 'size', 'features', 'category')
STATUS = {'AFFORDABLE':'AFFORDABLE — ซื้อได้ตามข้อมูลที่ยืนยัน',
          'SAVE_FIRST':'SAVE_FIRST — เก็บเงินก่อน',
          'NOT_AFFORDABLE':'NOT_AFFORDABLE — ยังไม่เหมาะสม',
          'INSUFFICIENT_DATA':'INSUFFICIENT_DATA — ข้อมูลไม่พอ'}

def today():
    return datetime.now(timezone(timedelta(hours=7))).date()

def product_query(product):
    """A strict allowlist, never copies budget/profile/transactions into a query.

    Values still require the Codex agent to check that they describe a product.
    This is not a PII classifier for arbitrary user text.
    """
    if not isinstance(product, dict) or set(product) - set(PRODUCT_KEYS):
        raise ValueError('query accepts product attributes only; financial fields forbidden')
    parts = []
    for key in PRODUCT_KEYS:
        value = product.get(key)
        if value is not None:
            if not isinstance(value, str) or len(value) > 200:
                raise ValueError('product attributes must be short strings')
            parts.append(value.strip())
    if not any(parts):
        raise ValueError('product attributes required')
    return ' '.join(v for v in parts if v) + ' ประเทศไทย'

def cell(value):
    if value is None or value == '':
        return 'ไม่ทราบ'
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ').replace('<','&lt;').replace('>','&gt;')

def safe_link(value):
    if not isinstance(value, str):
        return 'ไม่มีลิงก์ที่ยืนยัน'
    p=urlparse(value)
    if p.scheme != 'https' or not p.netloc or p.username or p.password:
        return 'ไม่มีลิงก์ที่ยืนยัน'
    return '[หน้าสินค้า](' + quote(value, safe=':/?=&%#@+;,~_-') + ')'

def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |'] +
                     ['| '+' | '.join(row)+' |' for row in rows])

def product_image(listing):
    """Only evidence-verified HTTPS images; never fetches or generates images."""
    url=listing.get('image_url')
    source=listing.get('image_source')
    if listing.get('image_verified') is not True or listing.get('image_matches_variant') is not True:
        return 'รูปสินค้า: ยังไม่มีรูปที่ยืนยันตรงรุ่น/ตัวเลือก'
    for value in (url, source):
        if not isinstance(value,str):
            return 'รูปสินค้า: ยังไม่มีแหล่งภาพที่ยืนยัน'
        parsed=urlparse(value)
        if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:
            return 'รูปสินค้า: แหล่งภาพไม่รองรับ'
    alt=str(listing.get('name','สินค้า')).replace('[','').replace(']','').replace('\\','').replace('\n',' ').replace('\r',' ').replace('<','').replace('>','')
    return '!['+alt+']('+quote(url,safe=':/?=&%#@+;,~_-')+')\n\nแหล่งภาพ: '+safe_link(source)

def amount(value):
    if value is None:
        return 'ยังประเมินไม่ได้'
    return f'{Decimal(value):,.2f} บาท'

def listing_details(listing):
    """Same three fields for every product, including explicit unknown states."""
    variants=listing.get('variants')
    options='ยังไม่ยืนยันตัวเลือกสินค้า'
    if listing.get('variants_verified') is True and isinstance(variants,list) and variants and all(isinstance(v,str) and v.strip() for v in variants):
        options=', '.join(variants)
    discount='ยังไม่มีส่วนลดเพิ่มเติมที่ยืนยัน'
    raw_discount=listing.get('discount')
    if not isinstance(raw_discount,bool) and raw_discount in ('0',0):
        discount='ไม่ใช้คูปองเพิ่มเติมในการเปรียบเทียบ'
    elif listing.get('discount_verified') is True and listing.get('eligible') is True:
        try:
            discount='ลด '+amount(money(raw_discount))
        except ValueError:
            pass
    shipping='ยังไม่ยืนยันค่าจัดส่ง'
    if listing.get('shipping_verified') is True:
        try:
            fee=money(listing.get('shipping'))
            shipping='ส่งฟรี (ยืนยันแล้ว)' if fee==0 else amount(fee)
        except ValueError:
            pass
    return table(['ตัวเลือกสินค้า','ส่วนลดเพิ่มเติม','ค่าจัดส่ง'],[[cell(options),cell(discount),cell(shipping)]])

def financial_cards(payload, report):
    """Markdown fallback for chat: renderer never invents financial metrics."""
    icons={'AFFORDABLE':'🟢','SAVE_FIRST':'🟡','NOT_AFFORDABLE':'🔴','INSUFFICIENT_DATA':'⚪'}
    advice={'AFFORDABLE':'ซื้อได้ตามงบที่ยืนยัน โดยคงเงินสำรองและเป้าหมายออมไว้ ตรวจสต็อกและยอดจ่ายอีกครั้งก่อนซื้อ',
            'SAVE_FIRST':'แนะนำเก็บเงินเพิ่มตามแผนก่อนซื้อ โดยไม่ถอนเงินสำรองหรือเงินออมที่กันไว้',
            'NOT_AFFORDABLE':'แนะนำชะลอซื้อและจัดการภาระที่ยังไม่ครอบคลุมก่อน หรือพิจารณาตัวเลือกที่ถูกลง',
            'INSUFFICIENT_DATA':'ยังไม่สรุปว่าซื้อไหว ยืนยันราคาสุทธิและข้อมูลการเงินที่ขาดก่อน'}
    labels={'income':'รายได้สุทธิ','essential':'รายจ่ายจำเป็น','debt':'ยอดชำระหนี้ต่อเดือน','saving':'เป้าหมายออมต่อเดือน',
            'cash':'เงินสดปัจจุบัน','emergency':'เงินสำรองฉุกเฉิน','reserved':'เงินกันภาระค้างจ่าย'}
    demo=report.get('data_mode')=='demo'
    lines=['> **DEMO — ข้อมูลการเงิน ราคา ค่าส่ง และสต็อกทั้งหมดเป็นข้อมูลจำลอง ไม่ใช่ของผู้ใช้หรือร้านจริง**', ''] if demo else []
    for listing,result in zip(payload.get('listings',[]),report['results']):
        f=result['financial'];status=f['status'];price=result['price']
        if not demo:
            lines += [product_image(listing),'']
        lines += [listing_details(listing),'']
        lines += ['## Financial Fit · '+cell(result['name']), '',f"**{icons[status]} {STATUS[status]}**",'',
                  '### '+amount(price['effective']),
                  ('ยอดรวมจำลอง (รวมค่าส่งจำลอง)' if demo else 'ราคาสุทธิรวมค่าส่งและส่วนลดที่ยืนยัน · '+cell(listing.get('store'))+' · '+safe_link(listing.get('url'))),
                  '',table(['เงินพร้อมใช้','เหลือต่อเดือน','งบเหลือหลังซื้อ'],
                           [['**'+amount(f.get('available'))+'**','**'+amount(f.get('monthly_surplus'))+'**','**'+amount(f.get('remaining_after_purchase'))+'**']]),'']
        months=f.get('months')
        when='ซื้อได้ตอนนี้ตามงบที่ยืนยัน' if months==0 else (f'ประมาณ **{months} เดือน**' if months is not None else 'ยังระบุเวลาไม่ได้')
        lines += ['**ซื้อได้เมื่อไร:** '+when]
        progress=f.get('savings_progress')
        if progress:
            bar='█'*progress['filled_segments']+'░'*(progress['total_segments']-progress['filled_segments'])
            lines += [f"**ความคืบหน้าแผนเก็บเงิน:** `{bar}` **{progress['percent']}%**",
                      'เงินในแผน '+amount(progress['funded'])+' / เป้าหมาย '+amount(progress['goal'])+' · ขาดอีก '+amount(progress['remaining'])]
        else:
            lines += ['**ความคืบหน้าแผนเก็บเงิน:** ยังประเมินไม่ได้ — ไม่แสดงเปอร์เซ็นต์เมื่อข้อมูลขาด']
        lines += ['', '**คำแนะนำ:** '+advice[status]]
        if listing.get('stock_verified') is not True or listing.get('stock')!='available':
            lines += ['**สต็อก:** '+('สินค้าหมดตามหน้าร้าน' if listing.get('stock_verified') is True and listing.get('stock')=='out_of_stock' else 'ยังไม่ยืนยันว่าพร้อมซื้อ')]
        if not demo and result['listing_match']['tier']!='HIGH':
            lines += ['**หลักฐานรุ่น/ตัวเลือก:** '+result['listing_match']['tier']+' — ควรยืนยันรุ่น/สี/ขนาดก่อนตัดสินใจ']
        missing=[]
        for issue in f['issues']:
            base=issue.removesuffix('_missing_or_invalid')
            missing.append(labels.get(base,{'confirm_budget_complete':'ยืนยันว่างบครบและไม่ซ้ำ','confirm_future_obligations':'ยืนยันภาระอนาคตครบ',
                'profile_outdated_or_undated':'ยืนยันข้อมูลงบล่าสุด','income_kind_missing':'รายได้คงที่หรือไม่แน่นอน',
                'verified_effective_price_required':'ราคาสุทธิที่ยืนยันแล้ว','invalid_future_obligation':'รายการภาระอนาคต',
                'need_three_complete_income_months':'รายได้ครบอย่างน้อย 3 เดือน','protected_cash_not_covered':'เงินสดไม่ครอบคลุมยอดที่ต้องคุ้มครอง',
                'future_obligations_not_covered':'เงินสดไม่ครอบคลุมเงินกันภาระอนาคต'}.get(issue,issue)))
        if missing:
            lines += ['**ต้องยืนยัน/ข้อจำกัด:** '+', '.join(cell(x) for x in missing)]
        if price['issues']:
            lines += ['**ข้อจำกัดราคา:** '+', '.join(price['issues'])+' — ไม่ใช้ราคาประมาณการสรุปซื้อไหว']
        lines += ['**ตรวจข้อมูล:** ราคา '+cell(listing.get('checked'))+' · งบ '+cell(payload.get('profile',{}).get('as_of')), '', '---', '']
    if len(report['results'])>1:
        rows=[]
        for result in report['results']:
            f=result['financial']
            ratio=f.get('spending_percent')
            rows.append([cell(result['name']),STATUS[f['status']],amount(f.get('remaining_after_purchase')),
                         str(ratio)+'%' if ratio is not None else 'ยังประเมินไม่ได้',amount(result['difference_from_lowest_verified']),
                         'คงเป้าหมายตามงบ' if f.get('goal_impact')=='protected' else 'ควรรอ/ยังประเมินไม่ได้'])
        lines += [table(['ตัวเลือก','Financial Fit','งบหลังซื้อ','สัดส่วนเงินพร้อมใช้','ส่วนต่างราคา','เป้าหมายออม'],rows),'']
    quality=report.get('data_quality',{})
    if any(quality.values()):
        lines += ['**ข้อจำกัด Pillar 1:** '+cell(json.dumps(quality,ensure_ascii=False))]
    lines += ['**สมมติฐาน:** ใช้งบที่ยืนยันเท่านั้น ไม่หักภาระ/ออมซ้ำ กันภาระอนาคตทุกยอดล่วงหน้า รายได้ไม่แน่นอนใช้ค่าต่ำสุดจากเดือนที่ยืนยันครบ; แผนเก็บเงินใช้เงิน earmarked หากระบุ มิฉะนั้นใช้เงินพร้อมใช้',
              '**ข้อจำกัด:** งบหลังซื้อเป็นการจำลอง ระยะเวลาใช้เงินเหลือต่อเดือนและราคาคงเดิม ไม่รับประกันวันซื้อได้',
              'ไม่มีการซื้อหรือบันทึกรายจ่ายจากการประเมินนี้ และไม่มีการติดตามเบื้องหลัง']
    return '\n'.join(lines)

def run_demo(current_day):
    """Explicit, isolated simulation. Never loads Pillar 1 or changes its files."""
    path=Path(__file__).resolve().parents[1]/'tests/fixtures'/'demo.json'
    request=json.loads(path.read_text(encoding='utf-8'))
    if request.get('synthetic') is not True:
        raise ValueError('demo fixture must be explicitly synthetic')
    # Only synthetic fixture dates move with the demonstration; real data is never refreshed this way.
    request['profile']['as_of']=current_day.isoformat()
    for listing in request['listings']:
        listing['checked']=current_day.isoformat()
    report=evaluate(request,current_day)
    report['data_mode']='demo'
    report['notice']='All financial data, prices, shipping and stock are synthetic; not a personal assessment or live offer.'
    return request,report

def render(payload, report):
    if 'decision_report' in report:
        from decision_policy import render_decision
        return render_decision(report['decision_report'])
    if 'planning_result' in report:
        from planning_cards import render_planning
        cards = render_planning(payload['planning'], report['planning_result'])
        if not payload.get('listings'):
            return cards
        return cards + '\n\n' + financial_cards(payload, report)
    if payload.get('include_financial') is True:
        return financial_cards(payload, report)
    lines=['ผลการค้นหาและเปรียบเทียบสินค้า', '']
    for listing in payload.get('listings',[]):
        lines += ['### '+cell(listing.get('name')),product_image(listing),'',listing_details(listing),'']
    rows=[]
    for listing,result in zip(payload.get('listings',[]),report['results']):
        price=result['price']
        discount=listing.get('discount')
        if discount not in ('0',0) and (listing.get('discount_verified') is not True or listing.get('eligible') is not True):
            discount=None
        rows.append([cell(listing.get('name')),cell(listing.get('store')),cell(listing.get('price')),
                     cell(listing.get('shipping')),cell(discount),cell(price['effective']) if price['effective'] is not None else 'ยังยืนยันไม่ได้',
                     cell(listing.get('stock')) if listing.get('stock_verified') is True else 'ยังไม่ยืนยัน',
                     safe_link(listing.get('url')),cell(listing.get('checked'))])
    lines.append(table(['สินค้า/รุ่น','ร้าน','ราคา (บาท)','ค่าส่ง','ส่วนลดที่ยืนยัน','ราคาสุทธิ','สต็อก','ลิงก์','ตรวจเมื่อ'],rows))
    for result in report['results']:
        lines.append('\n'+cell(result['name'])+': Identification '+result['identification']['tier']+
                     '; Listing match '+result['listing_match']['tier']+' (ระดับหลักฐาน ไม่ใช่เปอร์เซ็นต์)')
        if result['price']['issues']:
            lines.append('ข้อจำกัดราคา: '+', '.join(result['price']['issues']))
    if payload.get('include_financial', False):
        lines += ['', 'Financial Fit และผลกระทบ (บาท)', '']
        quality=report.get('data_quality',{})
        if any(quality.values()):
            lines.append('ข้อจำกัดข้อมูล Pillar 1: '+cell(json.dumps(quality,ensure_ascii=False)))
        rows=[]
        for result in report['results']:
            f=result['financial']
            rows.append([cell(result['name']),STATUS[f['status']],cell(f.get('monthly_surplus')),cell(f.get('available')),
                         cell(f.get('remaining_after_purchase')),cell(f.get('spending_percent')),
                         cell(f.get('months')),cell(result['difference_from_lowest_verified']),cell(f.get('goal_impact'))])
            if f['issues']:
                lines.append('ข้อมูลที่ต้องยืนยันสำหรับ '+cell(result['name'])+': '+', '.join(f['issues']))
        lines += ['',table(['สินค้า','สถานะ','เหลือต่อเดือน','เงินพร้อมใช้','งบเหลือหลังซื้อ','ใช้เงินพร้อมใช้ (%)','เก็บเพิ่ม (เดือน)','ส่วนต่างราคาต่ำสุดที่ยืนยัน','เป้าหมายออม'],rows)]
        lines += ['','งบเหลือหลังซื้อเป็นการจำลอง ไม่ใช่ยอดบัญชีหลังทำธุรกรรม; เป้าหมายออม protected หมายถึงกันตามงบที่ยืนยัน ไม่ใช่รับประกันอนาคต',
                  'สมมติฐาน: ไม่หักภาระรายเดือนจากเงินสดซ้ำ; reserved คือภาระปัจจุบันค้างจ่าย; กัน future_extra ทั้งหมดไว้ล่วงหน้า; รายได้ไม่แน่นอนใช้ค่าต่ำสุดอย่างน้อย 3 เดือน; ระยะเวลาปัดขึ้นและราคาคงเดิม']
    lines += ['', report['recommendation'],
              'ยังสรุปร้านที่ถูกที่สุดไม่ได้' if not report['cheapest_claim_supported'] else 'เปรียบเทียบราคาต่ำสุดได้เฉพาะรายการที่ตรวจสอบในตารางนี้',
              report['monitoring']]
    return '\n'.join(lines)

def load_finance(finance_dir, current_day, profile_path=None, include_ledger=True):
    if not finance_dir:
        return {'ledger':{'issues':['finance_source_not_configured'],'monthly':{},'cash_inferred':False},
                'profile':{},'issues':['finance_source_not_configured'],'profile_candidates':[],
                'schema':SCHEMA,'connected':False,
                'note':'Pillar 4 is standalone. Select a local Pillar 1 source only for financial assessment; never infer missing amounts.'}
    root=Path(finance_dir).resolve()
    if not (root/'AGENTS.md').is_file():
        raise ValueError('AGENTS.md not found: read project rules before using financial data')
    ledger=read_ledger(root/'database.csv',current_day) if include_ledger else {'issues':[],'monthly':{},'cash_inferred':False,'not_loaded':True}
    result={'ledger':ledger,'profile':{},'issues':[],
            'profile_candidates':[p.name for p in root.glob('*profile*.json')],
            'schema':SCHEMA,'note':'No income, debt, emergency reserve or cash inferred from incomplete transactions.'}
    if profile_path:
        path=Path(profile_path).resolve()
        if path.parent != root:
            raise ValueError('profile must be inside the selected finance project')
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            # Legacy profiles are not silently mapped into a cash/budget snapshot.
            if not isinstance(data,dict) or data.get('schema_version') != 1 or not isinstance(data.get('profile'),dict):
                raise ValueError('unsupported profile schema')
            result['profile']=data['profile']
        except (OSError,ValueError):
            result['issues'].append('profile_unavailable_or_unsupported')
    return result

def run_request(payload, current_day, finance_dir=None):
    if not isinstance(payload,dict):
        raise ValueError('request must be an object')
    request=dict(payload)
    if 'include_financial' in request and not isinstance(request['include_financial'],bool):
        raise ValueError('include_financial must be boolean')
    finance=None
    if request.get('include_financial') is True:
        finance=load_finance(finance_dir,current_day,request.get('profile_path'))
        request['profile']={**finance['profile'],**request.get('profile',{})}
    else:
        request.pop('profile',None)
        request.pop('profile_path',None)
    report=evaluate(request,current_day)
    if request.get('include_financial') is True and 'decision' in request:
        from decision_policy import evaluate_decision
        report['decision_report']=evaluate_decision(request['profile'],request['decision'],current_day)
    if request.get('include_financial') is True and 'planning' in request:
        from planning import run, fit
        report['planning_result']=run(request['profile'],request['planning'],current_day)
        if request['planning'].get('budget'):
            for result in report['results']:
                result['financial']=fit(request['profile'],result['price']['effective'],request['planning']['budget'],current_day)
    if finance:
        report['data_quality']={'ledger':finance['ledger']['issues'],'profile':finance['issues']}
    return request,report

def save_purchase_goals(path, payload, consent, current_day, finance_dir=None):
    """Consent-only, versioned local snapshots; never overwrite a goal or ledger."""
    if consent is not True:
        raise ValueError('explicit consent required to save or change purchase goals')
    if payload.get('planning',{}).get('action') != 'readiness':
        raise ValueError('purchase goals require a readiness request')
    request, report=run_request({**payload,'include_financial':True},current_day,finance_dir)
    result=report['planning_result']
    if result['status']=='INSUFFICIENT_DATA':
        raise ValueError('cannot save unvalidated goal allocations: '+','.join(result['issues']))
    goals=[]
    for original, evaluated in zip(request['planning']['goals'],result['goals']):
        if not isinstance(original.get('product_name'),str) or not original['product_name'].strip():
            raise ValueError('product_name required')
        listing=original['latest_listing']
        if safe_link(listing.get('url'))=='ไม่มีลิงก์ที่ยืนยัน':
            raise ValueError('verified product URL required')
        target=money(original.get('target_price'))
        goals.append({**evaluated,'product_name':original['product_name'],'product_url':listing['url'],
                      'target_price':str(target),'estimated_purchase_months':evaluated['months'],
                      'allocation_confirmed':True})
    path=Path(path).resolve()
    if path.suffix.lower()!='.json' or path.parent.name!='local':
        raise ValueError('purchase goals must use a separate local/*.json snapshot')
    path.parent.mkdir(parents=True,exist_ok=True)
    data={'schema_version':1,'purchase_goals':goals,'last_checked':current_day.isoformat(),'monitoring':False}
    with path.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    return data

def save_watchlist(path, product, consent=False):
    if consent is not True:
        raise ValueError('explicit consent required to save a watchlist')
    # Deliberately excludes free-form evidence, profile, receipts and prices.
    product_query(product)
    data={'product':product,'saved_at':today().isoformat(),'monitoring':False}
    path=Path(path)
    if path.name in ('database.csv','tax_preparation.csv') or path.suffix.lower() != '.json':
        raise ValueError('watchlist must be a separate JSON file')
    # Exclusive creation prevents silently replacing unrelated local data.
    with path.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    return data

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('welcome','evaluate','decision','plan','goal','goals','purchase','companion','ledger','query','watchlist','demo'))
    parser.add_argument('--finance-dir',default=os.environ.get('FINANCE_DIR'),help='Optional local Pillar 1 source, used only for financial intent; no source is connected by default')
    parser.add_argument('--profile-path')
    parser.add_argument('--input',help='Local JSON; omitted means stdin. Avoid financial data in command arguments.')
    parser.add_argument('--format',choices=('json','markdown','inline'),default='json')
    parser.add_argument('--store',help='Separate local goal SQLite file; never the transaction ledger')
    parser.add_argument('--output',help='New watchlist JSON path (never a transaction CSV)')
    parser.add_argument('--consent',action='store_true',help='Use only after explicit user consent in chat')
    args=parser.parse_args(argv)
    try:
        if args.command=='welcome':
            from welcome import native_question
            result=native_question()
        elif args.command=='demo':
            if args.input or args.profile_path or args.output or args.consent:
                raise ValueError('demo uses only the built-in synthetic fixture; no input, profile, watchlist or consent options')
            request,result=run_demo(today())
            if args.format=='markdown':
                print(render(request,result))
                return 0
        elif args.command=='ledger':
            result=load_finance(args.finance_dir,today(),args.profile_path)
        else:
            raw=Path(args.input).read_text(encoding='utf-8-sig') if args.input else sys.stdin.read(1000001)
            if len(raw)>1000000:
                raise ValueError('request too large')
            payload=json.loads(raw)
            if payload.get('synthetic') is True and (args.command=='goals' or (args.command=='purchase' and payload.get('action') in ('evaluate','select_and_evaluate','change_date','buy_today','goal_preview','start_goal','confirm_goal'))):
                from companion import demo_input
                payload={**demo_input(today()),**payload}
            if args.command=='companion':
                from companion import run_companion,render_companion
                from goal_storage import GoalStore,default_store
                from shared_state import load_transactions
                if args.finance_dir and payload.get('synthetic') is not True:
                    if payload.get('action','daily') in ('daily','travel') and 'profile' not in payload:
                        provider=load_finance(args.finance_dir,today(),args.profile_path,include_ledger=False)
                        payload={**payload,'profile':provider.get('profile',{})}
                    if payload.get('action','daily') in ('daily','leaks','subscriptions') and 'transactions' not in payload:
                        payload={**payload,'transactions':load_transactions(args.finance_dir,today().strftime('%Y-%m'),3 if payload.get('action') in ('leaks','subscriptions') else 1)}
                result=run_companion(payload,GoalStore(args.store or default_store(payload.get('synthetic') is True)),today())
                if args.format=='inline':
                    if not args.output:raise ValueError('--output required for inline fragment')
                    raw=render_companion(result)
                    with Path(args.output).open('x',encoding='utf-8') as stream:stream.write(raw)
                    print(json.dumps({'inline_path':str(Path(args.output).resolve())}));return 0
                if args.format=='markdown':
                    report=result['report'].get('initial',result['report'])
                    print('Financial Companion — '+result['kind']+'\n'+json.dumps(report,ensure_ascii=False,indent=2));return 0
            elif args.command=='purchase':
                from purchase_flow import run_purchase
                from purchase_renderer import render_purchase,render_purchase_markdown
                from goal_storage import GoalStore,default_store
                store=GoalStore(args.store or default_store(payload.get('synthetic') is True))
                financial_actions=('evaluate','select_and_evaluate','change_date','buy_today','goal_preview','start_goal','confirm_goal')
                if args.finance_dir and payload.get('synthetic') is not True and payload.get('action') in financial_actions and 'profile' not in payload:
                    provider=load_finance(args.finance_dir,today(),args.profile_path)
                    payload={**payload,'profile':provider.get('profile',{})}
                result=run_purchase(payload,store,today(),args.consent)
                if args.format=='inline':
                    if not args.output:raise ValueError('--output required for inline fragment')
                    with Path(args.output).open('x',encoding='utf-8') as stream:
                        stream.write(render_purchase(result,payload.get('synthetic') is True))
                    print(json.dumps({'inline_path':str(Path(args.output).resolve())}));return 0
                if args.format=='markdown':
                    print(render_purchase_markdown(result));return 0
            elif args.command=='goals':
                from goal_planner import run as run_goals
                from goal_storage import GoalStore,default_store
                from goal_renderer import render_inline,render_markdown
                if args.format in ('inline','markdown') and payload.get('action','view') not in ('view','preview'):
                    raise ValueError('mutations return JSON; render a fresh view after confirmation')
                store=GoalStore(args.store or default_store(payload.get('synthetic') is True))
                if args.finance_dir and payload.get('synthetic') is not True and payload.get('action','view')!='list' and 'profile' not in payload:
                    provider=load_finance(args.finance_dir,today(),args.profile_path)
                    payload={**payload,'profile':provider.get('profile',{})}
                result=run_goals(payload,store,today(),args.consent)
                if args.format in ('inline','markdown'):
                    if payload.get('action','view') not in ('view','preview'):
                        raise ValueError('render a fresh view after a successful goal mutation')
                    if args.format=='inline':
                        if not args.output:raise ValueError('--output required for inline fragment')
                        raw=render_inline(result,demo=payload.get('synthetic') is True)
                        with Path(args.output).open('x',encoding='utf-8') as stream:stream.write(raw)
                        print(json.dumps({'inline_path':str(Path(args.output).resolve())}));return 0
                    print(render_markdown(result));return 0
            elif args.command=='query':
                result={'query':product_query(payload)}
            elif args.command=='watchlist':
                if not args.output:
                    raise ValueError('--output is required')
                result=save_watchlist(args.output,payload,args.consent)
            elif args.command=='goal':
                if not args.output:
                    raise ValueError('--output is required')
                result=save_purchase_goals(args.output,payload,args.consent,today(),args.finance_dir)
            else:
                if args.command=='decision':
                    payload={**payload,'include_financial':True}
                    if not isinstance(payload.get('decision'),dict):
                        raise ValueError('decision object required')
                if args.command=='plan':
                    payload={**payload,'include_financial':True}
                    if not isinstance(payload.get('planning'),dict):
                        raise ValueError('planning object required')
                request,result=run_request(payload,today(),args.finance_dir)
                if args.format=='markdown':
                    print(render(request,result))
                    return 0
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,TypeError,AttributeError,KeyError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
