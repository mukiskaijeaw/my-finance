"""Deterministic recommendation policy over financial results and sourced facts.

No money calculations, data access, product search or model calls.
"""
POLICY_VERSION = '1.0'
LABELS = {'BUY_NOW': 'ซื้อได้ตามแผน', 'BUY_WITH_CAUTION': 'ซื้อได้ แต่ควรพิจารณาอีกครั้ง',
          'WAIT_AND_SAVE': 'แนะนำรอเก็บเงิน', 'CHOOSE_ALTERNATIVE': 'แนะนำทางเลือกที่เหมาะกว่า',
          'SKIP_PURCHASE': 'เก็บเงินไว้ตามความตั้งใจของคุณ', 'NEED_MORE_INFO': 'ยังต้องยืนยันข้อมูล'}
ALTERNATIVES = {'repair': 'ตรวจราคาซ่อมของเดิม', 'use_current': 'ใช้ของเดิมต่อ', 'borrow': 'ยืมใช้งาน',
                'rent': 'เช่าใช้งาน', 'buy_used': 'พิจารณามือสอง', 'cheaper': 'เลือกรุ่นที่ราคาต่ำกว่า'}


def fact(context, key):
    item = context.get(key)
    if isinstance(item, dict) and isinstance(item.get('source'), str) and item['source'].strip():
        return item.get('value')
    return None


def recommend(financial, context, alternatives=None):
    """Unknown purpose/value never becomes a high necessity score or BUY_NOW."""
    if not isinstance(context, dict) or not isinstance(financial, dict):
        raise ValueError('financial and context must be objects')
    fit = financial.get('status', 'INSUFFICIENT_DATA')
    facts = {key: fact(context, key) for key in ('purpose', 'necessity', 'timing', 'value_suitable',
        'planned', 'promotion', 'prefer_skip', 'current_usable', 'repair_possible', 'borrow_possible',
        'secondhand_acceptable', 'offer_ready')}
    reasons, actions, questions, missing = [], [], [], []
    viable = []
    for item in alternatives or []:
        if item.get('action') not in ALTERNATIVES:
            raise ValueError('unsupported alternative action')
        if item.get('financial', {}).get('status') == 'AFFORDABLE' and fact(item, 'suitable') is True:
            viable.append({'id': item['id'], 'action': item['action'], 'label': ALTERNATIVES[item['action']],
                           'financial_fit': 'AFFORDABLE'})
    if facts['prefer_skip'] is True:
        final = 'SKIP_PURCHASE'
        reasons.append('คุณระบุว่าต้องการเก็บเงินไว้ จึงไม่จำเป็นต้องค้นสินค้าหรือซื้อเพิ่ม')
    elif fit not in ('AFFORDABLE', 'SAVE_FIRST', 'NOT_AFFORDABLE'):
        final = 'NEED_MORE_INFO'
        reasons.append('ข้อมูลการเงินหรือราคาสุทธิยังไม่ครบ จึงยังไม่ตัดสินว่าควรซื้อ')
        missing.extend(financial.get('issues') or ['financial_fit_required'])
        questions.append('ขอยืนยันเฉพาะข้อมูลการเงินหรือราคาสุทธิที่ยังขาดก่อนนะครับ')
    elif facts['necessity'] not in ('required', 'wanted', 'not_needed') or not isinstance(facts['purpose'], str) or not facts['purpose'].strip():
        final = 'NEED_MORE_INFO'
        reasons.append('ซื้อไหวกับควรซื้อเป็นคนละเรื่อง ยังไม่ทราบวัตถุประสงค์ที่อาจเปลี่ยนคำแนะนำ')
        missing.append('purpose_and_necessity')
        questions.append('ต้องใช้ทำอะไร และของเดิมยังใช้งานได้ไหมครับ?')
    elif facts['value_suitable'] is False:
        final = 'CHOOSE_ALTERNATIVE' if viable else 'NEED_MORE_INFO'
        reasons.append('ตัวเลือกนี้ไม่ตรงข้อกำหนดการใช้งานที่ยืนยัน แม้จ่ายไหวก็ไม่ควรเลือกจากราคาอย่างเดียว')
        if not viable:
            questions.append('ข้อกำหนดใดที่ตัวเลือกใหม่ต้องมีครับ?')
    elif fit in ('SAVE_FIRST', 'NOT_AFFORDABLE'):
        if facts['timing'] == 'urgent' and viable:
            final = 'CHOOSE_ALTERNATIVE'
            reasons.append('ต้องใช้เร็ว แต่ตัวเลือกเดิมยังไม่ผ่านแผนการเงิน มีทางเลือกที่ตรงการใช้งานและซื้อไหว')
        else:
            final = 'WAIT_AND_SAVE'
            reasons.append('ราคาหรือภาระยังเกินเงินที่ใช้ซื้อได้ โดยไม่ถอนเงินสำรองหรือเปลี่ยนเป้าหมายเดิม')
            if fit == 'NOT_AFFORDABLE':
                actions.append('ทบทวนภาระและกระแสเงินสดก่อน ยังระบุวันซื้อที่ปลอดภัยไม่ได้')
            elif financial.get('months') is not None:
                actions.append('เก็บเงินตามแผนประมาณ ' + str(financial['months']) + ' เดือน แล้วตรวจราคาและงบใหม่')
    elif facts['offer_ready'] is not True or facts['value_suitable'] is not True:
        final = 'NEED_MORE_INFO'
        reasons.append('เงินพอตามแผน แต่ยังไม่ยืนยันว่าตรงการใช้งาน รุ่น ตัวเลือก และเงื่อนไขซื้อพร้อม')
        missing.append('offer_readiness_or_value')
        questions.append('ขอยืนยันตัวเลือกและความเหมาะสมกับการใช้งานก่อนสรุปซื้อครับ')
    elif facts['necessity'] == 'required' and facts['planned'] is True and facts['promotion'] is not True:
        final = 'BUY_NOW'
        reasons.append('ซื้อไหว อยู่ในแผนเดิม จำเป็นต่อวัตถุประสงค์ที่ระบุ และตัวเลือกตรงการใช้งาน')
        actions.append('ตรวจยอดเช็คเอาท์และสต็อกอีกครั้ง แล้วให้คุณเป็นผู้ตัดสินใจซื้อ')
    else:
        final = 'BUY_WITH_CAUTION'
        reasons.append('ซื้อไหวตามข้อมูลที่ยืนยัน แต่ยังควรชั่งประโยชน์กับเงินที่จะจ่ายและความสำคัญของเป้าหมายอื่น')
    if facts['promotion'] is True:
        reasons.append('โปรโมชันเป็นเงื่อนไขราคา ไม่ใช่เหตุผลว่าจำเป็นต้องซื้อหรือประหยัดเสมอไป')
    if facts['current_usable'] is True:
        actions.append('ใช้ของเดิมต่อระหว่างพิจารณาหรือเก็บเงิน')
    if facts['repair_possible'] is True:
        actions.append('ขอราคาซ่อมของเดิมก่อนตัดสินใจ ไม่ถือว่าซ่อมถูกกว่าจนกว่าจะมีราคา')
    if facts['borrow_possible'] is True:
        actions.append('พิจารณายืมตามทางเลือกที่คุณระบุ โดยยืนยันเงื่อนไขก่อน')
    if facts['secondhand_acceptable'] is True:
        actions.append('เปรียบเทียบมือสองที่ตรวจสภาพและเงื่อนไขได้ก่อน')
    actions.extend(item['label'] for item in viable)
    return {'policy_version': POLICY_VERSION, 'financial_fit': fit, 'recommendation': final,
            'label': LABELS[final], 'reasons': reasons, 'alternative_actions': list(dict.fromkeys(actions)),
            'verified_alternatives': viable, 'follow_up_questions': questions[:1], 'missing': missing,
            'assessment': {'affordability': fit,
                           'necessity': facts['necessity'] if facts['necessity'] in ('required','wanted','not_needed') else 'unknown',
                           'purpose': facts['purpose'], 'value': facts['value_suitable'], 'timing': facts['timing'],
                           'financial_impact': financial.get('goal_impact', 'unknown')},
            'notice': 'คำแนะนำตามกฎและข้อมูลที่ยืนยัน ไม่ซื้อ บันทึกธุรกรรม หรือเปลี่ยนเป้าหมายแทนคุณ'}


