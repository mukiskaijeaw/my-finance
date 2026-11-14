"""PNG decision presentation. Consumes policy + financial results, never recalculates."""
import argparse
import json
import unicodedata
from decimal import Decimal
from pathlib import Path
from PIL import Image, ImageDraw, features
from card_renderer import PALETTES, font, windows_text_mask, value_text
from decision_policy import LABELS


def render_decision_card(report, output, theme='light', demo=False):
    f, decision = report['financial'], report['decision']
    if decision['recommendation'] not in LABELS or decision['financial_fit'] != f['status']:
        raise ValueError('consistent financial and decision output required')
    p = PALETTES[theme]
    im = Image.new('RGB', (1200, 1700), p['bg'])
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((30,30,1170,1670), radius=34, fill=p['card'])

    def text(x,y,message,size=28,bold=False,color=None):
        message = str(message)
        face = font(size,bold)
        if features.check_feature('raqm'):
            draw.text((x,y),message,font=face,fill=color or p['text'])
        else:
            mask=windows_text_mask(message,size,bold)
            im.paste(color or p['text'],(x,y,x+mask.width,y+mask.height),mask)

    def paragraph(y, message, size=27, lines=3):
        rows, row = [], ''
        face=font(size)
        for char in message:
            if draw.textlength(row+char,font=face)>1000 and not unicodedata.combining(char):
                rows.append(row); row=char
            else:
                row+=char
        if row: rows.append(row)
        for index,line in enumerate(rows[:lines]):
            text(86,y+index*43,line + ('…' if index==lines-1 and len(rows)>lines else ''),size)
        return y+min(len(rows),lines)*43

    text(86,74,'PERSONAL FINANCIAL DECISION',26,color=p['muted'])
    text(86,124,'ควรซื้อเลยไหม?',54,True)
    text(86,205,'DEMO · ข้อมูลจำลองสำหรับทดสอบ' if demo else 'ผลจากข้อมูลและบริบทที่ยืนยัน',25,color=p['muted'])
    draw.rounded_rectangle((86,265,1114,402),radius=23,fill=p['panel'])
    rec=decision['recommendation']
    status_color='#BC7A17' if rec in ('WAIT_AND_SAVE','BUY_WITH_CAUTION') else ('#3D9F76' if rec=='BUY_NOW' else '#72879A')
    draw.ellipse((111,299,131,319),fill=status_color)
    text(155,285,rec,31,True)
    text(112,337,decision['label'],32,True)
    text(86,437,'Financial Fit: '+f['status'],25,color=p['muted'])
    progress=f.get('savings_progress',{})
    metrics=[('ราคาสินค้าสุทธิ',report.get('price')),('เงินพร้อมใช้ซื้อ',f.get('available')),
             ('ต้องเก็บเพิ่ม',progress.get('remaining')),('เก็บเพิ่มได้ต่อเดือน',f.get('monthly_surplus'))]
    for i,(label,value) in enumerate(metrics):
        x=86+(i%2)*529; y=500+(i//2)*175
        draw.rounded_rectangle((x,y,x+499,y+148),radius=22,fill=p['panel'])
        text(x+23,y+20,label,25,color=p['muted'])
        label_value=value_text(value)
        size=48
        while draw.textlength(label_value,font=font(size,True))>450 and size>20:
            size-=1
        text(x+23,y+65,label_value,size,True)
    months=f.get('months')
    eta='ซื้อได้ตามงบตอนนี้' if months==0 else ('ประมาณ '+str(months)+' เดือน' if months is not None else 'ยังระบุเวลาไม่ได้')
    text(86,875,'ระยะเวลาตามแผน',25,color=p['muted'])
    text(86,917,eta,46,True,color=p['accent'])
    if progress:
        pct=Decimal(progress['percent'])
        if not pct.is_finite() or not 0<=pct<=100: raise ValueError('invalid engine progress')
        text(86,994,'ความคืบหน้าเงินซื้อสินค้า',25,color=p['muted'])
        text(980,994,str(pct)+'%',25,True)
        draw.rounded_rectangle((86,1038,1114,1058),radius=10,fill=p['track'])
        width=int(Decimal(1028)*pct/100)
        if width: draw.rounded_rectangle((86,1038,86+width,1058),radius=min(10,width//2),fill=p['accent'])
    else:
        text(86,994,'ยังคำนวณความคืบหน้าไม่ได้',25,color=p['muted'])
    draw.line((86,1096,1114,1096),fill=p['line'],width=2)
    text(86,1125,'เหตุผล',27,True)
    y=1172
    for reason in decision['reasons'][:2]:
        y=paragraph(y,reason,25,lines=2)
    next_y=y+35
    text(86,next_y,'ทางเลือกถัดไป',27,True)
    actions=decision['alternative_actions'] or decision['follow_up_questions'] or ['ตรวจงบและเงื่อนไขอีกครั้งก่อนตัดสินใจ']
    next_y+=45
    for action in actions[:2]:
        next_y=paragraph(next_y,action,25,lines=2)
    footer_y=next_y+35
    # Crop unused bottom space, then restore the rounded bottom of the card.
    height=max(footer_y+90,1450)
    if height>1700:
        raise ValueError('decision text exceeds supported card height')
    draw.rectangle((30,height-65,1170,1700),fill=p['bg'])
    draw.rounded_rectangle((30,height-110,1170,height-30),radius=34,fill=p['card'])
    draw.rectangle((30,height-110,1170,height-70),fill=p['card'])
    text(86,footer_y,'สมมติให้เงินเหลือและราคาคงเดิม · ไม่ถอนเงินสำรอง · ไม่ดำเนินการซื้อ',22,color=p['muted'])
    # Footer sits above this reconstructed empty margin.
    im=im.crop((0,0,1200,height))
    output=Path(output)
    if output.suffix.lower()!='.png': raise ValueError('PNG output required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream: im.save(stream,format='PNG')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--theme',choices=PALETTES,default='light')
    parser.add_argument('--demo',action='store_true')
    args=parser.parse_args()
    report=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    render_decision_card(report,args.output,args.theme,args.demo)
