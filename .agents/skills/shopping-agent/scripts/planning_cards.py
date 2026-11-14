"""Markdown-only response templates. No HTML and no recalculation of metrics."""
import json

TITLES = {'budget': 'Smart Budget', 'fit': 'Financial Fit', 'opportunity': 'Opportunity Cost',
          'installment': 'Payment Comparison', 'readiness': 'Purchase Goal', 'what_if': 'What-if Analysis'}

ASSUMPTIONS = {
    'budget': 'เงินเผื่อเป็นยอดที่ผู้ใช้ยืนยัน กันบิลก่อนรายรับครั้งถัดไปและภาระอนาคตที่ระบุไว้ ไม่หักบิลที่จ่ายแล้วหรือกันไว้ซ้ำ',
    'fit': 'กันเงินสำรอง เงินเผื่อ และบิลที่ยืนยันก่อนซื้อ แผนออมใช้เงินเหลือต่อเดือนคงเดิม ภาระ future_extra กันเต็มยอดล่วงหน้า ราคาและรายได้อาจเปลี่ยน',
    'opportunity': 'ใช้เฉพาะแหล่งเงินที่ระบุ ไม่แตะเงินฉุกเฉิน ไม่สมมติผลตอบแทน การย้ายเงินออมเป็นเพียงสถานการณ์ ไม่เปลี่ยนเป้าหมายจริง',
    'installment': 'ตรวจข้อมูลครบทุกงวด ค่าธรรมเนียมจ่ายครั้งเดียวตอนเริ่ม ภาระเดิมอยู่ในรายจ่ายแล้ว ค่างวดจ่ายก่อนรายรับอย่างระมัดระวัง 0% ยังอาจมีต้นทุนอื่น',
    'readiness': 'เงินกันจริงเป็นส่วนหนึ่งของเงินสดเดิม เงินที่วางแผนเก็บยังไม่ใช่เงินสด วันที่คาดการณ์สมมติว่ารับเงินรายเดือนวันเดิม ตรวจใหม่เฉพาะเมื่อกลับมาถาม',
    'what_if': 'คำนวณบนสำเนาตามตัวแปรสมมติ ไม่แก้ข้อมูลจริงหรือบันทึกรายจ่าย ผลขึ้นอยู่กับความครบถ้วนของข้อมูลทั้งสองสถานการณ์'}


