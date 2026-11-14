(function () {
  const $ = id => document.getElementById(id);
  const API = (window.PAOWEEN_API_BASE||location.origin)+'/api/copilot';
  let session = null, pillar = 'overview', busy = false, generation = 0;
  const suggestions = {
    overview: ['สรุปงานที่ควรตรวจ 3 เรื่องแรก พร้อมรายการอ้างอิง'],
    spending: ['ช่วงนี้ใช้จ่ายหมวดไหนมากที่สุด และมีรายการใดน่าตรวจ?','ช่วยเตรียมบันทึกรายจ่ายใหม่ให้หน่อย'],
    investment: ['สรุปยอดซื้อและขายการลงทุนแยกตามหมวด และข้อมูลที่ยังขาด'],
    tax: ['มีหลักฐานภาษีอะไรยังขาดในปีที่เลือก และควรขออะไรก่อน?'],
    comparison: ['ช่วยเปรียบเทียบราคาสินค้าให้หน่อย ต้องใช้ข้อมูลอะไรบ้าง?'],
    subscription: ['ค้นหารายจ่ายที่อาจเป็น subscription และยอดที่เปลี่ยน']
  };
  async function api(path, data) {
    const response = await fetch(API + path, data ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)} : {cache:'no-store'});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'เชื่อมต่อไม่สำเร็จ');
    return value;
  }
  function message(role, text, sources) {
    const article = document.createElement('article'); article.className='chat-message '+role;
    const label=document.createElement('strong'); label.textContent=role==='user'?'คุณ':'Finance Copilot';
    const body=document.createElement('p');
    const links=/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>]+)|\*\*([^*]+)\*\*|`([^`]+)`/g;
    let offset=0; for(const match of text.matchAll(links)){
      body.append(document.createTextNode(text.slice(offset,match.index)));
      if(match[4]||match[5]){const inline=document.createElement(match[4]?'strong':'code');inline.textContent=match[4]||match[5];body.append(inline);}else{const link=document.createElement('a');link.href=match[2]||match[3];link.textContent=match[1]||match[3];link.target='_blank';link.rel='noopener noreferrer';body.append(link);}offset=match.index+match[0].length;
    }
    body.append(document.createTextNode(text.slice(offset))); article.append(label,body);
    if(sources){const el=document.createElement('div'); el.className='chat-evidence'; el.textContent='อ่านบัญชี '+sources.transactions+' รายการ · งานตรวจ '+sources.tasks+' งาน · ปี '+sources.scope.year+' / เดือน '+sources.scope.month;article.append(el);}
    const welcome=$('chat-welcome');if(welcome)welcome.remove();
    $('chat-log').append(article); article.scrollIntoView({block:'nearest',behavior:'auto'});
  }
  function controls(value) {busy=value;$('chat-send').disabled=value;$('chat-input').disabled=value;$('chat-reset').disabled=value;$('chat-progress').hidden=!value;}
  function showSuggestions(){ $('chat-suggestions').replaceChildren();suggestions[pillar].forEach(text=>{const button=document.createElement('button');button.type='button';button.textContent=text;button.onclick=()=>{$('chat-input').value=text;$('chat-input').focus();};$('chat-suggestions').append(button);}); }
  function syncFilters(){['year','month'].forEach(name=>{const source=$(name+'-filter'),target=$('chat-'+name);target.replaceChildren(...Array.from(source.options).map(o=>o.cloneNode(true)));target.value=source.value;});}
  function view(){if(['#finance-copilot','#subscriptions','#comparison'].includes(location.hash))syncFilters();}
  window.addEventListener('hashchange',view);view();
  new MutationObserver(()=>{if(!$('finance-copilot').hidden)syncFilters();}).observe($('year-filter'),{childList:true});
  ['year','month'].forEach(name=>$('chat-'+name).addEventListener('change',()=>{const source=$(name+'-filter');source.value=$('chat-'+name).value;source.dispatchEvent(new Event('change'));}));
  document.querySelectorAll('[data-pillar]').forEach(button=>{button.onclick=()=>{pillar=button.dataset.pillar;document.querySelectorAll('[data-pillar]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));showSuggestions();};});
  function proposal(p){
    const box=$('chat-proposal'); box.replaceChildren();box.hidden=!p;if(!p)return;
    const title=document.createElement('strong');title.textContent='ตรวจแผนก่อนบันทึก';
    const preview=document.createElement('pre');const a=p.action;
    const types={expense:'รายจ่าย',income:'รายรับ',investment:'การลงทุน',transfer:'โอนระหว่างบัญชีตนเอง'};
    preview.textContent=a.kind==='review_task'?'บันทึกคำตอบงาน '+a.task_id+'\n'+a.note:
      'เพิ่ม'+(types[a.transaction_type]||a.transaction_type)+'\nวันที่: '+a.date+'\nรายละเอียด: '+a.description+'\nจำนวน: '+a.amount_thb+' บาท\nหมวด: '+a.category+(a.action?' · '+a.action:'')+(a.tax_category?'\nติดตามภาษี: '+a.tax_category+' (รอหลักฐานและตรวจสิทธิ)':'');
    const approve=document.createElement('button');approve.className='button';approve.type='button';approve.textContent='ยืนยันบันทึกตามแผน';
    const cancel=document.createElement('button');cancel.className='chat-secondary';cancel.type='button';cancel.textContent='ข้าม';cancel.onclick=()=>{box.hidden=true;};
    approve.onclick=async()=>{approve.disabled=true;cancel.disabled=true;try{const result=await api('/approve',{session,proposal_id:p.id});message('assistant',result.answer);box.hidden=true;$('reload-button').click();}catch(e){message('assistant',e.message);}finally{approve.disabled=false;cancel.disabled=false;}};
    box.append(title,preview,approve,cancel);
  }
  $('chat-form').onsubmit=async event=>{
    event.preventDefault();if(busy)return;const text=$('chat-input').value.trim();if(!text)return;
    controls(true);proposal(null);message('user',text);$('chat-input').value='';const token=generation;
    try {
      if(!session)session=(await api('/session',{})).session;
      await api('/chat',{session,message:text,pillar,scope:{year:$('chat-year').value||'all',month:$('chat-month').value||'all'}});
      for(let i=0;i<150;i++){
        const job=await api('/job?session='+encodeURIComponent(session));
        if(token!==generation)return;$('chat-progress').textContent=job.stage;
        if(job.status==='done'){message('assistant',job.answer,job.sources);proposal(job.proposal);break;}
        if(job.status==='error')throw new Error(job.error);
        if(i===149)throw new Error('งานใช้เวลานาน ลองเริ่มแชทใหม่');
        await new Promise(resolve=>setTimeout(resolve,2000));
      }
    }catch(e){message('assistant',e.message);}finally{controls(false);$('chat-input').focus();}
  };
  $('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}};
  $('chat-reset').onclick=()=>{generation++;session=null;$('chat-log').replaceChildren();proposal(null);message('assistant','เริ่มแชทใหม่แล้ว เลือก pillar และช่วงข้อมูลแล้วถามได้เลย');};
  api('/status').then(s=>{$('copilot-status').textContent=s.available?'Codex · ข้อมูลจริง':'ไม่พบ Codex CLI';}).catch(()=>{$('copilot-status').textContent='เปิด open-dashboard.command เพื่อเชื่อม Codex';});
  showSuggestions();
  if(window.financeUI)window.financeUI.route();
})();
