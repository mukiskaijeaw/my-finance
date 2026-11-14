"""Deterministic chat adapter; no LLM, network, transaction or goal writes."""
import re
NUMBER=r'((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?![\d.,])'


def respond(app,payload):
    message=payload.get('message')
    if not isinstance(message,str) or not 0<len(message.strip())<=2000:raise ValueError('กรุณาพิมพ์ข้อความไม่เกิน 2,000 ตัวอักษรครับ')
    text=message.strip();lower=text.casefold();previous=payload.get('context') or {}
    if not isinstance(previous,dict):raise ValueError('invalid_chat_context')
    context={k:str(previous[k])[:200] for k in ('name','price','shipping') if previous.get(k) is not None}
    def answer(reply,kind='message',data=None):return dict(reply=reply,kind=kind,data=data,context=context,mode='LOCAL_RULES_DEMO')
    if lower in ('สวัสดี','hello','hi','หวัดดี','เริ่มใหม่','/new'):
        context.clear();return answer('สวัสดีครับ วันนี้เล็งอะไรไว้? พิมพ์ชื่อสินค้าได้เลย ถ้ามีราคาและค่าส่ง บอกมาด้วย เดี๋ยวช่วยเช็กผลกระทบให้ครับ')
    if any(w in lower for w in ('เงินเหลือ','เหลือเงิน','เช็กงบ','เช็คงบ','งบวันนี้','ใช้เงินได้','/budget')):
        return answer('นี่คืองบจำลองล่าสุดครับ กันภาระและเป้าหมายแล้ว ยังไม่มีการบันทึกรายจ่ายจากแชท','daily',app.state()['daily'])
    if any(w in lower for w in ('ลดรายจ่าย','จับโป๊ะ','รูรั่ว','subscription','spotify','/leaks')):
        data=app.state()['leaks']
        return answer('ยังไม่มีข้อมูลรายจ่ายสำหรับวิเคราะห์ครับ เพิ่มเฉพาะรายการที่คุณมีจริงก่อน ผมจะไม่สมมติหมวดหรือบริการให้เอง' if not data.get('items') else 'ลองปรับเฉพาะรายการที่คุณระบุครับ เงินที่อาจประหยัดยังไม่ใช่เงินสด และไม่ได้แปลว่า Subscription ไหนไม่ได้ใช้','leaks',data)
    goal_match=re.search(r'(?:อยากได้|อยากซื้อ|เก็บเงินซื้อ)\s*(.+?)\s*(?:ก่อน|ภายใน|ให้ทัน)\s*(สิ้นเดือน|สิ้นปี)',text)
    if goal_match and ('กันงบ' in text or 'เก็บเงิน' in text or 'เป้าหมาย' in text):
        from goal_engine import target_day,today_bangkok
        goal=dict(goal_name=goal_match.group(1).strip(),goal_category='purchase',target_date=target_day(goal_match.group(2),today_bangkok()).isoformat(),funding_source='free_cash')
        return answer('ได้ครับ ผมเตรียมเป้าหมายให้แล้ว ขอราคาหรือยอดเป้าหมายและยอดที่เก็บไว้จริงก่อนตรวจแผน ยังไม่บันทึกจนกว่าคุณยืนยันครับ','goal_draft',goal)
    if any(w in lower for w in ('เป้าหมาย','เก็บเงิน','แผนออม','/goals')):
        return answer('ดูหรือสร้างแผนต่อได้ครับ การพิมพ์อย่างเดียวจะยังไม่บันทึกเป้าหมาย','goals',app.state()['goals'])
    if any(w in lower for w in ('ไปเที่ยว','วางแผนเที่ยว','ทริป','/travel')):
        return answer('ในหน้าวางแผนเที่ยว ใส่ต้นทาง ปลายทาง วันที่ จำนวนวัน/คืน คน และงบแต่ละหมวด แล้วผมจะคำนวณให้ครับ','travel_setup')
    if lower in ('ขอบคุณ','ขอบคุณครับ','โอเค','ok','ได้เลย'):return answer('ได้ครับ ส่งตัวเลือกใหม่มาได้ แต่ผมจะไม่ซื้อหรือบันทึกแผนจนกว่าคุณยืนยันครับ')
    if lower in ('ยืนยัน','ยืนยันซื้อเลย','ซื้อเลย','ตกลงซื้อ'):return answer('หน้านี้ไม่สั่งซื้อให้อัตโนมัติครับ ถ้าจะเริ่มเก็บเงิน ให้กดวางแผนและตรวจข้อมูลก่อนยืนยันในหน้าที่แสดง')
    budget_only=bool(re.search(r'(งบ|ไม่เกิน|งบประมาณ)\s*'+NUMBER,text)) and 'ราคา' not in text
    price=re.search(r'(?:ราคา|ชิ้นละ|คู่ละ)\s*'+NUMBER,text)
    shipping=re.search(r'(?:ค่าส่ง|ค่าจัดส่ง|ส่ง)\s*'+NUMBER,text)
    if re.search(r'(?:ราคา|ชิ้นละ|คู่ละ)\s*\d',text) and not price:raise ValueError('รูปแบบราคาไม่ถูกต้องครับ เช่น 2500 หรือ 2,500.00')
    if re.search(r'(?:ค่าส่ง|ค่าจัดส่ง|ส่ง)\s*\d',text) and not shipping:raise ValueError('รูปแบบค่าจัดส่งไม่ถูกต้องครับ')
    free=bool(re.search(r'(?:ส่งฟรี|ฟรีค่าส่ง|ค่าส่งฟรี|ค่าส่ง\s*0(?:\s|บาท|$))',text))
    starts=re.match(r'^\s*'+NUMBER+r'(?:\s*บาท)?(?:\s|$)',text)
    if not budget_only and price:context['price']=price.group(1).replace(',','')
    elif not budget_only and starts and context.get('name'):context['price']=starts.group(1).replace(',','')
    if shipping:context['shipping']=shipping.group(1).replace(',','')
    if free:context['shipping']='0'
    named=re.sub(r'^(?:อยากซื้อ|อยากได้|ช่วยดู|ซื้อ)\s*','',text)
    named=re.split(r'(?:ราคา|ชิ้นละ|คู่ละ|ค่าส่ง|ค่าจัดส่ง|ส่งฟรี|งบ(?:ประมาณ)?|ไม่เกิน)',named,maxsplit=1)[0].strip(' ,:')
    followup=bool(price or shipping or free or starts)
    if named and not re.fullmatch(r'[\d,.\s]+(?:บาท)?',named) and (not followup or price and not starts):
        if named!=context.get('name'):
            context={'name':named[:200]}
            if price and not budget_only:context['price']=price.group(1).replace(',','')
            if shipping:context['shipping']=shipping.group(1).replace(',','')
            if free:context['shipping']='0'
    if not context.get('name'):return answer('อยากประเมินสินค้าอะไรครับ? บอกชื่อรุ่นก่อน แล้วตามด้วยราคาและค่าส่งที่ทราบได้เลย')
    if any(w in lower for w in ('หาราคา','ร้านไหน','ถูกสุด','ราคาเท่าไหร่','ไม่รู้ราคา')):
        return answer('หน้าแชทบนเครื่องยังค้นหาราคาสดเองไม่ได้ครับ ใช้ Codex Chat ช่วยค้น '+context['name']+' แล้วนำราคากับค่าส่งกลับมาประเมินได้ ผมจะไม่แต่งราคาให้')
    missing=[]
    if 'price' not in context:missing.append('ราคาสินค้า')
    if 'shipping' not in context:missing.append('ค่าจัดส่ง (ถ้าฟรีบอกว่าส่งฟรี)')
    if missing:return answer('เล็ง '+context['name']+' ไว้ใช่ไหมครับ? ขอ '+' และ '.join(missing)+' เพื่อเช็กงบให้ตรงยอดจ่ายจริง'+(' งบเป็นเพดาน จึงยังใช้แทนราคาสินค้าไม่ได้ครับ' if budget_only else ''))
    if budget_only:return answer('งบที่บอกเป็นเพดานครับ ผมยังไม่เปลี่ยนราคาสินค้าที่คุยไว้ หากต้องการจำลองราคาใหม่ พิมพ์ว่า ราคา ตามด้วยจำนวนเงินได้เลย')
    result=app.purchase(context)
    reply={'AFFORDABLE':'ยอดนี้อยู่ในงบจำลองครับ แต่ยังต้องเช็กรุ่น การใช้งาน และร้านค้า ไม่ใช่ไฟเขียวให้ซื้ออัตโนมัติ','SAVE_FIRST':'งบตอนนี้ยังไม่ถึงครับ ลองวางแผนเก็บเงินหรือดูตัวเลือกที่ถูกลงก่อน','NOT_AFFORDABLE':'ยอดนี้กระทบแผนครับ ยังไม่ควรใช้เงินส่วนที่กันไว้','INSUFFICIENT_DATA':'ข้อมูลยังไม่พอสรุปซื้อไหวครับ ตรวจแผนและภาระก่อน'}[result['financial']['status']]
    return answer(reply,'purchase',result)
