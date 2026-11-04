const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'browser-helper/bridge.js'),'utf8');
function setup(origin='https://qiuchen.yinxingpingpang.com'){
 const listeners=[],main={children:[],prepend(e){this.children.unshift(e)}};
 const doc={querySelector(s){if(s==='main')return main;if(s==='#ginkgo-local-helper-status')return main.children.find(e=>e.id===s.slice(1));return null},
  createElement(tag){return {tag,children:[],replaceChildren(){this.children=[]},append(e){this.children.push(e)},set innerHTML(x){throw Error('Untrusted HTML must not be interpreted')}}},body:main};
 const sandbox={Date,Number,String,location:{origin,pathname:'/api/match-center/growth/'},document:doc,
  chrome:{runtime:{id:'own',onMessage:{addListener:f=>listeners.push(f)}}},
  window:{},setTimeout,clearTimeout};
 Object.defineProperty(doc,'cookie',{get(){throw Error('must not read cookies')}});
 Object.defineProperty(sandbox,'localStorage',{get(){throw Error('must not read authentication storage')}});
 vm.createContext(sandbox);vm.runInContext(source,sandbox);
 const report={helper_version:'1.4.9',status:'running',platform:'douyin',phase:'await_title',completed_rounds:1,empty_rounds:0,total_added:0,next_at:Date.now()+30000,updated_at:new Date().toISOString()};
 const send=(r=report,sender='own')=>{let result;for(const f of listeners)f({type:'GINKGO_COLLECTION_STATUS',report:r},{id:sender},x=>result=x);return result};
 const text=()=>main.children.flatMap(e=>e.children.map(x=>x.textContent)).join('\n');
 return {listeners,main,send,text,sandbox,report};
}
let tests=0;
const f=setup();assert.equal(f.send().ok,true);assert.match(f.text(),/核验原帖已打开/);assert.match(f.text(),/已完成 1 轮/);tests++;
f.send({...f.report,partial_rounds:2,failed_posts:3,last_skipped_reason:'页面资源未就绪'});assert.match(f.text(),/未完整读取 2 轮/);assert.match(f.text(),/原帖 3 条/);assert.match(f.text(),/最近跳过：页面资源未就绪/);tests++;
f.send({...f.report,status:'paused',reason:'点击失败 <img src=x onerror=alert(1)>'});assert.equal(f.main.children.length,1);assert.match(f.text(),/<img src=x/);assert.match(f.text(),/已暂停/);tests++;
const wrong=setup();assert.equal(wrong.send(wrong.report,'another-extension'),undefined);assert.equal(wrong.main.children.length,0);tests++;
const foreign=setup('https://www.douyin.com');assert.equal(foreign.listeners.length,0);assert.equal(foreign.main.children.length,0);tests++;
vm.runInContext(source,f.sandbox);assert.equal(f.listeners.length,1);tests++;
const result={passed:true,tests,network_calls:0,customer_messages:0,authentication_reads:0};
fs.writeFileSync(path.join(__dirname,'status-bridge-verification.json'),JSON.stringify(result,null,2));
console.log('PASS '+tests+' read-only status bridge checks; no authentication reads, networking or customer messages.');
