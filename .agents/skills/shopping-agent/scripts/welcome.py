"""Native selection data and routes; no financial reads or product search."""
TITLE='วันนี้อยากปรึกษาเรื่องเงินอะไร?'
DESCRIPTION='ผู้ช่วยทางการเงินที่เข้าใจแผนการใช้เงินของคุณ'
TRIGGERS=('/shopping-agent','/ shopping-agent','/shopping','shopping agent','เริ่ม shopping agent')
CHOICES=(
 ('💰','วันนี้ยังใช้เงินได้อีกเท่าไหร่','daily_spending',('companion',)),
 ('🛍️','อยากซื้อของชิ้นหนึ่ง ควรซื้อไหม','purchase_decision',('decision','fit')),
 ('🎯','วางแผนและติดตามสิ่งที่อยากได้','savings_goal',('goals',)),
 ('🔎','เงินหายไปกับอะไรโดยไม่รู้ตัว','money_leaks',('companion',)),
 ('✈️','อยากไปเที่ยวที่ไหน ต้องเตรียมเงินเท่าไหร่','travel_budget',('companion',)))


def is_trigger(text):
    return isinstance(text,str) and text.strip().casefold() in TRIGGERS


def native_question(max_options=8):
    if type(max_options) is not int or max_options<2:
        raise ValueError('native selection requires at least two options')
    if max_options>=len(CHOICES):
        options=[icon+' '+description for icon,description,*_ in CHOICES]
    else:
        options=['เช็กเงินคงเหลือ / จับโป๊ะรายจ่าย','ตัดสินใจซื้อของ','เป้าหมายของฉัน / วางแผนเที่ยว'][:max_options]
        if max_options==2:options=['เช็กเงินคงเหลือ / จับโป๊ะรายจ่าย','ตัดสินใจซื้อของ / เป้าหมายของฉัน / วางแผนเที่ยว']
    return {'questions':[{'title':TITLE+'\n'+DESCRIPTION,'options':options}]}


def route_answer(text):
    if not isinstance(text,str):raise ValueError('selection must be text')
    legacy={'💰 เดือนนี้เหลือเงินใช้ได้อีกเท่าไหร่':'monthly_overview','ซื้อสดกับผ่อน แบบไหนเหมาะกับฉัน':'installment','มี Subscription อะไรที่ควรยกเลิกไหม':'subscriptions'}
    if text.strip() in legacy:return dict(description=text,intent=legacy[text.strip()],tools=[],financial_data_required=True,clarification_required=False,record_transaction=False)
    for icon,description,intent,tools in CHOICES:
        if text.strip() in (description,icon+' '+description):
            return dict(description=description,intent=intent,tools=list(tools),financial_data_required=True,
                        clarification_required=False,record_transaction=False)
    return dict(description=text,intent='free_text',tools=[],financial_data_required=None,
                clarification_required=True,record_transaction=False)
