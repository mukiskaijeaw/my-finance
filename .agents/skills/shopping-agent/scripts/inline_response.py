"""Local presentation only: accepts computed display values, never reads finance."""
from html import escape
from pathlib import Path
import re

TITLES = {'balance': 'เงินคงเหลือ', 'purchase': 'ตัดสินใจซื้อของ',
          'savings': 'วางแผนแบ่งเงิน', 'subscriptions': 'จัดการ Subscription',
          'installment': 'ซื้อสดหรือผ่อน', 'travel': 'วางแผนเที่ยว',
          'confirmation': 'อัปเดตแผนการเงิน'}


def render(kind, values, *, demo=False):
    if kind not in TITLES:
        raise ValueError('unsupported response kind')
    if type(demo) is not bool:
        raise ValueError('explicit demo flag required')
    raw = (Path(__file__).resolve().parents[1]/'assets/response-inline.html').read_text(encoding='utf-8')
    fields = dict(values, KIND=kind, TITLE=TITLES[kind],
                  MODE='DEMO · ข้อมูลจำลอง' if demo else 'สรุปจากข้อมูลที่ระบุ')
    def substitute(match):
        value = fields.get(match.group(1))
        return escape('ยังไม่ยืนยัน' if value is None else str(value), quote=True)
    return re.sub(r'__([A-Z0-9_]+)__', substitute, raw)
