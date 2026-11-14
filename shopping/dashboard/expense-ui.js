'use strict';
function renderExpenseAnalysis(){
  intro('รายจ่ายที่ปรับได้ของคุณ','เริ่มจากสิ่งที่คุณจ่ายจริง แล้วค่อยเลือกว่าส่วนไหนลดได้ครับ');
  const data=state.leaks,grid=node('div','grid'),list=node('article','card'),sim=node('article','card');
  list.append(node('h2','','ข้อมูลรายจ่ายสำหรับการวิเคราะห์'));
  const items=data.items||[];
  if(!items.length){
    list.append(node('div','empty-mark','◎'),node('h3','','ยังไม่มีข้อมูลรายจ่ายให้วิเคราะห์'),node('p','muted','ระบบจะไม่ใส่หมวดรายจ่ายหรือบริการสมาชิกให้เอง เพิ่มเฉพาะรายการที่คุณมีจริง หรือใช้ข้อมูลจากผู้ช่วยการเงินเมื่อเชื่อมต่อแล้ว'));
    sim.append(node('h2','','เริ่มจากรายจ่ายของคุณ'),node('p','muted','เมื่อมีข้อมูล จึงจะแสดงตัวปรับลดและยอดที่อาจประหยัดได้ ตอนนี้ยังไม่สรุปว่าเงินรั่วตรงไหนครับ'));
  }else{
    items.forEach(item=>{
      const row=node('div','rows'),head=node('div','row-head');head.append(node('span','',item.name),node('strong','',money(item.amount)+(item.period==='annual'?' / ปี':' / เดือน')));row.append(head,node('p','muted','แหล่งข้อมูล: ยอดที่คุณระบุ ไม่ใช่รายการธุรกรรม'));
      row.append(button('นำออกจากการวิเคราะห์',async()=>{state.leaks=await api('expense-summary',{action:'remove',id:item.id});render();}));list.append(row,node('hr','divider'));
    });
    sim.append(node('h2','','ทดลองลดเฉพาะรายการที่คุณเลือก'));
    const controls=[],simulation=data.simulation,metrics=node('div','stats');let chosen={monthly:'0',annual:'0'};
    function update(){const key=controls.map(({input,control})=>input.type==='checkbox'?(input.checked?'1':'0'):String(control.values[Number(input.value)])).join(',');chosen=simulation.states[key];if(!chosen)return;metrics.replaceChildren();metric(metrics,'อาจประหยัดต่อเดือน ถ้าทำได้จริง',chosen.monthly);metric(metrics,'ต่อปี ถ้าทำได้ต่อเนื่อง',chosen.annual);}
    simulation.controls.forEach(control=>{
      const label=node('label',control.type==='checkbox'?'check':'',control.label),input=node('input');input.type=control.type;input.value='0';input.min='0';input.max=String(control.values.length-1);input.step='1';
      const output=node('output','','0%');if(control.unit==='percent')label.append(output);
      input.addEventListener(control.type==='checkbox'?'change':'input',()=>{if(control.unit==='percent')output.textContent=control.values[Number(input.value)]+'%';update();});label.append(input);sim.append(label);controls.push({input,control});
    });
    sim.append(metrics,node('p','note','เงินที่อาจประหยัดได้ยังไม่ใช่เงินสด ไม่เพิ่มงบใช้จ่ายหรือยอดออมให้อัตโนมัติ'),node('p','muted','รายจ่ายที่มากหรือจ่ายบ่อยไม่ได้แปลว่าฟุ่มเฟือย เลือกปรับเฉพาะส่วนที่ไม่กระทบสิ่งจำเป็นครับ'));
    sim.append(button('ใช้ประกอบการวางแผนเป้าหมาย',()=>{go('goals');notice.textContent='อาจลดได้ '+money(chosen.monthly)+' ต่อเดือน ยังไม่ใช่เงินที่ออมแล้ว แผนจะประเมินจากเงินจริงที่มีเท่านั้นครับ';},true));update();
  }
  list.append(node('hr','divider'));
  const form=node('form');form.append(node('h3','','เพิ่มรายจ่ายที่คุณอยากลองปรับ'));
  field(form,'name','ชื่อหมวดรายจ่ายหรือบริการ');field(form,'amount','ยอดรวมตามรอบที่เลือก (บาท)','number');
  selectField(form,'type','ประเภทและรอบของยอดนี้',[['expense','หมวดรายจ่าย · ยอดรวมต่อเดือน'],['subscription_monthly','บริการสมาชิก · ยอดต่อเดือน'],['subscription_annual','บริการสมาชิก · ยอดต่อปี']]);
  const submit=node('button','btn primary','ใช้ยอดนี้วิเคราะห์');submit.type='submit';form.append(submit,node('p','muted','จำลองได้ครั้งละ 2 หมวดและ 3 บริการ ข้อมูลอยู่ในหน่วยความจำระหว่างเปิดตัวรัน ไม่บันทึกลง ledger'));
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;notice.textContent='';try{const values=Object.fromEntries(new FormData(form)),item={name:values.name,amount:values.amount,kind:values.type==='expense'?'expense':'subscription',period:values.type==='subscription_annual'?'annual':'monthly'};state.leaks=await api('expense-summary',{action:'add',item});render();}catch(err){notice.textContent=err.message;}finally{submit.disabled=false;}});
  list.append(form);grid.append(list,sim);view.append(grid);
}
