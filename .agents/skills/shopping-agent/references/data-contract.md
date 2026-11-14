# Local helper contract

ส่วนนี้เป็น contract เดิมที่ยังรองรับเพื่อ compatibility สำหรับการวางแผนรุ่นใหม่ ให้อ่าน [planning-contract.md](planning-contract.md) และใช้ planning budget ที่ยืนยันรอบรายรับ/ภาระก่อนสรุปซื้อไหว Adapter รองรับ header จริงทั้ง 14 คอลัมน์และฐาน 11 คอลัมน์ตรงลำดับ ไม่ merge CSV ระหว่าง provider

Python 3.10+ standard library เท่านั้น ไม่เรียก LLM/network ไม่ต้องใช้ API key

`shopping.py evaluate`: อ่าน JSON ผ่าน stdin หรือ `--input`; JSON เป็น default output, `--format markdown` สำหรับแชท วันปัจจุบันใช้ Asia/Bangkok ไม่รับวันย้อนหลังจาก LLM เพื่อทำให้ข้อมูลเก่าดูสด

```json
{
  "target": {"brand":"Example", "model":"Model A", "color":"black"},
  "identification_evidence": {"model":{"value":"Model A", "source":"user explicitly named model"}},
  "listings": [{
    "name":"Model A", "store":"Example store", "url":"https://example.org/product",
    "price":"1000.00", "shipping":null, "discount":"0", "checked":"2026-11-12",
    "verified":false, "shipping_verified":false,
    "discount_verified":false, "eligible":false,
    "stock":"unknown", "stock_verified":false,
    "evidence":{"model":{"value":"Model A", "source":"https://example.org/product"}}
  }],
  "include_financial":false
}
```

ตัวอย่างสังเคราะห์เท่านั้น ไม่ใช่ listing จริง Agent ต้องเติมจากหลักฐานจริง ไม่ส่ง JSON ให้ผู้ใช้กรอก

- `verified` ใช้ true เฉพาะเมื่อตรวจราคาของ variant นั้นจากหน้าสินค้าจริง มี https URL และ checked ไม่เกิน 7 วัน
- shipping ต้องทราบและ shipping_verified=true แม้เป็น 0
- discount=null หมายถึงไม่ทราบ ต้องบอกข้อจำกัด; discount="0" คือไม่ใช้ส่วนลดในราคาที่เทียบ ถ้ามากกว่า 0 ต้อง discount_verified=true และ eligible=true ไม่เช่นนั้นไม่หักและ effective=null
- ราคาที่ไม่ครบส่งออก `effective:null` / issues; estimate อาจยังไม่รวมค่าส่งที่ไม่ทราบ ห้ามใช้ estimate เพื่อสรุปซื้อไหวหรือถูกสุด
- stock ใช้ available/unknown/out_of_stock; ยืนยันเฉพาะ variant ที่เลือก ซื้อถูกสุดในรายการที่ตรวจได้ต่อเมื่อทุก listing ราคาสุทธิ รุ่น และสต็อกพร้อมซื้อยืนยันครบ ไม่ใช่ถูกสุดทั้งตลาด
- source เป็น provenance ที่ agent ตรวจ ไม่ใช่ข้อพิสูจน์ว่าทุก URL/ข้อความเชื่อถือได้ เครื่องคำนวณไม่ fetch URL

## Financial profile

การ์ดสินค้าทุกใบแสดงตัวเลือกสินค้า/ส่วนลดเพิ่มเติม/ค่าจัดส่งเรียงเหมือนกัน `variants` เป็นรายการข้อความของตัวเลือกที่ตรวจได้ และ `variants_verified:true` เมื่อมีหลักฐานยืนยัน หากไม่มีข้อมูลจะแสดงยังไม่ยืนยัน ไม่ซ่อนหัวข้อและไม่สร้างตัวเลือกขึ้นเอง

ให้ `include_financial:true` พร้อม profile ที่ได้จากข้อมูล local และผู้ใช้ที่ยืนยันแล้ว ค่าเงินเป็น string ทศนิยมไม่เกิน 2 ตำแหน่ง ไม่ทราบใช้ null ไม่เติมศูนย์

