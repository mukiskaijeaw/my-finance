"""Reusable purchase UI data adapter. No financial/date calculations."""
import json
from pathlib import Path


def public_session(session):
    return {k:session[k] for k in ('version','stage','intent','candidates','selected_product','selection_confirmed','identification') if k in session}


def render_purchase(session, demo=False):
    if session.get('goal_view'):
        from goal_renderer import render_inline
        return render_inline(session['goal_view'],demo)
    def compact(report):
        if not report:return None
        keep=('product','current_date','target_date','quote','financial','decision','available_spending',
              'remaining_after_purchase','existing_goal_commitments','suggested_purchase_date',
              'daily_saving','daily_spending','new_plan_zero_assumption','linked_goal_id','goal_confirmation_required',
              'review_token','reviewed_purchase_saved_amount','savings_progress','goal_status','goal_issues')
        result={key:report.get(key) for key in keep}
        result['financial']={key:report['financial'].get(key) for key in ('status','issues')}
        return result
    date_fields=('target_date','suggested_purchase_date','daily_saving','daily_spending','savings_progress','goal_status','goal_issues')
    data=dict(session=public_session(session),report=compact(session.get('report')),demo=demo,price_simulation=session.get('price_simulation'),
              revision=session.get('store_revision'),date_reports={key:{field:report.get(field) for field in date_fields} for key,report in session.get('date_reports',{}).items()})
    raw=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=Path(__file__).resolve().parents[1]/'assets/purchase-flow-inline.html'
    result=template.read_text(encoding='utf-8').replace('__PURCHASE_PAYLOAD__',raw)
    if len(result.encode())>1000000:raise ValueError('purchase_ui_too_large')
    return result


def render_purchase_markdown(session):
    report=session.get('report')
    if report:
        return '\n'.join([report['product']['name'],report['decision']['label'],
            'Financial Fit: '+report['financial']['status'],
            'ราคาสุทธิ: '+str(report['quote']['effective'] or 'ยังไม่ยืนยัน'),
            'เงินเหลือ: '+str(report['remaining_after_purchase'] or 'ยังประเมินไม่ได้')])
    choices=session.get('candidates',[])
    if choices:return '\n'.join(p['name']+' — '+p['source'] for p in choices)
    return 'อยากได้สินค้าอะไรครับ? พิมพ์ชื่อ รุ่น ลิงก์ หรือแนบรูปในแชทได้เลย'
