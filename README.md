# My Finance · AI Personal Finance Agent

เครื่องมือจัดการรายรับรายจ่ายสำหรับมนุษย์เงินเดือนและฟรีแลนซ์ชาวไทย ส่งสลิปโอนเงินหรือภาพ statement ธนาคาร แล้ว agent จะอ่าน จัดหมวด ตรวจรายการซ้ำ และบันทึกลง `database.csv` ในเครื่อง พร้อมแดชบอร์ดสรุปรายเดือน รายการประจำอย่าง Netflix, Spotify, ค่าโทรศัพท์ ถูกจัดเป็น `Subscriptions` เพื่อใช้แจ้งเตือน Subscription ต่อ

## ไฟล์

| ไฟล์ | ใช้ทำอะไร |
| --- | --- |
| `AGENTS.md` | กติกาของ agent: schema, การจัดหมวด, การอ่านสลิปธนาคารไทย (แปลงปี พ.ศ., ตัดสินประเภทจากฝั่งผู้ใช้, จับคู่สลิปกับ statement ไม่ให้ซ้ำ) |
| `dashboard.html` | แดชบอร์ดอ่าน `database.csv` พร้อมโหมดอ่านสลิปและ statement |
| `open-dashboard.command` | เปิดแดชบอร์ดบน Mac ผ่าน local server `127.0.0.1:8765` |
| `database.example.csv` | แม่แบบหัวตาราง (ไม่มีข้อมูล) |
| `demo/try-finance.html` | หน้า demo ภาษาไทย เริ่มจากว่าง กรอกเงินเดือน เพิ่มสลิป/statement หรือกด "ลองดูข้อมูลตัวอย่าง" ข้อมูลเก็บใน localStorage ของเบราว์เซอร์เท่านั้น |
| `demo/database.example.csv` | ข้อมูลสมมติของมนุษย์เงินเดือน (Example Co. Ltd.) 3 เดือน สำหรับ demo |

## Agent รายรับรายจ่าย (Pillar 1) และแจ้งเตือน Subscription (Pillar 5)

Agent มีสองส่วนทำงานคู่กัน

- **System-1** (`agent/`): Python ล้วน รันบนเครื่อง ไม่ต่ออินเทอร์เน็ต จัดหมวดแต่ละรายการพร้อมคะแนนความมั่นใจ มั่นใจ 90% ขึ้นไปบันทึกเอง 60 ถึง 89% ส่งให้ Codex ต่ำกว่า 60% ถามผู้ใช้ เรียนรู้จากรายการเก่าใน ledger และจากคำตอบของผู้ใช้ (`rules.csv`)
- **Codex skills** (`.agents/skills/`): `income-expense` อ่านภาพสลิปหรือ statement แล้วส่งแถวให้ System-1 คิดต่อกับรายการที่ก้ำกึ่ง และถามผู้ใช้เฉพาะที่ยังไม่ชัด `subscription` หารายจ่ายประจำและเตือนก่อนต่ออายุหรือครบกำหนด

| ไฟล์ | ใช้ทำอะไร |
| --- | --- |
| `agent/system1.py` | ตัวตัดสินใจเร็วพร้อม confidence score |
| `agent/recurring.py` | หารายจ่ายประจำ, subscription และสร้างการแจ้งเตือน |
| `agent/cli.py` | คำสั่ง `ingest`, `review`, `answer`, `alerts`, `state`, `dashboard` |
| `.agents/skills/dashboard` | skill `/dashboard`: พิมพ์ "ขอดูสรุป" แล้ว agent สร้าง `my-dashboard.html` จากข้อมูลของเราแล้วเปิดให้ |
| `dashboard-journal.html` | แดชบอร์ดแบบสมุดบันทึก (ร่างล่าสุด): แบนเนอร์ เมนูซ้ายมือ ปฏิทินวันจ่าย กราฟประเภทรายจ่าย ดับเบิลคลิกเปิดได้เลย |
| `dashboard-folder.html` | แดชบอร์ดแบบแฟ้มเอกสาร (ร่าง) ดับเบิลคลิกเปิดได้เลย มีข้อมูลตัวอย่างฝังอยู่ |
| `demo/statement-2026-11.example.csv` | statement สมมติ 1 เดือนสำหรับลองรอบการทำงาน |
| `demo/build-demo.py` | รันหนึ่งรอบด้วยข้อมูลสมมติ แล้วฝังผลลงแดชบอร์ด |

