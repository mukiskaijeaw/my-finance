# Shopping Agent — Chat acceptance cases

## Final Interactive MVP

tests/test_companion.py covers the reconciled final demo with no default goal, daily balance coverage and no double subtraction, last-day division, local what-if without writes, dynamic category/frequency analysis, explicit delivery fees, unknown billing cycle, exact annual subscription cost, duplicates/recurring/outlier candidates, malformed-data blocking, bounded five-category travel simulation, shared goal commitments, male-particle personality, calendar padding and transient demo progress, future/duplicate saving rejection, demo-store separation, price simulation and a shopping → reduction draft → confirmed goal → daily-budget → travel-goal E2E chain. All persisted acceptance records use temporary local databases.

component_tests/test_companion_dom.cjs and updated purchase/goal DOM tests verify local slider events without follow-up, private selection restore without save-on-load, subscription toggles, honest missing-host fallback, review-required goal/travel actions, demo future-day progress without writes and price simulation retaining the sourced quote. These are DOM simulations, not evidence of actual new Codex host clicks or responsive/dark-mode appearance. See test-results.txt for actual latest results.

## Purchase decision → goal flow

tests/test_purchase_flow.py verifies blank entry and supplied-text/photo form skipping, broad <=4/exact 1 sourced candidate, mandatory confirmation, reject/reset, default month-end, protected current goals without double deduction, stock/price/shipping freshness, optional budget cap, local date snapshot generation, cross-month forecast, preview without writes, reviewed consent and active goal/calendar creation, stale review rejection, and skip without mutation. component_tests/test_purchase_dom.cjs verifies blank form/chat image hint, real selection/rejection requests, product-only widgetState, zero-follow-up date switching, savings request vs automatic write, and template reuse/no network. These tests do not certify real merchant stock, image recognition accuracy or actual Codex host clicks.

## Dynamic financial goals — automated acceptance

tests/test_goal_planner.py covers all five goal categories, changing names/prices/dates, Bangkok date functions, leap/non-leap month-end, same-day/overdue/funded targets, inclusive saving days, ceiling-to-satang/final cap, complete cross-month cashflow and early shortfall before later income, multiple simultaneous goals, saved-money coverage/no double deduction, protected balances for paused/deleted goals, missing data, consent, revision conflicts, idempotent retries, same-day duplicate savings, preview without writes, edit/pause/activate/delete, progress and recorded calendar updates. All mocks are in tests/fixtures or test functions, not default production UI.

component_tests/test_goal_dom.cjs tests blank form/no product defaults, dynamic text/progress, record request requiring confirmation, host-unavailable fallback, precomputed calendar month switching and no network/LLM calculation. These are DOM-stub tests; actual new-button clicks/rendered responsive/dark-mode UI still require user verification. No real goal/ledger is written during tests.

## Financially Aware Upgrade

tests/test_planning.py เพิ่ม regression และ end-to-end CLI สำหรับ: ไม่กำหนดงบ/งบขัดกัน/คงงบเดิม, ค่าเช่าใกล้ครบกำหนด, subscription, paid/covered ไม่หักซ้ำ, projected ต้องยืนยัน, เงินเผื่อหายไม่เป็นศูนย์, รอบรายรับไม่ถูกต้อง, freelancer ขั้นต่ำ 3 เดือน, กระแสเงินสดติดลบ, opportunity delay=0/มากกว่า0/ไม่มี ETA, permission ใช้เงินเป้าหมาย, เงินสดเทียบผ่อนครบงวด/ค่าธรรมเนียม/เดือนหลังไม่พอ/terms ไม่ครบ, จำลองหลายสินค้าไม่ mutate, readiness ราคาขยับ/เงินซ้ำ/เงินเก็บอนาคตไม่ใช่เงินกันจริง, goal consent/แยกไฟล์/ไม่เขียนทับ, price-only ไม่อ่าน planning/profile, engine ไม่มี network, rendering ทุก template, STDIN → plan → Markdown และ schema 11/14 อ่านอย่างเดียว

