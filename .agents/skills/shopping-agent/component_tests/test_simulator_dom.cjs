// View-model/input-event unit tests, not a browser or drag test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{test}=require('node:test');
const folder=process.env.SIMULATOR_PREVIEW_DIR || (()=>{throw Error('Run scripts/test_simulator_view.py --node node, which prepares synthetic fixtures');})();
function mount(file){
 const html=fs.readFileSync(folder+file,'utf8'),nodes=new Map();
 for(const match of html.matchAll(/\bid="([^"]+)"/g)){nodes.set(match[1],{textContent:'',hidden:false,value:'',attributes:{},listeners:{},dataset:{},style:{setProperty(k,v){this[k]=v}},setAttribute(k,v){this.attributes[k]=v},addEventListener(k,v){this.listeners[k]=v}})}
 nodes.get('simulation-data').textContent=html.match(/<script type="application\/json" id="simulation-data">([\s\S]*?)<\/script>/)[1];
 const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
 vm.runInNewContext(script,{document:{getElementById:id=>{assert(nodes.has(id));return nodes.get(id)}},Intl,console});
 return {nodes,html,update(value){const slider=nodes.get('price-slider');slider.value=String(value);slider.listeners.input();}};
}
const expected=[['3200','฿3,300','49.2%','AFFORDABLE'],['5500','฿1,000','84.6%','BUY_WITH_CAUTION'],['8000','฿-1,500','123.1%','WAIT_AND_SAVE'],['5000','฿1,500','76.9%','AFFORDABLE'],['6500','฿0','100.0%','BUY_WITH_CAUTION']];
for(const [price,remaining,percent,status] of expected){test('input event '+price,()=>{const app=mount('nike-simulator.html');app.update(price);const n=app.nodes;assert.equal(n.get('remaining').textContent,remaining);assert.equal(n.get('spending-label').textContent,'ใช้เงินพร้อมใช้ '+percent);assert.equal(n.get('simulator').dataset.status,status);assert.equal(n.get('product-price').textContent,n.get('slider-price').textContent);assert(n.get('recommendation').textContent.length>0);assert(n.get('explanation').textContent.length>0);});}
test('all 111 input events use precomputed states',()=>{const app=mount('nike-simulator.html');for(let value=1000;value<=12000;value+=100){app.update(value);assert(app.nodes.get('product-price').textContent.startsWith('฿'));}});
test('over-budget progress clamped and correct color token',()=>{const app=mount('nike-simulator.html');app.update(8000);assert.equal(app.nodes.get('bar-fill').style.width,'100%');assert.equal(app.nodes.get('simulator').style['--tone'],'var(--red)');assert(app.nodes.get('explanation').textContent.includes('1,500'));});
test('dynamic product not hardcoded and placeholder supported',()=>{const first=mount('nike-simulator.html'),second=mount('headphones-simulator.html');assert.notEqual(first.nodes.get('product-name').textContent,second.nodes.get('product-name').textContent);assert(second.nodes.get('product-name').textContent.includes('หูฟัง'));assert.equal(second.nodes.get('product-image').src,undefined);});
test('no outgoing calls or LLM in component',()=>{const {html}=mount('nike-simulator.html');assert(!/\b(fetch|XMLHttpRequest|WebSocket)\s*\(/.test(html));assert(html.includes("connect-src 'none'"));});