| Field | ความหมาย |
|---|---|
| income | รายได้สุทธิต่อเดือน ไม่ใช่เงินเดือน gross |
| essential | รายจ่ายจำเป็นต่อเดือน ไม่รวมหนี้และออมด้านล่าง |
| debt | ยอดชำระหนี้ต่อเดือน ไม่ใช่ยอดหนี้คงค้างทั้งหมด |
| saving | เป้าหมายออม/ลงทุนต่อเดือน ไม่รวมใน essential/debt |
| cash | เงินสดทั้งหมด ณ วันที่ยืนยัน รวมยอด protected และ earmarked แล้ว |
| emergency | ส่วนเงินสดที่ต้องรักษาเป็นเงินฉุกเฉิน |
| reserved | เงินกันไว้สำหรับภาระปัจจุบันที่ยังไม่จ่าย นับครั้งเดียว ไม่ใช่เอารายจ่ายที่จ่ายไปแล้วมาหักซ้ำ |
| earmarked | optional: ส่วนเงินสดที่ตั้งใจใช้ในแผนเก็บเงิน ถ้าไม่ระบุใช้เงินพร้อมใช้ที่ไม่ถูกคุ้มครอง ไม่บวกเป็นยอดเงินใหม่ |
| as_of | วันที่ยืนยัน YYYY-MM-DD ไม่เกิน 30 วันและไม่ใช่อนาคต |
| complete | true เมื่อผู้ใช้ยืนยันงบรายเดือน/เงินสดครบและไม่ซ้ำกัน |
| future_complete | true เมื่อยืนยันรายการอนาคตครบและไม่ซ้ำกับ reserved/งบรายเดือน |
| future_extra | array ของ {"month":1,"amount":"1500"}; ไม่มีภาระต้องยืนยัน [] ไม่ปล่อย missing |
| income_kind | stable หรือ variable |
| income_history | สำหรับ variable: ยอดรายได้สุทธิอย่างน้อย 3 เดือนที่ยืนยันว่าบันทึกครบ ใช้ค่าต่ำสุดร่วมกับ income |

Optional local profile file ต้องอยู่ภายใน finance-dir และมีรูปแบบ `{"schema_version":1,"profile":{...}}` โหลดด้วย `profile_path` ใน request หรือ `ledger --profile-path` ไม่เก็บไฟล์นี้เองโดยไม่ร้องขอ ไม่ใช้ legacy profiles ที่ไม่มี version อัตโนมัติ

Schema ธุรกรรมจริง 14 คอลัมน์: transaction_id,date,transaction_type,description,amount_thb,category,action,year_month,source,source_reference,data_quality_flag,model,token_input,token_output

Adapter ตรวจ header, วันที่, year_month, transaction_type, investment action, จำนวนเงิน, ID ซ้ำ, data_quality_flag และความเก่า 45 วัน ยอด monthly เป็นเพียง observed totals 0 ในยอดรวมคือไม่มีแถวประเภทนั้นที่บันทึก ไม่ใช่รายได้/รายจ่ายจริงเท่ากับ 0 ไม่อ้างยอดนี้เป็นความครบถ้วนของเดือน

## กฎคำนวณ

monthly_surplus = income - essential - debt - saving

available = cash - emergency - reserved - ผลรวม future_extra ทุกยอด (กันล่วงหน้าอย่างระมัดระวัง ไม่จำลองวันครบกำหนด)

- ข้อมูลขาด/เก่า/ไม่ยืนยัน/ราคาไม่ครบ: INSUFFICIENT_DATA
- ยอด earmarked เกิน cash: ข้อมูลขัดแย้ง INSUFFICIENT_DATA
- เงินสดไม่ครอบคลุม protected/current/future reserve: NOT_AFFORDABLE ไม่มี months แม้ surplus บวก นี่เป็นนโยบายกันทุกภาระอนาคตก่อน ต้องอธิบายว่าเป็น conservative MVP
- surplus >= 0 และ price <= available: AFFORDABLE, months=0
- ยังซื้อไม่ได้และ surplus>0: SAVE_FIRST; months=ceil(max(0,price-min(available,earmarked หรือ available))/surplus)
- surplus<=0 และไม่เข้า AFFORDABLE: NOT_AFFORDABLE ไม่มี months

`remaining_after_purchase` คือ available-price ในการจำลอง ไม่ใช่เงินจริงหลังธุรกรรม `spending_percent` คือ price/available และไม่มีค่าเมื่อ available=0 `goal_impact` บอกว่ายังคุ้มครองเป้าหมายตามข้อมูลที่ยืนยันหรือควรรอ ไม่แปลงเงินติดลบเป็นคำแนะนำให้ถอนเงินออม

MVP สมมติเงินเหลือรายเดือนคงที่ในอนาคต ไม่มีดอกเบี้ย/ผลตอบแทน/เงินเฟ้อ/เครดิตใหม่ จำนวนเดือนเป็นประมาณการ ห้ามรับประกันวันซื้อได้
