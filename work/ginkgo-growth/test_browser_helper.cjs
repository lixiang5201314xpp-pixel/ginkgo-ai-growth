/* Isolated extension bridge/permission tests. No browser credentials or network calls. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.join(__dirname,'browser-helper');let tests=0;
function test(fn){fn();tests++}
function bridge(origin='https://qiuchen.yinxingpingpang.com'){
 const handlers=[],writes=[],messages=[];
 const sandbox={location:{origin,pathname:'/api/match-center/growth/'},sessionStorage:{setItem:(k,v)=>writes.push([k,v])},window:{postMessage:(v,d)=>messages.push([v,d])},chrome:{runtime:{id:'own-extension',onMessage:{addListener:fn=>handlers.push(fn)}}}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'bridge.js'),'utf8'),sandbox);
 return {handlers,writes,messages};
}
test(()=>{const m=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));assert.deepEqual(m.permissions,['activeTab','scripting','storage']);assert(m.host_permissions.every(x=>x.startsWith('https://qiuchen.yinxingpingpang.com/')||x.startsWith('http://127.0.0.1:8796/')))});
test(()=>{const b=bridge();b.handlers[0]({type:'GINKGO_CAPTURE',payload:{items:[{excerpt:'synthetic'}]}},{id:'own-extension'},()=>{});assert.equal(b.writes.length,1);assert.equal(b.writes[0][0],'ginkgo_external_capture');assert.equal(b.messages.length,1)});
test(()=>{const b=bridge();b.handlers[0]({type:'GINKGO_CAPTURE',payload:{items:[{}]}},{id:'other-extension'},()=>{});assert.equal(b.writes.length,0)});
test(()=>{const b=bridge();b.handlers[0]({type:'unexpected',payload:{items:[{}]}},{id:'own-extension'},()=>{});assert.equal(b.writes.length,0)});
test(()=>{const b=bridge();b.handlers[0]({type:'GINKGO_CAPTURE',payload:{items:Array(21).fill({})}},{id:'own-extension'},()=>{});assert.equal(b.writes.length,0)});
test(()=>{const b=bridge();b.handlers[0]({type:'GINKGO_CAPTURE',payload:{items:[]}},{id:'own-extension'},()=>{});assert.equal(b.writes.length,0)});
test(()=>{const b=bridge('https://evil.invalid');assert.equal(b.handlers.length,0);assert.equal(b.writes.length,0)});
test(()=>{const b=bridge('http://127.0.0.1:8796');assert.equal(b.handlers.length,1)});
test(()=>{const sandbox={URL};vm.runInNewContext(fs.readFileSync(path.join(root,'capture.js'),'utf8'),sandbox);const c=sandbox.GinkgoCapture;assert.equal(c.platformForUrl('https://www.douyin.com.evil.invalid/video/a'),null);assert.equal(c.platformForUrl('https://name:pass@www.douyin.com/video/a'),null);assert.equal(c.platformForUrl('https://www.douyin.com/video/a'),'douyin');assert(!c.redact('电话13800138000 微信abcdef123').includes('13800138000'));assert(!c.looksRelevant('成都乒乓球不要联系我'))});
fs.writeFileSync(path.join(__dirname,'browser-helper-verification.json'),JSON.stringify({passed:true,tests,live_network_requests:0,customer_messages:0},null,2));console.log('PASS: '+tests+' isolated browser-helper permission and message-bridge checks.');
