'use strict';
// Conversation is kept only in this page's memory. No localStorage or external AI.
const shoppingChat={messages:[],context:{},draft:'',busy:false};
function shopping(){
  const heading=node('div','chat-heading'),copy=node('div');copy.append(node('h1','','คุยก่อนซื้อ'),node('p','','Shopping Agent · อยากได้อะไร ค่อย ๆ คิดด้วยกันครับ'));
  heading.append(copy,button('ใช้แบบฟอร์ม',()=>{view.replaceChildren();shoppingForm();}));view.append(heading);
  const shell=node('section','chat-shell'),toolbar=node('div','chat-toolbar'),title=node('div','chat-title');
  title.append(node('span','chat-avatar','S'),node('span','','Shopping'),node('span','chat-status','ผู้ช่วยตัดสินใจซื้อ'));
  toolbar.append(title,button('แชทใหม่',()=>{if(shoppingChat.busy)return;shoppingChat.messages=[];shoppingChat.context={};shoppingChat.draft='';render();}));
  const log=node('div','chat-log');log.setAttribute('role','log');log.setAttribute('aria-label','บทสนทนา Shopping');log.setAttribute('aria-live','polite');
  const composer=node('form','chat-composer'),row=node('div','chat-input-row'),input=node('textarea'),send=node('button','chat-send','ส่ง ↑');
  input.rows=1;input.maxLength=2000;input.setAttribute('aria-label','ข้อความถึง Shopping');input.placeholder='พิมพ์ชื่อสินค้า หรือถามว่าซื้อไหวไหม…';input.value=shoppingChat.draft;
  input.addEventListener('input',()=>shoppingChat.draft=input.value);input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();composer.requestSubmit();}});
  send.type='submit';row.append(input,send);composer.append(row,node('div','chat-caption','โหมดคำสั่งพื้นฐานในเครื่อง · ข้อมูลการเงินจำลอง · ยังไม่เชื่อม AI หรือค้นหาราคาสด'));
  shell.append(toolbar,log,composer);view.append(shell);
  function draw(){log.replaceChildren();
    if(!shoppingChat.messages.length){const welcome=messageBubble('assistant','สวัสดีครับ วันนี้เล็งอะไรไว้?\nพิมพ์ชื่อสินค้าได้เลย ถ้ารู้ราคาและค่าส่งแล้ว บอกมาด้วย เดี๋ยวช่วยเช็กงบให้ครับ');const quick=node('div','chat-quick');['เช็กงบวันนี้','ดูเป้าหมายของฉัน','ช่วยลดรายจ่าย'].forEach(text=>quick.append(button(text,()=>submit(text))));welcome.content.append(quick);log.append(welcome.row);}
    shoppingChat.messages.forEach(m=>{const item=messageBubble(m.role,m.text);if(m.result)chatResult(item.content,m.result);log.append(item.row);});
    if(shoppingChat.busy)log.append(node('div','chat-typing','กำลังตรวจข้อมูลในเครื่อง…'));
    send.disabled=shoppingChat.busy;input.disabled=shoppingChat.busy;log.scrollTop=log.scrollHeight;
  }
  async function submit(text){if(shoppingChat.busy||!text.trim())return;shoppingChat.messages.push({role:'user',text:text.trim()});shoppingChat.draft='';input.value='';shoppingChat.busy=true;draw();
    try{const result=await api('chat',{message:text.trim(),context:shoppingChat.context});shoppingChat.context=result.context||{};shoppingChat.messages.push({role:'assistant',text:result.reply,result});}
    catch(err){shoppingChat.messages.push({role:'assistant',text:'ยังประเมินไม่สำเร็จครับ: '+err.message+' ลองแก้ข้อความแล้วส่งใหม่ได้ ไม่มีการบันทึกรายการ'});}
    finally{shoppingChat.busy=false;if(page==='shopping'){draw();input.focus({preventScroll:true});}}
  }
  composer.addEventListener('submit',event=>{event.preventDefault();submit(input.value);});draw();
}
function messageBubble(role,text){const row=node('article','chat-message'+(role==='user'?' user':'')),avatar=node('div','chat-avatar',role==='user'?'คุณ':'S'),content=node('div','chat-content');content.append(node('div','chat-author',role==='user'?'คุณ':'Shopping · Local'),node('div','chat-bubble',text));row.append(avatar,content);return {row,content};}
function chatResult(parent,response){const data=response.data;if(response.kind==='message')return;const card=node('div','chat-result');
  if(response.kind==='purchase'){
    card.append(node('span','pill','จำลองจากราคาที่คุณบอก'),node('h3','',data.name),node('div','big',money(data.total)));
    const stats=node('div','stats');metric(stats,'เงินพร้อมใช้',data.available);metric(stats,'เงินเหลือหลังซื้อ',data.remaining);card.append(stats,node('div','status',data.financial.status));
    card.append(node('p','muted','ตัวเลือกสินค้า: '+data.name),node('p','muted','ส่วนลดเพิ่มเติม: ยังไม่ใช้ · ค่าจัดส่ง: '+money(data.shipping)),node('p','muted',data.notice));
    if(data.simulation){const sim=data.simulation,detail=node('div','muted'),bar=track(card,0);const update=i=>{const s=sim.states[i];detail.textContent='เหลือ '+money(s.remaining)+' · ใช้ต่อวัน '+money(s.daily_spending)+' · '+s.status;bar.fill.style.width=s.used_percent+'%';bar.t.setAttribute('aria-valuenow',s.used_percent);};slider(card,'ลองปรับยอดจ่ายรวม · ราคาสมมติ',sim.states.map(s=>s.price),sim.initial,update);update(sim.initial);card.append(detail);}
    const actions=node('div','actions');actions.append(button('วางแผนเก็บเงิน',()=>{go('goals');view.querySelector('form').replaceWith(goalForm(data.goal));},true),button('ดูรายจ่ายที่ลดได้',()=>go('leaks')));card.append(actions);
  }else if(response.kind==='daily'){
    const r=data.initial;card.append(node('span','pill','งบวันนี้ · DEMO'),node('h3','','วันนี้ยังใช้เพิ่มได้'),node('div','big',money(r.today_remaining)));track(card,r.spending_progress);const stats=node('div','stats');metric(stats,'ใช้ไปวันนี้',r.today_recorded);metric(stats,'เงินพร้อมใช้เดือนนี้',r.available_month);card.append(stats,node('p','muted',r.message),button('ทดลองปรับงบวันนี้',()=>go('daily')));
  }else if(response.kind==='goal_draft'){card.append(node('h3','','เป้าหมาย: '+data.goal_name),node('p','muted','วันที่ต้องการ: '+data.target_date),button('ตรวจและเติมข้อมูลเป้าหมาย',()=>{go('goals');view.querySelector('form').replaceWith(goalForm(data));},true));
  }else if(response.kind==='goals'){
    card.append(node('h3','','เป้าหมายของฉัน'));if(!data.goals.length)card.append(node('p','muted','ยังไม่มีเป้าหมายที่บันทึกไว้ครับ'));
    data.goals.forEach(g=>card.append(node('p','',g.goal_name+' · '+g.progress+'% · เหลือ '+money(g.remaining_target_amount))));card.append(button('ดู / สร้างเป้าหมาย',()=>go('goals'),true));
  }else if(response.kind==='leaks'){
    card.append(node('h3','','ข้อมูลรายจ่ายของคุณ'));if(!data.items?.length)card.append(node('p','muted','ยังไม่มีข้อมูล จึงยังไม่คำนวณยอดที่อาจประหยัดได้'));(data.items||[]).forEach(item=>{const row=node('div','row-head');row.append(node('span','',item.name),node('strong','',money(item.amount)+(item.period==='annual'?' / ปี':' / เดือน')));card.append(row);});card.append(button(data.items?.length?'ลองปรับรายจ่าย':'เพิ่มข้อมูลรายจ่าย',()=>go('leaks'),true));
  }else if(response.kind==='travel_setup'){card.append(node('h3','','วางงบทริป'),button('ใส่รายละเอียดทริป',()=>go('travel'),true));}
  parent.append(card);
}