ลองหนึ่งรอบด้วยข้อมูลสมมติ (ไม่แตะข้อมูลจริง):

```sh
mkdir -p /tmp/try && cp demo/database.example.csv /tmp/try/database.csv
python3 agent/cli.py --dir /tmp/try --today 2026-11-12 ingest demo/statement-2026-11.example.csv
python3 agent/cli.py --dir /tmp/try review
python3 agent/cli.py --dir /tmp/try answer Q001 --type income --category Freelance
python3 agent/cli.py --dir /tmp/try --today 2026-11-12 alerts --days 7
```

### สิ่งที่ pillar อื่นอ่านได้

ทุกคำสั่งเขียน `agent_state.json` (schema `pillar1-state/1`) ใหม่ทุกครั้ง: `monthly` (รายรับ รายจ่าย เงินคืน เงินลงทุน แยกหมวดรายเดือน), `recurring`, `alerts`, `fixed_costs`, `review_queue`, `routing` Main agent, Tax, Investment อ่านไฟล์นี้ไฟล์เดียวโดยไม่ต้องแตะ `database.csv` เงินคืน (`Refund`) แยกออกจากรายได้แล้ว

## เริ่มใช้กับ Codex หรือ Claude

1. Clone repo นี้ไว้ในโฟลเดอร์ส่วนตัว
2. คัดลอก `database.example.csv` เป็น `database.csv`
3. เปิดโฟลเดอร์ใน Codex หรือ Claude Code แล้วพิมพ์ "ช่วยตั้งค่า Personal Finance Agent จาก AGENTS.md ให้พร้อมรับสลิป"
4. แนบสลิป (PNG/JPG) หรือพิมพ์รายการ เช่น "วันนี้ค่าอาหาร 120 บาท" agent จะถามก่อนบันทึกถ้าวันที่ ยอดเงิน หรือประเภทอ่านไม่ชัด

## เปิดแดชบอร์ด

- Mac: ดับเบิลคลิก `open-dashboard.command` จะสร้าง `my-dashboard.html` จาก `database.csv` แล้วเปิดให้ ไม่ต้องเปิด server
- ทุกเครื่อง: `python3 agent/cli.py dashboard --open` หรือพิมพ์ "ขอดูสรุป" ในแชทของ Codex
- เครื่องอื่น: รัน `python3 -m http.server 8765` ในโฟลเดอร์นี้ แล้วเปิด `http://127.0.0.1:8765/dashboard.html`
- Demo: ดาวน์โหลด `demo/try-finance.html` แล้วดับเบิลคลิกเปิดในเบราว์เซอร์ได้เลย ข้อมูลตัวอย่างฝังอยู่ในไฟล์แล้ว

## ตัวอ่านภาพสลิปและ statement (ใน demo)

กด **ตัวอ่านภาพ** ในส่วนเพิ่มสลิปเพื่อเลือกวิธีอ่าน

| ตัวเลือก | ข้อมูลออกจากเครื่องไหม | หมายเหตุ |
| --- | --- | --- |
| Claude บน claude.ai | ผ่าน claude.ai | มีเฉพาะตอนเปิดจากลิงก์ claude.ai |
| อ่านในเครื่อง (ค่าเริ่มต้น) | ไม่ออก | ใช้ Tesseract.js อ่านภาษาไทย แล้วแยกวันที่ (แปลง พ.ศ.) เวลา ยอดเงิน ผู้รับ เลขอ้างอิง 6 ตัวท้าย และเดาหมวดจากชื่อร้าน ครั้งแรกต้องต่ออินเทอร์เน็ตเพื่อโหลดตัวอ่านและโมเดลภาษา ผลลัพธ์มั่นใจไม่เกิน 85% จึงต้องตรวจก่อนบันทึกเสมอ |
| Claude API key ของฉัน | ส่งไป api.anthropic.com หลังกดยืนยันทุกครั้ง (หรือยืนยันครั้งเดียวจนปิดหน้า) | ใช้ key ของผู้ใช้เอง ค่าเริ่มต้นไม่จำ key เลือกให้จำไว้ในเบราว์เซอร์ได้ โมเดลเริ่มต้น `claude-opus-5-5` แก้ได้ |

## Schema

`transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag`

## ความเป็นส่วนตัว

repo นี้มีเฉพาะข้อมูลสมมติ `database.csv` จริง สลิป และภาพ statement ถูกกันไว้ใน `.gitignore` เก็บไว้ในเครื่องเท่านั้น
