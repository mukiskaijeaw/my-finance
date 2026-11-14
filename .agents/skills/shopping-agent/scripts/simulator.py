"""Precompute finite slider states using the unchanged local finance engine.

The UI only selects a state; no financial formulas, LLM or network on input.
"""
import argparse
import json
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from engine import financial_fit, money


def demo_profile(current_day):
    fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/simulator.json').read_text(encoding='utf-8'))
    return dict(fixture['profile'],as_of=current_day.isoformat())


def currency(value):
    if value is None: return 'ยังประเมินไม่ได้'
    n=Decimal(str(value))
    return '฿'+format(n,',.0f' if n==n.to_integral_value() else ',.2f')


def compute_state(profile, price, safety_buffer, current_day):
    fit=financial_fit(profile,price,current_day)
    price=money(price);buffer=money(safety_buffer)
    if fit['status']=='INSUFFICIENT_DATA' or fit.get('available') is None:
        return {'price':str(price),'priceText':currency(price),'demoFinancialStatus':'INSUFFICIENT_DATA',
                'title':'ข้อมูลยังไม่เพียงพอ','explanation':'ยืนยันข้อมูลก่อนประเมิน ไม่แทนข้อมูลที่ขาดด้วยศูนย์',
                'availableMoney':None,'remainingMoney':None,'spendingPercentage':None,'progressBarWidth':None,
                'shortfall':None,'engineFinancialFit':fit['status'],'issues':fit['issues']}
    available=Decimal(fit['available']);remaining=Decimal(fit['remaining_after_purchase'])
    ratio=Decimal(fit['spending_percent']) if fit['spending_percent'] is not None else None
    # Savings-plan earmarking is not the same as the cash shortfall in this view.
    gap=str(max(Decimal(0),-remaining))
    # Demo-only visual buffer policy, separate from the engine's four fit states.
    if remaining<0:
        status='WAIT_AND_SAVE';title='แนะนำให้รอเก็บเงินก่อน'
        explanation='ยังขาดเงินอีก '+format(Decimal(gap),',.0f')+' บาท ไม่ควรนำเงินสำรองฉุกเฉินมาใช้ซื้อ'
    elif remaining<buffer:
        status='BUY_WITH_CAUTION';title='ซื้อได้ แต่ควรระมัดระวัง'
        explanation='เงินพร้อมใช้หลังซื้อเหลือน้อยกว่าเงินเผื่อที่กำหนด'
    else:
        status='AFFORDABLE';title='ซื้อได้ตามแผนการเงิน'
        explanation='ไม่กระทบเงินออมที่กันไว้และภาระที่ระบุในข้อมูลจำลอง'
    if fit['status']=='NOT_AFFORDABLE':
        status='WAIT_AND_SAVE';title='แนะนำให้รอเก็บเงินก่อน'
        explanation='กระแสเงินสดหรือเงินที่ต้องคุ้มครองยังไม่ผ่านเกณฑ์ของ engine'
    return dict(price=str(price),priceText=currency(price),availableMoney=str(available),availableText=currency(available),
                remainingMoney=str(remaining),remainingText=currency(remaining),shortfall=gap,
                spendingPercentage=str(ratio.quantize(Decimal('.1'),rounding=ROUND_HALF_UP)) if ratio is not None else None,
                progressBarWidth=str(min(ratio,Decimal(100))) if ratio is not None else None,
                demoFinancialStatus=status,title=title,explanation=explanation,engineFinancialFit=fit['status'],issues=[])


def build_payload(profile, product, current_day, safety_buffer=None, minimum=None, maximum=None, step=None, demo_mode=True):
    if demo_mode is not True:
        raise ValueError('This MVP simulator is demo-only; real financial data must not enter UI previews')
    if not isinstance(product,dict):raise ValueError('product required')
    initial=money(product.get('productPrice'))
    if safety_buffer is None:safety_buffer=profile.get('safety_buffer')
    money(safety_buffer)
    if minimum is None and maximum is None and step is None:
        step=max(1,int(initial)//100)
        minimum=int(initial)%step
        maximum=minimum+step*200
    if not all(type(v) is int for v in (minimum,maximum,step)) or not 0<=minimum<maximum or step<=0 or (maximum-minimum)%step or (maximum-minimum)//step>1000:
        raise ValueError('invalid or excessively large slider grid')
    if not isinstance(product,dict) or not isinstance(product.get('productName'),str) or not product['productName'].strip():
        raise ValueError('productName required')
    if initial<minimum or initial>maximum or (initial-minimum)%step:
        raise ValueError('initial price must be on the slider grid')
    if profile.get('earmarked') is not None and money(profile['earmarked'])!=0:
        raise ValueError('spending simulator requires unearmarked available cash')
    image=product.get('productImageUrl')
    if image:
        u=urlsplit(image)
        if u.scheme!='https' or not u.netloc or u.username or u.password or product.get('imageVerified') is not True or not product.get('imageSource'):
            raise ValueError('verified HTTPS product image and provenance required')
        source=urlsplit(product['imageSource'])
        if source.scheme!='https' or not source.netloc or source.username or source.password:
            raise ValueError('HTTPS image provenance required')
    states={str(price):compute_state(profile,str(price),safety_buffer,current_day) for price in range(minimum,maximum+1,step)}
    return dict(schemaVersion=1,productName=product['productName'],productImageUrl=image or None,
                imageSource=product.get('imageSource') if image else None,productPrice=str(initial),
                availableMoney=states[str(int(initial))]['availableMoney'],safetyBuffer=str(money(safety_buffer)),
                currency='THB',demoMode=True,slider=dict(minimum=minimum,maximum=maximum,step=step),states=states,
                assumptions=['ข้อมูลจำลองที่ระบุในคำขอ ไม่ใช่ยอดเงินจริง',
                    'กันเงินฉุกเฉิน reserved และภาระตามข้อมูลครั้งเดียว',
                    'Safety buffer เป็นเกณฑ์ภาพจำลอง ไม่เปลี่ยน Financial Fit หรือ Final Recommendation หลัก'])


def render_html(payload):
    template=Path(__file__).resolve().parents[1]/'assets/simulator.html'
    raw=template.read_text(encoding='utf-8')
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return raw.replace('__SIMULATOR_PAYLOAD__',encoded)


def write_preview(payload,output):
    raw=render_html(payload)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: stream.write(raw)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--product-name',required=True)
    parser.add_argument('--price',required=True)
    parser.add_argument('--input',required=True,help='Explicit synthetic profile, buffer and slider configuration JSON')
    args=parser.parse_args()
    from shopping import today
    config=json.loads(Path(args.input).read_text(encoding='utf-8'))
    if config.get('synthetic') is not True:raise ValueError('explicit synthetic input required')
    write_preview(build_payload(config['profile'],dict(productName=args.product_name,productPrice=args.price),today(),
                  safety_buffer=config['safety_buffer'],**config['slider']),args.output)
