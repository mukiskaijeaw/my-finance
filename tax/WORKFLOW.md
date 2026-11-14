# Local finance review workflow

Core รุ่นแรกเชื่อม Pillar 1 → Pillar 3 และค้นหา candidate สำหรับ Pillar 5 ใช้ Python 3.9+ standard library เท่านั้น เขียนขึ้นใหม่จากโจทย์ของ workspace ไม่ได้คัดโค้ดจาก repo ที่ค้น

## ใช้งาน

ในโฟลเดอร์ my-finance วิธีที่ง่ายที่สุดคือ `python3 agent/cli.py tax` (รัน scan แล้วแสดง report) และ `python3 agent/cli.py dashboard` จะใส่ผลตรวจลงหน้า Tax ให้ หรือรันจากโฟลเดอร์ `tax/` โดยระบุ workspace ที่เก็บบัญชีจริง:

```sh
python3 -m finance_core --workspace /path/to/finance scan
python3 -m finance_core --workspace /path/to/finance report
python3 -m finance_core --workspace /path/to/finance review TASK-xxxxxxxxxxxxxxxx --note 'คำอธิบายที่ผู้ใช้ยืนยัน'
```

`database.csv` ใช้ schema 11 คอลัมน์ของ Pillar 1 หรือ 14 คอลัมน์ (มี `model,token_input,token_output`) ก็ได้ `tax_preparation.csv` ต้องมี schema ตาม AGENTS.md ถ้ายังไม่มีไฟล์นี้ ระบบถือว่ายังไม่มีรายการภาษี ระบบไม่เขียนสองไฟล์นี้ ผลตรวจและ audit อยู่ใน `finance_review.json` ของ workspace รายงานเป็นข้อมูลส่วนตัว เก็บในเครื่องเท่านั้น `report` จะ scan ล่าสุดก่อนแสดงผลด้วย

รายงานแสดงงานสำคัญก่อน จำกัดรายละเอียดเริ่มต้น 20 งาน ใช้ `report --limit 100` เพื่ออ่านเพิ่ม ธงคุณภาพจากข้อมูลนำเข้าเดิมเป็นข้อสังเกตชวนตรวจ ไม่ใช่ข้อยืนยันว่ารายการผิด; อย่าถามผู้ใช้ทุกงานพร้อมกัน

หลังแก้รายการเดิมหรือเพิ่มเอกสาร ให้ scan อีกครั้ง งานที่ข้อมูลเปลี่ยนจะกลับเป็น `open`; งานที่ปัญหาหายไปจะเป็น `resolved`; `reviewed` หมายถึงมีบันทึกคำตอบ ไม่ใช่ยืนยันยอดภาษีหรือสิทธิหักลดหย่อน รายงานยังแสดงงาน reviewed อยู่ การรันซ้ำด้วยข้อมูลเดิมไม่เพิ่มงานหรือ audit scan ซ้ำ

ทุกงานมีรหัสคงที่ตามปัญหา, transaction IDs, แหล่งเอกสาร, เหตุผล, คำถาม และ fingerprint ข้อมูล ข้อมูลวิกฤตผิด schema/วันที่/ยอด จะหยุดก่อนเขียนผล scan ใหม่ ไฟล์ state ใช้ atomic replace และ CLI มี lock กันสองคำสั่งเขียนพร้อมกัน หากโปรเซสถูก kill อาจมี `.finance_review.lock` ค้าง ให้ตรวจว่าไม่มีโปรเซสรันแล้วก่อนลบ lock และลองใหม่

## เอกสารเงินเดือน

คัดลอก `tax/finance_evidence.example.json` เป็น `finance_evidence.json` ภายใน workspace แล้วใส่เฉพาะข้อมูลที่อ่านและตรวจจากหลักฐานแล้ว โครงสร้างตัวอย่างอยู่ที่ `examples/review_demo/finance_evidence.example.json`

- `transaction_ids`: ระบุรายการเงินเดือนที่เอกสารครอบคลุมจริง ไม่จับคู่ทั้งปีโดยเดา
- `tax_year`: ปี พ.ศ. ต้องตรงกับวันที่ธุรกรรม
- `gross_income_thb`: ยอดก่อนหักตามเอกสาร
- `withholding_thb`: ภาษีที่หักจริงในขอบเขตเดียวกัน
- `other_withheld_thb`: รวมรายการหักอื่นในขอบเขตเดียวกันตามหลักฐาน ต้องทราบจริงก่อนกรอก แม้เป็นศูนย์
- `source_reference`: ที่มาหรือไฟล์ในเครื่อง หลีกเลี่ยงข้อมูลบัญชีเต็มหรือ credentials

เทียบ `gross − withholding − other withheld` กับยอดเงินเข้าที่ลิงก์ไว้ ความตรงกันทางเลขไม่ยืนยันความครบถ้วนของปีภาษีหรือสิทธิใด ๆ ระบบไม่สร้างรายการลดหย่อนจากยอดหักเงินเดือน และไม่แก้เงินรับสุทธิเป็น gross

## ขอบเขตการตรวจ