def evaluate_decision(profile, request, today):
    """Reuse cycle-aware engine; alternative costs must be confirmed first."""
    from planning import fit
    options = request.get('budget', {})
    price = request.get('price') if request.get('price_confirmed') is True and request.get('price_source') else None
    financial = fit(profile, price, options, today)
    alternatives = []
    for item in request.get('alternatives', []):
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            raise ValueError('alternative id required')
        cost = item.get('price') if item.get('price_confirmed') is True and item.get('price_source') else None
        alternatives.append({**item, 'financial': fit(profile, cost, options, today)})
    decision = recommend(financial, request.get('context', {}), alternatives)
    return {'financial': financial, 'decision': decision, 'price': price}


def render_decision(report):
    """Text accessibility fallback; selected primary UI is a rendered PNG."""
    from shopping import amount, cell, table
    f, r = report['financial'], report['decision']
    lines = ['## ' + r['label'], '', '**' + r['recommendation'] + '** · Financial Fit: ' + r['financial_fit'], '',
             table(['ราคาสุทธิ','เงินพร้อมใช้','ต้องเก็บเพิ่ม','เหลือต่อเดือน','เก็บเพิ่ม (เดือน)'],
                   [[amount(report.get('price')),amount(f.get('available')),amount(f.get('savings_progress',{}).get('remaining')),amount(f.get('monthly_surplus')),cell(f.get('months'))]]), '',
             '**เหตุผล:** ' + ' '.join(r['reasons'])]
    if r['alternative_actions']:
        lines += ['', '**ทางเลือก:** ' + '; '.join(r['alternative_actions'])]
    if r['follow_up_questions']:
        lines += ['', r['follow_up_questions'][0]]
    return '\n'.join(lines + ['', r['notice']])
