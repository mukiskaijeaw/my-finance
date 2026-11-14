// Event/view tests using a local DOM stub; not a host/browser certification.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{test}=require('node:test');
const html=fs.readFileSync(path.join(__dirname,'../assets/purchase-flow-inline.html'),'utf8');
class El{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.style={};this.dataset={};this.events={};this.value='';this.textContent='';}
 append(...items){this.children.push(...items);}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,v){(this.events[k]??=[]).push(v);}
 replaceChildren(){this.children=[];}
 querySelectorAll(){return walk(this).filter(e=>e.dataset.productId);}
 checkValidity(){return true;}
 reportValidity(){}
 async click(){for(const fn of this.events.click||[])await fn();}
}
const walk=el=>[el,...el.children.flatMap(walk)];
function mount(data){
 const nodes=Object.fromEntries(['content','feedback','mode'].map(k=>[k,new El('div')]));
 const root={querySelector:q=>nodes[q.match(/data-role="(.*?)"/)[1]]};
 const calls=[],states=[];
 const host={sendFollowUpMessage:async p=>calls.push(p),setWidgetState:async p=>states.push(p)};
 vm.runInNewContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1],{
   document:{getElementById:id=>id==='shopping-purchase-flow'?root:{textContent:JSON.stringify(data)},createElement:tag=>new El(tag)},
   window:{openai:host,addEventListener(){}},crypto:{randomUUID:()=> 'fixture-operation'}
 });
 return {nodes,calls,states};
}
const product={id:'p',name:'สินค้า fixture',model:'Model fixture',source:'https://example.org/p',quote:{effective:'300'},listing:{shipping:'0',shipping_verified:true},match:{tier:'HIGH'}};
const base={version:1,stage:'INTENT',intent:{},candidates:[],selected_product:null,selection_confirmed:false};
const report={product,current_date:'2030-01-01',target_date:'2030-01-31',quote:{effective:'300'},financial:{status:'AFFORDABLE'},decision:{recommendation:'BUY_WITH_CAUTION',label:'fixture',reasons:[]},available_spending:'1000',remaining_after_purchase:'700',existing_goal_commitments:'100',daily_saving:'10',daily_spending:'20',savings_progress:'0',new_plan_zero_assumption:true};
test('entry has no default product and images attach in chat',()=>{const a=mount({session:base});const all=walk(a.nodes.content);assert(all.some(e=>e.tag==='input'&&e.name==='product'&&e.value===''));assert(all.some(e=>e.textContent.includes('แนบในช่องแชทหลัก')));assert(!all.some(e=>e.type==='file'));});
test('candidate confirmation stores product only and requests assessment',async()=>{const a=mount({session:{...base,stage:'CONFIRM',candidates:[product]}});await walk(a.nodes.content).find(e=>e.textContent==='ใช่ รุ่นนี้แหละ').click();assert(a.calls[0].prompt.includes('select_and_evaluate'));assert(a.states[0].modelContent.purchaseSession.selection_confirmed);assert(!a.states[0].modelContent.purchaseSession.profile);});
test('reject all and search again are real action requests',async()=>{const a=mount({session:{...base,stage:'CONFIRM',candidates:[product]}});await walk(a.nodes.content).find(e=>e.textContent==='ไม่ใช่สักรุ่น').click();assert(a.calls[0].prompt.includes('reject'));});
test('known date changes locally without a follow-up or search',async()=>{const r2={...report,target_date:'2030-01-20',daily_saving:'15'};const a=mount({session:base,report,date_reports:{'2030-01-20':r2}});const input=walk(a.nodes.content).find(e=>e.type==='date');input.value='2030-01-20';await walk(a.nodes.content).find(e=>e.textContent==='คำนวณวันใหม่').click();assert.equal(a.calls.length,0);assert(a.nodes.feedback.textContent.includes('ในเครื่อง'));assert(walk(a.nodes.content).some(e=>e.tag==='input'&&e.value==='2030-01-20'));});
test('start savings is a request, not an automatic save or order',async()=>{const a=mount({session:base,report});await walk(a.nodes.content).find(e=>e.textContent==='วางแผนซื้อของชิ้นนี้').click();assert(a.calls[0].prompt.includes('start_goal'));assert(a.nodes.feedback.textContent.includes('ยังไม่มีการซื้อ'));});
test('price slider uses local computed states without search or follow-up',()=>{const a=mount({session:base,report,price_simulation:{initial:0,notice:'fixture',states:[{price:'300',remaining:'700',daily_spending:'20',used_percent:'30',status:'WITHIN_AVAILABLE_BUDGET'},{price:'1200',remaining:'-200',daily_spending:'0',used_percent:'100',status:'WAIT_AND_SAVE'}]}});const slider=walk(a.nodes.content).find(e=>e.type==='range');slider.value='1';slider.events.input[0]();assert.equal(a.calls.length,0);assert(walk(a.nodes.content).some(e=>e.textContent.includes('WAIT_AND_SAVE')));assert.equal(report.quote.effective,'300');});
test('template has no network calls or hardcoded product default',()=>{assert(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(html));assert(!/Nike|PUMA|Jordan/.test(html));});
