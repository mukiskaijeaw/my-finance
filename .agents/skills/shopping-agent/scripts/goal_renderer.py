"""Cached inline/Markdown presentation and personality; no financial formulas."""
import json
from pathlib import Path


def personality(goal, feasible):
    if goal['status']=='FUNDED':return 'ครบเป้าหมายแล้ววว! แต่เช็กเงื่อนไขก่อนจ่ายกันอีกทีนะครับ'
    if feasible=='INSUFFICIENT_DATA':return 'ขอข้อมูลที่ยังขาดก่อนนะครับ จะได้ไม่พาแผนสะดุด'
    if feasible=='NOT_FEASIBLE':return 'คุณพี่ครับ แผนรวมยังไม่พอครับ ลองเลื่อนวันหรือลดยอดเป้าหมายก่อนดีไหม'
    if goal['status']=='PAUSED':return 'พักแผนนี้ไว้ เงินที่เก็บแล้วไม่กลายเป็นเงินช้อปอัตโนมัตินะครับ'
    return f"ต้องเก็บวันละ {goal['daily_saving']} บาทเพื่อ {goal['goal_name']} ครับ"


def ui_data(report, demo=False):
    goals=[]
    for raw in report.get('goals',[]):
        goal=dict(raw)
        goal['countdown_text']=('เลยกำหนดแล้ว' if goal['days_remaining']<0 else f"อีก {goal['days_remaining']} วัน · เก็บได้รวมวันนี้ {goal['saving_days_including_today']} วัน")
        goal['message']=personality(goal,report['status'])
        if demo:
            from goal_engine import demo_progress_states
            from datetime import date
            goal['demo_progress']=demo_progress_states(goal,date.fromisoformat(report['current_date']))
        goals.append(goal)
    issues={'complete_future_cashflow_required':'ต้องยืนยันกระแสเงินสดจนถึงวันเป้าหมาย',
            'unconfirmed_future_cashflow':'ข้อมูลรายรับรายจ่ายอนาคตยังไม่ยืนยัน',
            'deadline_passed':'มีเป้าหมายเลยกำหนดแล้ว'}
    detail='; '.join(issues.get(code,'ข้อมูลที่ต้องตรวจ: '+code) for code in report.get('issues',[]))
    if not detail:detail='กันภาระและเป้าหมายอื่นร่วมกันแล้ว' if report['status']=='FEASIBLE' else 'ตรวจหรือระบุข้อมูลเป้าหมายก่อนเริ่มแผน'
    return dict(goals=goals,current_date=report['current_date'],daily_spending=report.get('daily_spending'),
                calendar=report.get('calendar',{}),demo=demo,
                summary='สถานะแผนรวม: '+report['status']+' · '+detail)


def render_inline(report, demo=False):
    template=Path(__file__).resolve().parents[1]/'assets/goal-planner-inline.html'
    data=json.dumps(ui_data(report,demo),ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    raw=template.read_text(encoding='utf-8').replace('__GOAL_PAYLOAD__',data)
    if len(raw.encode('utf-8'))>1000000:
        raise ValueError('inline_too_large_request_one_goal_id')
    return raw


def render_markdown(report):
    lines=['**Goal Planner — '+report['status']+'**','', '| เป้าหมาย | ยอดเป้าหมาย | วันที่ | เก็บ/วัน | ความคืบหน้า |','|---|---:|---|---:|---:|']
    for g in report.get('goals',[]):
        name=g['goal_name'].replace('|','\\|').replace('\n',' ')
        lines.append(f"| {name} | {g['target_amount']} | {g['target_date']} | {g['daily_saving'] or 'ยังประเมินไม่ได้'} | {g['progress']}% |")
    lines+=['','งบใช้ต่อวัน: '+str(report.get('daily_spending') or 'ยังประเมินไม่ได้')]
    return '\n'.join(lines)