การทดสอบเหล่านี้ใช้ข้อมูลสังเคราะห์ ไม่พิสูจน์ความถูกต้องของการตีความภาษาธรรมชาติทุกกรณีหรือเงื่อนไขร้านจริง ดู contract สำหรับข้อจำกัดการจำลองตามเดือน

ต่อยอดกรณีทดสอบจาก MVP เดิมและข้อกำหนด Chat-based ล่าสุด ตัด HTTP/UI tests ออกจากแพ็กเกจแชท ไม่มี server หรือ frontend ในแพ็กเกจนี้

รัน `python -m unittest discover -s tests -v` ใช้ข้อมูลสังเคราะห์ ไม่เรียก API แบบเสียเงิน

| กลุ่ม | Acceptance |
|---|---|
| เงินสดพอ / ไม่พอ | AFFORDABLE แยก monthly surplus กับ available; SAVE_FIRST ปัดเดือนขึ้น; earmarked ไม่ถูกบวกซ้ำ |
| เงินเหลือศูนย์ / ติดลบ | ไม่สร้างระยะเวลา; รักษาสถานะ NOT_AFFORDABLE |
| ข้อมูลขาด / เก่า / อนาคต / ไม่ยืนยัน | INSUFFICIENT_DATA; ไม่แทนค่าว่างด้วย 0 |
| เงินสำรอง / หนี้ค้าง / ภาระอนาคต | กัน protected cash ครั้งเดียว; future_extra ต้องมีและไม่ซ้ำ; ระบุสมมติฐานกันทุกยอดล่วงหน้า |
| รายได้ไม่แน่นอน | ต้องมีรายได้ครบอย่างน้อย 3 เดือน ใช้ค่าต่ำสุดอย่างระมัดระวัง |
| ราคา / ค่าส่ง / ส่วนลด | Decimal; effective ต้องมีหลักฐานครบ; คูปอง ineligible ไม่ถูกหักแม้ estimate |
| หลักฐานระบุสินค้า / listing | แยกระดับสองชนิด; model/sku และ variants ต้องตรง; source ว่างหรือขัดแย้งไม่ HIGH |
| ผลกระทบ | เงินหลังซื้อ สัดส่วนใช้เงินพร้อมใช้ เดือนเก็บเงิน ส่วนต่างราคา และสถานะคุ้มครองเป้าหมาย |
| ไม่มีข้อมูลการเงิน | ยังสร้างตารางสินค้าได้ ไม่อ่านไฟล์การเงินและไม่แสดงข้อมูลการเงินทั้งหมด |
| Adapter | schema 14 คอลัมน์ตามไฟล์จริง; ตรวจซ้ำ/รูปแบบ/คุณภาพ/ความเก่า; ไม่เขียนฐานข้อมูล |
| Profile เดิม | ไม่ map legacy fields เป็นเงินสดอัตโนมัติ; versioned profile ต้องอยู่ใน finance-dir |
| Adaptive | ทุก financial request อ่าน ledger ใหม่; skill ต้องค้นราคาใหม่เมื่อกลับมาถาม |
| Query privacy | ปฏิเสธ financial keys และ nested values; allowlist เฉพาะสินค้า ไม่มี network ใน engine/helper |
| Watchlist | ต้อง consent; รับเฉพาะคุณลักษณะสินค้า; JSON แยก CSV; ไม่เขียนทับไฟล์; monitoring=false |
| CLI integration | JSON stdin → engine → Markdown ภาษาไทย; ไม่เปิด socket/server; malformed JSON ได้ exit code 2 |
| Markdown safety | escape table delimiters/newlines/HTML; URL ต้อง https ไม่มี credentials |
| Financial Fit Summary Card | เลือกแสดง card เมื่อ include_financial=true; status/metrics/ETA/progress/recommendation/assumptions ครบ; ราคาอย่างเดียวไม่แสดงการเงิน |
| Savings Progress | คำนวณใน engine; 0/บางส่วน/ครบ/เกินเป้า/ราคา0; จำกัด 100%; แถบ 10 ช่องไม่เต็มก่อนถึงเป้า; ข้อมูลขาดหรือราคาไม่ยืนยันไม่มีเปอร์เซ็นต์ปลอม |

