const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert'),{randomUUID}=require('crypto');
let passed=0;
function fixture(platform='xiaohongshu'){
 const store={},alarms=[],updates=[],messages=[],reports=[],listeners={},pages=[];
 let tab={id:5,url:platform==='douyin'?'https://www.douyin.com/search/成都乒乓球?type=video':'https://www.xiaohongshu.com/search_result?keyword=成都乒乓球'},reply={added_valid:1,sent:0};
 const sb={URL,Date,crypto:{randomUUID},console,importScripts(){},chrome:{
  storage:{local:{get:async k=>({[k]:store[k]}),set:async d=>Object.assign(store,structuredClone(d))}},
  alarms:{create:async(n,d)=>alarms.push(d),clear:async()=>true,onAlarm:{addListener:f=>listeners.alarm=f}},
  tabs:{get:async()=>tab,query:async()=>[{id:9}],update:async(id,d)=>{updates.push(d);tab={...tab,...d}}},
  scripting:{executeScript:async d=>{if(!d.func)return [];const result=pages.shift();if(platform==='douyin'&&result?.kind==='search'&&!('search_sort' in result))result.search_sort='latest';return [{result}]}},
  runtime:{id:'own',getURL:p=>'chrome-extension://own/'+p,
   sendMessage:async()=>{},onMessage:{addListener:f=>listeners.message=f},onStartup:{addListener:f=>listeners.startup=f}}
 }};
 sb.chrome.tabs.sendMessage=async(id,m)=>{if(m.type==='GINKGO_COLLECTION_STATUS'){reports.push(m.report);return {ok:true}}messages.push(m);return {ok:true,result:reply}};
 vm.createContext(sb);vm.runInContext(fs.readFileSync(path.join(__dirname,'browser-helper/capture.js'),'utf8'),sb);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'browser-helper/continuous.js'),'utf8'),sb);
 async function message(m,sender={id:'own',url:'chrome-extension://own/popup.html'}){
  let resolve;const wait=new Promise(r=>resolve=r);
  const keep=listeners.message(m,sender,resolve);
  return keep?wait:undefined;
 }
 const get=()=>store.ginkgo_continuous_v1;
 const tick=async()=>{if(get())get().next_at=0;await vm.runInContext('tick()',sb)};
 const start=async()=>{pages.push({kind:'search',links:[]});return message({type:'GINKGO_CONTINUOUS_START',tab_id:5,destination:'https://qiuchen.yinxingpingpang.com/api/match-center/growth/'})};
 return {store,alarms,updates,messages,reports,pages,listeners,get,tick,start,message,
  setUrl:u=>tab.url=u,setReply:r=>reply=r};
}
async function test(name,fn){await fn();passed++;console.log('PASS '+name)}
(async()=>{
 await test('popup-only start and explicit allowed destination',async()=>{const f=fixture();assert.equal(await f.message({type:'GINKGO_CONTINUOUS_START'},{id:'other',url:'https://evil.invalid'}),undefined);const r=await f.message({type:'GINKGO_CONTINUOUS_START',destination:'https://evil.invalid'});assert.equal(r.ok,false);assert.equal(f.get(),undefined)});
 await test('search navigation stays in granted origin and caps five posts',async()=>{const f=fixture();await f.start();f.pages.push({kind:'search',links:['https://evil.invalid/explore/1',...Array.from({length:9},(_,i)=>'https://www.xiaohongshu.com/explore/'+i)]});await f.tick();assert.equal(f.updates.length,1);assert.equal(f.get().queue.length,4);assert.equal(f.updates[0].url,'https://www.xiaohongshu.com/explore/0')});
 await test('detail intake stores id/body before transmission and counts actual valid additions',async()=>{const f=fixture();await f.start();f.pages.push({kind:'search',links:['https://www.xiaohongshu.com/explore/1']});await f.tick();f.pages.push({kind:'detail',source_url:'https://www.xiaohongshu.com/explore/1',captured_at:new Date().toISOString(),items:[{excerpt:'成都想找乒乓球教练'}]});await f.tick();assert.equal(f.messages.length,1);assert(f.messages[0].payload.batch_id);assert.equal(f.get().total_added,1);assert.equal(f.get().phase,'cooldown');assert(f.get().next_at-Date.now()>479000);assert.equal(f.get().last_receipt.sent,0)});
 await test('three genuinely empty rounds pause',async()=>{const f=fixture();await f.start();f.get().phase='detail';f.get().queue=[];f.get().search_url='https://www.xiaohongshu.com/search_result?keyword=x';for(let i=0;i<3;i++){f.get().phase='detail';f.get().visited=[];f.get().round_added=0;f.setUrl('https://www.xiaohongshu.com/explore/'+i);f.pages.push({kind:'detail',source_url:'https://www.xiaohongshu.com/explore/'+i,items:[]});await f.tick()}assert.equal(f.get().status,'paused');assert.equal(f.get().empty_rounds,3)});
 await test('captcha or login stops without counting empty round',async()=>{const f=fixture();await f.start();f.pages.push({blocked:'平台需要安全验证'});await f.tick();assert.equal(f.get().status,'paused');assert.equal(f.get().empty_rounds,0);assert.equal(f.messages.length,0)});
 await test('leaving origin stops without reading a private or foreign page',async()=>{const f=fixture();await f.start();f.setUrl('https://evil.invalid/chat');await f.tick();assert.equal(f.get().status,'paused');assert.equal(f.messages.length,0)});
 await test('browser restart requires fresh explicit invocation',async()=>{const f=fixture();await f.start();await f.listeners.startup();assert.equal(f.get().status,'paused');assert.match(f.get().reason,/浏览器已重启/)});
 await test('operator stop clears future schedule',async()=>{const f=fixture();await f.start();await f.message({type:'GINKGO_CONTINUOUS_STOP'});assert.equal(f.get().status,'paused');assert.equal(f.get().next_at,null)});
 await test('Douyin modal start retains the real parent search without modal selector',async()=>{
  const f=fixture('douyin');f.setUrl('https://www.douyin.com/search/成都乒乓球?type=video&modal_id=7679679918087250107');
  f.pages.push({kind:'detail',source_url:'https://www.douyin.com/video/7679679918087250107',items:[]});
  const r=await f.message({type:'GINKGO_CONTINUOUS_START',tab_id:5,destination:'https://qiuchen.yinxingpingpang.com/api/match-center/growth/'});
  assert.equal(r.ok,true);assert.equal(new URL(f.get().search_url).pathname,'/search/%E6%88%90%E9%83%BD%E4%B9%92%E4%B9%93%E7%90%83');
  assert.equal(new URL(f.get().search_url).searchParams.get('type'),'video');assert.equal(new URL(f.get().search_url).searchParams.has('modal_id'),false);
 });
 await test('Douyin two-title flow opens canonical pages before intake and returns to search for the next title',async()=>{
  const f=fixture('douyin');await f.start();
  f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练甲','成都想找乒乓球教练乙']},{clicked:true});
  await f.tick();assert.equal(f.get().phase,'await_title');assert.equal(f.get().queue.length,1);
  const first='https://www.douyin.com/video/7679679918087250107';
  f.setUrl('https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250107');
  f.pages.push({kind:'detail',needs_canonical:true,source_url:first,items:[{excerpt:'成都想找乒乓球教练甲'}]});
  await f.tick();assert.equal(f.updates.at(-1).url,first);assert.equal(f.messages.length,0);
  f.pages.push({kind:'detail',source_url:first,captured_at:new Date().toISOString(),items:[{excerpt:'成都想找乒乓球教练甲',posted_text:'发布时间：2026-08-30 12:40'}]});
  await f.tick();assert.equal(f.messages.length,1);assert.equal(f.get().phase,'open_title');assert(f.updates.at(-1).url.includes('/search/'));
  f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练乙']},{clicked:true});
  await f.tick();assert.equal(f.get().phase,'await_title');
  const second='https://www.douyin.com/video/7679679918087250108';
  f.setUrl('https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250108');
  f.pages.push({kind:'detail',needs_canonical:true,source_url:second,items:[]});await f.tick();
  assert.equal(f.updates.at(-1).url,second);assert.equal(f.messages.length,1);
  f.pages.push({kind:'detail',source_url:second,captured_at:new Date().toISOString(),items:[]});await f.tick();
  assert.equal(f.get().completed_rounds,1);assert.equal(f.get().phase,'cooldown');assert.equal(f.get().total_added,1);
 });
 await test('missing click return is verified on the next page rather than treated as a failed click or clicked twice',async()=>{
  const f=fixture('douyin');await f.start();
  f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练']},undefined);
  await f.tick();assert.equal(f.get().status,'running');assert.equal(f.get().phase,'await_title');assert.equal(f.get().open_acknowledged,false);
  const source='https://www.douyin.com/video/7679679918087250107';f.setUrl(source);
  f.pages.push({kind:'detail',source_url:source,captured_at:new Date().toISOString(),items:[]});await f.tick();
  assert.equal(f.get().completed_rounds,1);assert.equal(f.get().phase,'cooldown');assert.equal(f.messages.length,0);
 });
 await test('real click failure pauses with a readable reason and reports no private state',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练']},{scheduled:true});await f.tick();
  for(let i=0;i<3;i++){f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练']});await f.tick()}
  assert.equal(f.get().status,'paused');assert.match(f.get().reason,/连续3次检查/);
  const report=f.reports.at(-1);assert.equal(report.helper_version,'1.4.9');assert.equal(report.status,'paused');
  assert.equal('pending_batch' in report,false);assert.equal('destination' in report,false);assert.equal(f.messages.length,0);
 });
 await test('actual canonical document wins when tab metadata still contains the search URL',async()=>{
  const f=fixture('douyin');f.pages.push({kind:'detail',source_url:'https://www.douyin.com/video/7669322400018301029',display_url:'https://www.douyin.com/video/7669322400018301029',items:[]});
  await f.message({type:'GINKGO_CONTINUOUS_START',tab_id:5,destination:'https://qiuchen.yinxingpingpang.com/api/match-center/growth/'});
  f.pages.push({kind:'detail',source_url:'https://www.douyin.com/video/7669322400018301029',display_url:'https://www.douyin.com/video/7669322400018301029',items:[]});await f.tick();
  assert.equal(f.updates.length,0);assert.equal(f.get().completed_rounds,1);assert.equal(f.messages.length,0);
 });
 await test('navigation waits for two transient search documents without a second click',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练']},{scheduled:true});await f.tick();
  for(let i=0;i<2;i++){f.pages.push({kind:'search',links:[],targets:['成都想找乒乓球教练']});await f.tick();assert.equal(f.get().status,'running')}
  const url='https://www.douyin.com/video/7669322400018301029';f.setUrl(url);
  f.pages.push({kind:'detail',display_url:url,source_url:url,items:[]});await f.tick();
  assert.equal(f.get().completed_rounds,1);assert.equal(f.get().navigation_checks,0);assert.equal(f.get().empty_rounds,1);
 });
 await test('actual foreign document never passes a stale permitted tab URL',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push({kind:'detail',display_url:'https://evil.invalid/video/1',source_url:'https://evil.invalid/video/1',items:[]});await f.tick();
  assert.equal(f.get().status,'paused');assert.match(f.get().reason,/页面实际地址离开授权平台/);assert.equal(f.messages.length,0);
 });
 await test('observed modal href is canonicalized before navigation',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push({kind:'search',links:['https://www.douyin.com/search/成都乒乓球?modal_id=7669322400018301029'],targets:[]});await f.tick();
  assert.equal(f.updates.at(-1).url,'https://www.douyin.com/video/7669322400018301029');assert.equal(f.get().current_target.url,f.updates.at(-1).url);
 });
 await test('old detail document is not reprocessed while returning to search for the next round',async()=>{
  const f=fixture('douyin');await f.start();const url='https://www.douyin.com/video/7669322400018301029';f.setUrl(url);
  f.pages.push({kind:'detail',display_url:url,source_url:url,items:[{excerpt:'成都想找乒乓球教练'}]});await f.tick();
  assert.equal(f.get().status,'running');assert.equal(f.messages.length,0);assert.equal(f.get().completed_rounds,0);
 });
 await test('missing navigation inspection waits without treating it as an empty completed round',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push(undefined);await f.tick();
  assert.equal(f.get().status,'running');assert.equal(f.get().navigation_checks,1);assert.equal(f.get().completed_rounds,0);assert.equal(f.get().empty_rounds,0);assert.equal(f.messages.length,0);
 });
 await test('rendered search results are usable while unrelated page resources keep loading',async()=>{
  const f=fixture();await f.start();f.pages.push({kind:'search',ready_state:'loading',links:['https://www.xiaohongshu.com/explore/1']});await f.tick();
  assert.equal(f.get().phase,'detail');assert.equal(f.updates.at(-1).url,'https://www.xiaohongshu.com/explore/1');
 });
 await test('verified visible detail is collected without waiting for media loading to finish',async()=>{
  const f=fixture();await f.start();f.pages.push({kind:'search',links:['https://www.xiaohongshu.com/explore/1']});await f.tick();
  f.pages.push({kind:'detail',ready_state:'loading',source_url:'https://www.xiaohongshu.com/explore/1',items:[{excerpt:'成都想找乒乓球教练'}]});await f.tick();
  assert.equal(f.messages.length,1);assert.equal(f.get().completed_rounds,1);
 });
 await test('one timed-out original does not discard the remaining originals or become a fake empty round',async()=>{
  const f=fixture();await f.start();f.pages.push({kind:'search',links:['https://www.xiaohongshu.com/explore/1','https://www.xiaohongshu.com/explore/2']});await f.tick();
  for(let i=0;i<3;i++){f.pages.push({pending:true,display_url:'https://www.xiaohongshu.com/explore/1'});await f.tick()}
  assert.equal(f.get().status,'running');assert.equal(f.updates.at(-1).url,'https://www.xiaohongshu.com/explore/2');assert.equal(f.get().round_failed,1);
  f.pages.push({kind:'detail',source_url:'https://www.xiaohongshu.com/explore/2',items:[]});await f.tick();
  assert.equal(f.get().completed_rounds,0);assert.equal(f.get().empty_rounds,0);assert.equal(f.get().partial_rounds,1);assert.equal(f.get().phase,'cooldown');
 });
 await test('three partial failed rounds pause separately without being counted as no-demand rounds',async()=>{
  const f=fixture();await f.start();
  for(let round=0;round<3;round++){
   f.get().phase='search';f.get().round_failed=0;f.get().queue=[];f.get().round_added=0;
   f.setUrl('https://www.xiaohongshu.com/search_result?keyword=x');
   f.pages.push({kind:'search',links:['https://www.xiaohongshu.com/explore/'+round]});await f.tick();
   for(let i=0;i<3;i++){f.pages.push({pending:true});await f.tick()}
  }
  assert.equal(f.get().status,'paused');assert.equal(f.get().empty_rounds,0);assert.equal(f.get().completed_rounds,0);assert.equal(f.get().partial_rounds,3);
 });
 await test('a loading Douyin modal still resolves its observed original before waiting on media',async()=>{
  const f=fixture('douyin');await f.start();
  f.pages.push({kind:'search',targets:['成都想找乒乓球教练'],links:[]},{scheduled:true});await f.tick();
  const original='https://www.douyin.com/video/7679679918087250107';
  f.setUrl('https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250107');
  f.pages.push({kind:'detail',needs_canonical:true,ready_state:'loading',source_url:original,items:[]});await f.tick();
  assert.equal(f.updates.at(-1)?.url,original);assert.equal(f.get().navigation_checks,0);
  assert.equal(f.get().current_target.url,original);assert.equal(f.messages.length,0);
 });
 await test('identity-pinned rendered modal is read in place without independent-page navigation',async()=>{
  const f=fixture('douyin');await f.start();f.pages.push({kind:'search',targets:['成都有人一起练单球吗#乒乓球搭子'],links:[]},{scheduled:true});await f.tick();
  const original='https://www.douyin.com/video/7679679918087250107';const modal='https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250107';f.setUrl(modal);
  f.pages.push({kind:'detail',needs_canonical:false,modal_identity_verified:true,ready_state:'loading',display_url:modal,source_url:original,captured_at:new Date().toISOString(),items:[{excerpt:'成都有人一起练单球吗#乒乓球搭子',posted_text:'1天前'}]});await f.tick();
  assert.equal(f.updates.length,0);assert.equal(f.messages.length,1);assert.equal(f.get().completed_rounds,1);assert.equal(f.get().phase,'cooldown');assert.equal(f.messages[0].payload.observation.page_url,original);
 });
 await test('a pending batch cannot be sent as a different verified modal',async()=>{
  const f=fixture('douyin');await f.start();f.get().phase='detail';f.get().pending_batch={batch_id:'old-pending',observation:{page_url:'https://www.douyin.com/video/7679679918087250108'},items:[{excerpt:'旧作品'}]};
  const original='https://www.douyin.com/video/7679679918087250107',modal='https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250107';f.setUrl(modal);
  f.pages.push({kind:'detail',needs_canonical:false,modal_identity_verified:true,display_url:modal,source_url:original,items:[]});await f.tick();
  assert.equal(f.get().status,'paused');assert.equal(f.get().pending_batch.batch_id,'old-pending');assert.equal(f.messages.length,0);
 });
 await test('a directly started original that times out is a failed read, not a completed empty round',async()=>{
  const f=fixture('douyin'),original='https://www.douyin.com/video/7679679918087250107';f.setUrl(original);
  f.pages.push({kind:'detail',source_url:original,display_url:original,items:[]});
  await f.message({type:'GINKGO_CONTINUOUS_START',tab_id:5,destination:'https://qiuchen.yinxingpingpang.com/api/match-center/growth/'});
  for(let i=0;i<3;i++){f.pages.push({pending:true,display_url:original});await f.tick()}
  assert.equal(f.get().failed_posts,1);assert.equal(f.get().partial_rounds,1);
  assert.equal(f.get().completed_rounds,0);assert.equal(f.get().empty_rounds,0);assert.equal(f.get().status,'paused');
 });
 await test('an uncertain stored batch cannot be discarded by a modal redirect',async()=>{
  const f=fixture('douyin');await f.start();f.get().phase='detail';f.get().pending_batch={batch_id:'pending',items:[{excerpt:'成都想找乒乓球教练'}]};
  f.setUrl('https://www.douyin.com/search/成都乒乓球?modal_id=7679679918087250107');
  f.pages.push({kind:'detail',needs_canonical:true,ready_state:'loading',source_url:'https://www.douyin.com/video/7679679918087250107',items:[]});await f.tick();
  assert.equal(f.get().status,'paused');assert.equal(f.get().pending_batch.batch_id,'pending');assert.equal(f.updates.length,0);assert.equal(f.messages.length,0);
 });
 await test('Douyin search reload restores latest order before using old default results',async()=>{
  const f=fixture('douyin');await f.start();
  f.pages.push({kind:'search',search_sort:'default',targets:['成都想找乒乓球教练旧帖'],links:[]},{pending:true,action:'open_filters'});await f.tick();
  assert.equal(f.get().phase,'search');assert.equal(f.get().sort_checks,1);assert.equal(f.get().current_target,undefined);assert.equal(f.messages.length,0);
  f.pages.push({kind:'search',search_sort:'default',targets:['成都想找乒乓球教练旧帖'],links:[]},{pending:true,action:'select_latest'});await f.tick();
  assert.equal(f.get().phase,'search');assert.equal(f.get().sort_checks,2);
  f.pages.push({kind:'search',search_sort:'latest',targets:['成都想找乒乓球教练新帖'],links:[]},{scheduled:true});await f.tick();
  assert.equal(f.get().phase,'await_title');assert.equal(f.get().current_target.title,'成都想找乒乓球教练新帖');assert.equal(f.get().sort_checks,0);
 });
 await test('latest sorting failure pauses without fake empty rounds or repeated unbounded clicks',async()=>{
  const f=fixture('douyin');await f.start();
  for(let i=0;i<3;i++){f.pages.push({kind:'search',search_sort:'unknown',targets:['成都想找乒乓球教练旧帖']},{pending:true,action:'open_filters'});await f.tick()}
  assert.equal(f.get().status,'paused');assert.match(f.get().reason,/最新发布/);assert.equal(f.get().empty_rounds,0);assert.equal(f.get().completed_rounds,0);assert.equal(f.messages.length,0);
 });
 await test('returning for a queued title also waits for latest sorting before clicking',async()=>{
  const f=fixture('douyin');await f.start();f.get().phase='open_title';f.get().current_target={title:'成都想找乒乓球教练新帖'};
  f.pages.push({kind:'search',search_sort:'default',targets:['成都想找乒乓球教练旧帖']},{pending:true,action:'select_latest'});await f.tick();
  assert.equal(f.get().phase,'open_title');assert.equal(f.get().sort_checks,1);assert.equal(f.get().open_acknowledged,undefined);
  f.pages.push({kind:'search',search_sort:'latest',targets:['成都想找乒乓球教练新帖']},{scheduled:true});await f.tick();assert.equal(f.get().phase,'await_title');
 });
 await test('same-ID video to note redirect is read once without canonical navigation loop',async()=>{
  const f=fixture('douyin');await f.start();
  const video='https://www.douyin.com/video/7702708741762243570',note=video.replace('/video/','/note/');
  f.pages.push({kind:'search',links:[video]});await f.tick();f.setUrl(note);
  f.pages.push({kind:'detail',display_url:note,source_url:video,items:[{excerpt:'成都有人一起练单球吗#乒乓球搭子'}],captured_at:new Date().toISOString()});await f.tick();
  assert.equal(f.messages.length,1);assert.equal(f.updates.length,1);assert.equal(f.get().completed_rounds,1);assert.equal(f.get().phase,'cooldown');assert.equal(f.messages[0].payload.observation.page_url,video);
 });
 fs.writeFileSync(path.join(__dirname,'continuous-verification.json'),JSON.stringify({passed:true,tests:passed,network_calls:0,customer_messages:0},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
