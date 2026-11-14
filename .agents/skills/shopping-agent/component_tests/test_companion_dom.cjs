// Local event/DOM simulation, not browser or host certification.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{test}=require('node:test'),{execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'assets/companion-inline.html'),'utf8');
const walk=n=>[n,...n.children.flatMap(walk)];
class El{
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.attrs={};this.listeners={};this.value='';this.textContent='';}
 append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}
 setAttribute(k,v){this.attrs[k]=v;}addEventListener(k,f){(this.listeners[k]??=[]).push(f);}
 querySelectorAll(tag){return walk(this).filter(n=>n.tag===tag);}
 dispatchEvent(e){for(const f of this.listeners[e.type]||[])f(e);}
}
function fixture(action){return JSON.parse(execFileSync('python',['-c',`import sys,json,tempfile;from pathlib import Path;from datetime import date;sys.path.insert(0,sys.argv[1]);from companion import run_companion;from goal_storage import GoalStore; t=tempfile.TemporaryDirectory(); print(json.dumps(run_companion(dict(action=sys.argv[2],synthetic=True,trip=dict(destination='Fixture',departure='Start',travel_date='2026-11-28',days=3,nights=2,travelers=1,costs=[dict(name='Transport',amount='1000',unit='per_person',certainty='estimated',source='fixture')])),GoalStore(Path(t.name)/'local'/'test.sqlite3'),date(2026,11,14))))`,path.join(root,'scripts'),action],{encoding:'utf8'}));}
function mount(data,saved=null,host=true){
 const nodes=Object.fromEntries(['mode','view','feedback'].map(k=>[k,new El('div')])),calls=[],states=[],events={};
 const surface={querySelector:q=>nodes[q.match(/data-role="(.*?)"/)[1]]};
 const openai=host?{widgetState:saved,sendFollowUpMessage:async p=>calls.push(p),setWidgetState:async p=>states.push(p)}:null;
 vm.runInNewContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1],{document:{getElementById:id=>id==='financial-companion'?surface:{textContent:JSON.stringify(data)},createElement:tag=>new El(tag)},window:{openai,addEventListener:(k,f)=>events[k]=f},Event:class{constructor(type){this.type=type;}}});
 return {nodes,calls,states,events,all:()=>walk(nodes.view)};
}
test('daily slider changes result with no followup or financial data in state',()=>{const a=mount(fixture('daily'));const slider=a.all().find(n=>n.type==='range');const hero=a.all().find(n=>n.className==='fc-hero');const before=hero.textContent;slider.value=slider.max;slider.dispatchEvent({type:'input'});assert.notEqual(hero.textContent,before);assert.equal(a.calls.length,0);assert.equal(a.states.length,1);assert.deepEqual(Object.keys(a.states[0].modelContent).sort(),['demo','view']);});
test('daily restores private choice without saving on load',()=>{const data=fixture('daily'),a=mount(data);const s=a.all().find(n=>n.type==='range');s.value='2';s.dispatchEvent({type:'input'});const b=mount(data,a.states[0]);assert.equal(b.all().find(n=>n.type==='range').value,'2');assert.equal(b.states.length,0);assert.equal(b.calls.length,0);});
test('leak reduction and subscription checkbox are local',()=>{const a=mount(fixture('leaks'));const sliders=a.all().filter(n=>n.type==='range');sliders[0].value='5';sliders[0].dispatchEvent({type:'input'});const sub=a.all().find(n=>n.type==='checkbox');sub.checked=true;sub.dispatchEvent({type:'change'});assert(a.all().some(n=>n.textContent==='฿809'));assert.equal(a.calls.length,0);});
test('potential goal does not pretend to save without goal selection',()=>{const a=mount(fixture('leaks'));a.all().find(n=>n.textContent==='เอาเงินส่วนนี้ไปเติมเป้าหมาย').dispatchEvent({type:'click'});assert.equal(a.calls.length,0);assert(a.nodes.feedback.textContent.includes('เลือกหรือสร้าง'));});
test('new goal asks for review, potential saving not cash',()=>{const a=mount(fixture('leaks'));a.all().find(n=>n.textContent==='สร้างเป้าหมายใหม่จากแผนลดรายจ่าย').dispatchEvent({type:'click'});assert.equal(a.calls.length,1);assert(a.calls[0].prompt.includes('ยังไม่ใช่เงินสด'));});
test('travel slider updates total locally; no image or booking',()=>{const a=mount(fixture('travel'));const slider=a.all().find(n=>n.type==='range');slider.value='4';slider.dispatchEvent({type:'input'});assert(a.all().some(n=>n.textContent==='฿2,000'));assert.equal(a.calls.length,0);assert(!a.all().some(n=>n.tag==='img'));});
test('travel create action forwards changed total and asks confirmation',()=>{const a=mount(fixture('travel'));const slider=a.all().find(n=>n.type==='range');slider.value='4';slider.dispatchEvent({type:'input'});a.all().find(n=>n.textContent==='สร้างเป้าหมายสำหรับทริปนี้').dispatchEvent({type:'click'});assert(a.calls[0].prompt.includes('2000'));assert(a.calls[0].prompt.includes('ก่อนบันทึก'));});
test('missing host produces an honest fallback',()=>{const a=mount(fixture('daily'),null,false);a.all().find(n=>n.textContent==='ดูเป้าหมายของฉัน').dispatchEvent({type:'click'});assert(a.nodes.feedback.textContent.includes('พิมพ์ในแชท'));});
test('no external network API, authored icons or destination images',()=>{assert(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(html));assert(!/<img|<svg|<iframe/.test(html));});
test('no user expenses shows no assumed categories or zero savings card',()=>{const a=mount({kind:'leaks',current_date:'2026-11-14',synthetic:false,revision:0,goals:[],report:{analysis:{categories:[],subscriptions:[]},simulation:{controls:[],states:{}}}});assert(a.all().some(n=>n.textContent.includes('ยังไม่มีข้อมูลรายจ่าย')));assert(!a.all().some(n=>n.textContent==='฿0'));assert(!a.all().some(n=>n.type==='range'||n.type==='checkbox'));});