Automated tests อยู่ใน tests/test_engine.py และ tests/test_chat.py รายงานจำนวนและผลจริงใน test-results.txt

Mock/demo: tests/test_demo.py ต้องยืนยันว่าอ่านเฉพาะ synthetic fixture ไม่อ่านการเงินจริง ไม่เรียก network ไม่เขียน fixture ทับ มีป้าย DEMO บน card/JSON ไม่เปิดลิงก์ร้านจำลอง และ real mode ไม่ fallback มาใช้ข้อมูลจำลอง ตรวจผลตัวอย่างห่อเล็ก AFFORDABLE เหลือ 111 บาท และแพ็กใหญ่ SAVE_FIRST ขาด 79 บาท เก็บเพิ่ม 1 เดือน

Pillar separation / product images: tests/test_separation_images.py ต้องยืนยันว่า source ที่ไม่เชื่อมไม่อ่านไฟล์การเงิน, search ไม่อ่านแม้มี source, financial request ที่ข้อมูลขาดไม่ fallback เป็น source เดิม, รูปต้องยืนยันทั้ง provenance และ variant, URL/source ที่ไม่ปลอดภัยหรือรูปไม่ตรงตัวเลือกไม่ถูก embed

ทดสอบจริงในแชท: อ่าน SKILL.md → ค้นเว็บด้วยคุณลักษณะสินค้า → เปิดหน้าร้าน → ส่งหลักฐานเข้า CLI → แสดงตาราง Markdown ต้องระบุราคา/สต็อก/ค่าส่งที่ยังยืนยันไม่ได้ ไม่เรียกสิ่งนี้ว่า automated retailer test

ข้อจำกัด: tests ไม่พิสูจน์ความถูกต้องของทุกคำตอบ LLM หรือ PII detection ใน free text; agent ต้องตรวจว่า query มีเฉพาะข้อมูลสินค้าก่อนเรียก web tool ยังไม่มีภาพอ้างอิงจริงสำหรับ forward-test การระบุสินค้าจากรูป

## Personal Financial Decision conversation cases

เพิ่มเติม tests/test_decision_policy.py: เงินพอไม่ซื้ออัตโนมัติ, จำเป็น+อยู่ในแผน+เหมาะสม, flash sale/BNPL ไม่เร่งซื้อ, ผู้ใช้อยากเก็บเงิน, ของพังจำเป็นเร่งด่วนพร้อมทางเลือกที่ fit, ทางเลือกไม่มีราคายืนยัน, ข้อมูลการเงิน/วัตถุประสงค์/หลักฐานขาด, เปลี่ยนข้อมูลแล้วคำแนะนำเปลี่ยน, คำถามเฉพาะจำเป็น, ไม่อนุมานซ่อม/ยืม/มือสอง, price-only ไม่อ่านเงิน, no network/no mutation และ stdin CLI ถึง policy และคำตอบ visual_tests/test_decision_renderer.py ตรวจ PNG สองธีม/ข้อมูลขาด/fit กับ policy ขัดแย้ง

ชุดทดสอบ conversation ใช้บริบทที่เข้ารหัสจากคำพูดจำลอง ไม่ใช่การรับรองความแม่นยำการตีความภาษาธรรมชาติทุกประโยคของโมเดล

## Native UI + Simulator acceptance

Native selection 8 ตัวเลือกและ user reply จริง monthly_overview = PASS ในแชทนี้; welcome.py ตรวจ triggers/routes และ welcome CLI ไม่อ่าน provider การคำนวณ simulator A–E, separate accounts/no-double-deduct, all111 states, zero denominator/shortfall/unsafe input และ MCP stdio resources/tools ทดสอบใน tests/test_simulator.py, test_mcp_ui_poc.py DOM-stub input-event tests ผ่าน scripts/test_simulator_view.py แยกจาก browser drag tests ซึ่ง NOT TESTED เนื่องจาก Browser URL policy ปฏิเสธ file:// MCP host rendering/click/follow-up/context = NOT TESTED ขณะฟีเจอร์ปิดและ server ไม่เชื่อม โปรดอย่าถือว่า protocol tests คือ host UI tests
