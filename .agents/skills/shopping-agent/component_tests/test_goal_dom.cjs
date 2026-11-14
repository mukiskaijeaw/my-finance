// Local DOM-stub tests, not a browser/host-click certification.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{test}=require('node:test');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../assets/goal-planner-inline.html'),'utf8');
class Element{
 constructor(tag){this.tag=tag;this.tagName=tag.toUpperCase();this.children=[];this.style={};this.attrs={};this.listeners={};this.value='';this.textContent='';}
 append(...children){this.children.push(...children);}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 replaceChildren(...children){this.children=children;}
 checkValidity(){return Number(this.value)>0;}
 reportValidity(){return this.checkValidity();}
}
function mount(goals=[],calendar={},host=true,demo=false){
 const nodes=Object.fromEntries(['mode','overview','goals','creation','form','feedback'].map(k=>[k,new Element('div')]));
 const root={querySelector:q=>{const k=q.match(/data-role="([^"]+)"/)[1];assert(nodes[k]);return nodes[k];}};
 const data={current_date:'2030-04-30',summary:'fixture',daily_spending:'100',goals,calendar,demo};
 const calls=[];const context={document:{getElementById:id=>id==='dynamic-goal-planner'?root:{textContent:JSON.stringify(data)},createElement:tag=>new Element(tag)},window:{openai:host?{sendFollowUpMessage:async p=>{calls.push(p);}}:null},FormData:class{constructor(form){return Object.entries(form.fields||{});}}};
 vm.runInNewContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1],context);
 return {nodes,calls};
}
function descendants(el){return [el,...el.children.flatMap(descendants)];}
const sample={goal_id:'fixture',goal_name:'ค่าเรียน',goal_category:'education',target_amount:'300',saved_amount:'100',target_date:'2030-05-02',countdown_text:'อีก 2 วัน',progress:'33.33',daily_saving:'66.67',status:'ACTIVE',plan_status:'ACTIVE',message:'fixture'};
test('empty UI has no product/price/date default',()=>{const app=mount();assert.equal(app.nodes.goals.children.length,0);assert(!/Nike|Jordan|PUMA/.test(html));assert(!html.includes('value="0"'));});
test('goal name and engine-computed progress are rendered',()=>{const app=mount([sample]);const all=descendants(app.nodes.goals);assert(all.some(n=>n.textContent==='ค่าเรียน'));assert(all.some(n=>n.style.width==='33.33%'));});
test('record button sends a request, never a fake success or local write',async()=>{const app=mount([sample]);const all=descendants(app.nodes.goals);const input=all.find(n=>n.tag==='input');input.value='50';await all.find(n=>n.textContent==='ขอบันทึกเงินออมวันนี้').listeners.click();await Promise.resolve();assert.equal(app.calls.length,1);assert(app.calls[0].prompt.includes('50'));assert(app.calls[0].prompt.includes('ขอยืนยัน'));});
test('missing host has an honest text fallback',async()=>{const app=mount([sample],{},false);await descendants(app.nodes.goals).find(n=>n.textContent==='พักแผน').listeners.click();assert(app.nodes.feedback.textContent.includes('พิมพ์ในแชท'));});
test('calendar uses recorded Python dates and month selection',()=>{const rows=[{date:'2030-04-30',state:'recorded',saved_amount:'100',weekday:1},{date:'2030-05-01',state:'upcoming',saved_amount:null,weekday:2}];const app=mount([sample],{fixture:rows});const all=descendants(app.nodes.goals);const select=all.find(n=>n.tag==='select');assert(select);select.value='2030-05';select.listeners.change();assert(descendants(app.nodes.goals).some(n=>n.textContent==='01'));});
test('no network or LLM calculation in component',()=>{assert(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(html));assert(!html.includes('/api/'));});
test('future demo click changes simulated progress without host call',()=>{const g={...sample,demo_progress:[{progress:'33.33'},{progress:'55.56'}]},rows=[{date:'2030-05-01',state:'upcoming',weekday:2,target:true}];const app=mount([g],{fixture:rows},true,true);let all=descendants(app.nodes.goals);const day=all.find(n=>n.tag==='button'&&n.textContent.includes('01'));day.listeners.click();all=descendants(app.nodes.goals);assert(all.some(n=>n.style.width==='55.56%'));assert.equal(app.calls.length,0);assert(app.nodes.feedback.textContent.includes('ยอดออมจริงและแผนไม่เปลี่ยน'));});