- ธุรกรรม: schema, IDs, วันที่/เดือน, ประเภท, จำนวนเงิน และธงรอตรวจ
- รายการคล้ายกัน: วัน ยอด รายละเอียด และประเภทตรงกัน → ตั้งคำถามก่อนแก้ ไม่ลบรายการ
- ภาษี: แยกยอด `confirmed` กับ `needs_review`; ไม่รวม snapshot, excluded, source totals หรือ tax estimates; ยอดว่างยังเป็นข้อมูลที่ขาด
- เอกสาร: ตรวจลิงก์ธุรกรรม/ปีภาษี และถามหลักฐานเพิ่มตามสถานะใน ledger ไม่ได้พิสูจน์ความแท้ของไฟล์
- รายจ่ายประจำ: ชื่อและหมวดตรงกัน เดือนละรายการอย่างน้อยสามเดือนต่อเนื่อง วันที่คลาดไม่เกินสี่วัน → candidate ให้ผู้ใช้ยืนยัน ไม่สร้างสัญญาหรือวันตัดเงินขึ้นเอง

ข้อจำกัดที่ตั้งใจแสดงให้ผู้ใช้เห็น: ยังไม่มี OCR ใน core, การประเมิน confidence ของ LAYA, การอ่าน PDF อัตโนมัติ, engine คำนวณภาษีที่ผ่านตรวจปีปัจจุบัน, การจำ alias ร้านค้า, และตัวรันแจ้งเตือนตามเวลา ความรู้ภาษีใน THAI_TAX_GUIDE.md ยังต้องตรวจแหล่งทางการของปีที่เลือกก่อนให้คำแนะนำ

## ลองด้วยข้อมูลจำลอง

ข้อมูลทุกแถวใน `examples/review_demo` เป็นข้อมูลสมมติ ต้องคัดลอกไปโฟลเดอร์ทดลองก่อน:

```sh
mkdir -p /tmp/thai-finance-demo
cp examples/review_demo/database.example.csv /tmp/thai-finance-demo/database.csv
cp examples/review_demo/tax_preparation.example.csv /tmp/thai-finance-demo/tax_preparation.csv
cp examples/review_demo/finance_evidence.example.json /tmp/thai-finance-demo/finance_evidence.json
python3 -m finance_core --workspace /tmp/thai-finance-demo report
```

ผลที่คาดหวัง: candidate รายจ่ายประจำที่ยอดเปลี่ยน, งานเทียบเงินเดือนคลาด 500 บาท และงานตรวจหลักฐานภาษี ลองเปลี่ยน `other_withheld_thb` เป็น `1000.00` ในโฟลเดอร์ทดลอง งานเทียบเงินเดือนจะ resolved โดยยอดเงินสดยังเป็น 28000.00

## สัญญาข้อมูลสำหรับทีม

คง CSV เดิมเป็น ledger ทุก pillar อ้างอิงด้วย `transaction_id` ไม่สร้างสำเนาธุรกรรมเป็นบัญชีใหม่ ผลตรวจใช้ task envelope เดียวกัน: `id`, `kind`, `transaction_ids`, `source_references`, `facts`, `question`, `fingerprint`, `status` ส่วนข้อมูลเฉพาะ domain เก็บเป็น sidecar ที่ลิงก์ ID

| Pillar | ทำแล้วในรอบนี้ | งานต่อไป |
| --- | --- | --- |
| 1 Income / expense | ตรวจข้อมูล, candidate ซ้ำ, คิวตรวจธงคุณภาพ, audit | confidence ราย field, กฎจำร้านที่ผู้ใช้ยืนยัน, ingestion แบบทำซ้ำไม่เพิ่มรายการ |
| 2 Investment | คง Buy/Sell แยกตาม ledger | sidecar instrument, units, price, fee, currency, account ก่อนคำนวณ holdings/returns |
| 3 Tax | คิวหลักฐาน, ยอดแยกสถานะ, เทียบ gross/net ตามเอกสาร | กฎแยกปีพร้อมแหล่งทางการ/วันที่ตรวจ/เงื่อนไข, ตรวจเอกสารละเอียด |
| 4 Price comparison | ระบุ contract ที่ต้องมี | product/variant ID, ปริมาณ, ราคาต่อหน่วย, ค่าส่ง, เงื่อนไข, source และเวลาที่ตรวจ |
| 5 Subscription | ค้นหา recurring candidate และยอดเปลี่ยน | สัญญา/วันต่ออายุที่ยืนยันแล้ว, scheduler และช่องทางแจ้งเตือนที่ผู้ใช้เลือก |

## การพิสูจน์ในงานแข่ง

- AI-native: agent อ่านหลักฐาน/คำตอบและเลือกเครื่องมือ; core รับผิดชอบเลขและสถานะที่ทำซ้ำได้
- Autonomous & Adaptive: scan ซ้ำไม่เพิ่มงานเดิม, หยุดเมื่อ input เสีย, รับคำตอบแล้วทำต่อ, เปิดงานเมื่อข้อมูลเปลี่ยน การจำกฎข้ามรายการยังเป็นงานต่อไป
- Deep Domain: แยก cash กับ gross, ไม่ใช้ snapshot เป็นสิทธิปัจจุบัน, ไม่หัก payroll ซ้ำ, ไม่ยืนยันสิทธิจากคะแนนโมเดล

การเตรียมนี้เป็นฐานก่อนแข่งขันตามกติกาที่ตรวจไว้ งานที่ทำระหว่างการแข่งขันควรระบุแยกจากฐานนี้ให้ชัด