def render_planning(request, result):
    from shopping import table, cell, amount, STATUS
    status = result['status']
    lines = ['## ' + TITLES.get(request.get('action'), 'Financial Planning'), '',
             '**' + STATUS.get(status, 'SIMULATION — ข้อมูลจำลองสถานการณ์') + '**', '']
    if status == 'INSUFFICIENT_DATA':
        return '\n'.join(lines + ['**ต้องยืนยันข้อมูล:** ' + cell(', '.join(result.get('issues', []))),
                                  'ยังไม่สรุปว่าซื้อไหว ไม่แทนข้อมูลที่ขาดด้วย 0'])
    action = request.get('action')
    if action == 'budget':
        lines += ['### งบแนะนำ ' + amount(result['recommended_budget']), '',
                  table(['งบผู้ใช้', 'งบซื้อไหวสูงสุด', 'เงินเผื่อที่ยืนยัน'],
                        [[amount(result['user_budget']), amount(result['affordable_budget']), amount(result['minimum_remaining'])]]),
                  '', '### Upcoming Expenses', '',
                  table(['ยอดเงินปัจจุบัน', 'กันเพิ่มสำหรับบิล', 'เงินพร้อมใช้ก่อนเผื่อ'],
                        [[amount(result['current_balance']), amount(result['upcoming_additional']), amount(result['available_spending_cash'])]]),
                  'ประเมินถึงรายรับครั้งถัดไป: ' + cell(result['cycle_end'])]
        if result['obligations']:
            lines += [table(['รายการ', 'ครบกำหนด', 'ยอด', 'สถานะ', 'กันเพิ่ม'],
                           [[cell(x['id']), cell(x['due']), amount(x['amount']), cell(x['state']), amount(x['additional_reserve'])] for x in result['obligations']])]
        if result['budget_conflict']:
            lines += ['**งบต่างกัน:** งบเดิมสูงกว่างบแนะนำ ' + amount(result['budget_difference']),
                      'ค้นตัวเลือกที่ตรงความต้องการในงบแนะนำก่อน พร้อมเสนอรุ่นในงบเดิมและผลกระทบ ให้ผู้ใช้ตัดสินใจ']
    elif action == 'fit':
        lines += ['### เงินพร้อมใช้ ' + amount(result.get('available')), '',
                  table(['ราคาสุทธิ', 'เหลือต่อเดือน', 'เงินหลังซื้อ', 'เก็บเพิ่ม (เดือน)'],
                        [[amount(request.get('price')), amount(result.get('monthly_surplus')), amount(result.get('remaining_after_purchase')), cell(result.get('months'))]])]
        p = result.get('savings_progress')
        if p:
            lines += ['**Savings Progress:** `' + '█' * p['filled_segments'] + '░' * (10 - p['filled_segments']) + '` ' + p['percent'] + '%']
    elif action == 'opportunity':
        lines += [table(['เป้าหมาย', 'ไม่ซื้อ: เดือนถึงเป้า', 'ซื้อ: เดือนถึงเป้า', 'ล่าช้า (เดือน)', 'เงินออมลดลง'],
                        [[cell(x['id']), cell(x['before_months']), cell(x['after_months']), cell(x['delay_months']), amount(x['savings_reduced'])] for x in result['scenarios']]),
                  'กระแสเงินสดเปลี่ยนทันที: ' + amount(result['scenario_b_cash_change']),
                  'กระแสเงินสดรายเดือนเปลี่ยน: ' + amount(result['monthly_cashflow_change'])]
    elif action == 'installment':
        lines += [table(['จ่ายสดทั้งหมด', 'ผ่อนรวมทั้งหมด', 'ส่วนต่างต้นทุน', 'ค่าธรรมเนียม', 'ดอกเบี้ยรวม'],
                        [[amount(result[k]) for k in ('cash_total', 'installment_total', 'additional_cost', 'fees', 'interest_total')]]),
                  '**ผลซื้อสด:** ' + STATUS[result['cash_fit']['status']],
                  table(['เดือน', 'ค่างวด', 'ก่อนรับรายได้', 'เงินหลังจ่าย', 'เหลือต่อเดือน', 'เงินคุ้มครอง'],
                        [[cell(x['month'])] + [amount(x[k]) for k in ('payment', 'cash_before_income', 'cash_after', 'monthly_remaining', 'protected_floor')] for x in result['schedule']])]
    elif action == 'readiness':
        lines += [table(['เป้าหมาย', 'ราคาล่าสุด', 'กันไว้จริง', 'ขาดอีก', 'เดือน', 'วันที่ประมาณ', 'สถานะ'],
                        [[cell(x['id']), amount(x['latest_verified_price']), amount(x['allocated_savings']), amount(x['remaining']), cell(x['months']), cell(x['estimated_purchase_date']), STATUS[x['status']]] for x in result['goals']])]
    elif action == 'what_if':
        lines += ['**HYPOTHETICAL — สมมติฐาน ไม่ใช่ข้อมูลจริงที่เปลี่ยนแล้ว**',
                  table(['สถานการณ์', 'ผลประเมิน', 'เงินพร้อมใช้', 'เหลือต่อเดือน', 'เก็บเพิ่ม (เดือน)'],
                        [[name, STATUS[result[key]['status']], amount(result[key].get('available')), amount(result[key].get('monthly_surplus')), cell(result[key].get('months'))] for name, key in [('ข้อมูลจริง', 'actual'), ('ข้อมูลสมมติ', 'hypothetical')]])]
    advice = {'AFFORDABLE': 'ซื้อได้ภายใต้ข้อมูลที่ยืนยัน ตรวจความจำเป็นและเงื่อนไขร้านอีกครั้ง',
              'SAVE_FIRST': 'แนะนำรอเก็บเงิน หรือพิจารณารุ่นที่ตรงความต้องการในงบต่ำลง',
              'NOT_AFFORDABLE': 'ไม่แนะนำตอนนี้ เพราะแผนนี้ยังคุ้มครองสภาพคล่องไม่ได้',
              'SIMULATION': 'เปรียบเทียบผลสองสถานการณ์ก่อนตัดสินใจ ข้อมูลจริงยังคงเดิม'}
    lines += ['', '**คำแนะนำ:** ' + advice.get(status, 'ยืนยันข้อมูลก่อนตัดสินใจ'),
              '**สมมติฐานและข้อจำกัด:** ' + ASSUMPTIONS.get(action, 'ตรวจสอบข้อมูลที่ยืนยันก่อนตัดสินใจ'),
              'คำนวณในเครื่อง ไม่มีการสั่งซื้อ บันทึกรายจ่าย หรือเฝ้าติดตามเบื้องหลัง']
    return '\n'.join(lines)
