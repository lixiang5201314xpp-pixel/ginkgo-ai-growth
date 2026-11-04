/* Bounded, owner-started public-page collection. No platform fetch, cookies or sending. */
'use strict';
importScripts('capture.js');
const STATE='ginkgo_continuous_v1',ALARM='ginkgo-collect-next';
const DESTINATIONS=['https://qiuchen.yinxingpingpang.com/api/match-center/growth/','http://127.0.0.1:8796/api/match-center/growth/'];
let executing=false;
async function state(){return (await chrome.storage.local.get(STATE))[STATE]||{status:'stopped'}}
async function publishStatus(s){
 if(!DESTINATIONS.includes(s.destination))return;
 try{
  const tabs=await chrome.tabs.query({url:s.destination+'*'});if(tabs.length!==1)return;
  await chrome.scripting.executeScript({target:{tabId:tabs[0].id},files:['bridge.js']});
  const publicPath=value=>{try{const u=new URL(value);return u.origin+u.pathname}catch{return ''}};
  const report={helper_version:'1.4.7',status:s.status,platform:s.platform,phase:s.phase,
   reason:s.reason||'',completed_rounds:s.completed_rounds||0,empty_rounds:s.empty_rounds||0,
   total_added:s.total_added||0,next_at:s.next_at||null,last_page:s.last_page||'',
   observed_page:publicPath(s.observed_page),attempted_page:publicPath(s.attempted_page),
   wait_reason:s.wait_reason||'',failed_posts:s.failed_posts||0,partial_rounds:s.partial_rounds||0,
   last_skipped_reason:s.last_skipped_reason||'',updated_at:new Date().toISOString()};
  await chrome.tabs.sendMessage(tabs[0].id,{type:'GINKGO_COLLECTION_STATUS',report});
 }catch{ /* Local read-only status must never stop collection or send content. */ }
}
async function save(s){await chrome.storage.local.set({[STATE]:s});await publishStatus(s)}
async function pause(s,reason){s.status='paused';s.reason=reason;s.next_at=null;await save(s);await chrome.alarms.clear(ALARM);return s}
function sameOrigin(url,s){try{return new URL(url).origin===s.origin&&GinkgoCapture.platformForUrl(url)===s.platform}catch{return false}}
function searchReturnUrl(url,kind){
 const u=new URL(url);
 if(kind==='search')return u.href;
 // A user can open the popup after a search result has opened its video modal.
 // Keep the actual parent search and remove only the observed modal selector.
 if(u.pathname.startsWith('/search/')&&/^\d{10,25}$/.test(u.searchParams.get('modal_id')||'')){
  u.searchParams.delete('modal_id');return u.href;
 }
 return null;
}
async function later(s,ms=30000){s.next_at=Date.now()+ms;await save(s);await chrome.alarms.create(ALARM,{when:s.next_at})}
async function sendToWorkbench(s,bundle){
 const tabs=await chrome.tabs.query({url:s.destination+'*'});
 if(tabs.length!==1)throw Error('请保留一个已登录获客工作台标签，再继续采集');
 await chrome.scripting.executeScript({target:{tabId:tabs[0].id},files:['bridge.js']});
 const result=await chrome.tabs.sendMessage(tabs[0].id,{type:'GINKGO_AUTO_CAPTURE',payload:bundle});
 if(!result?.ok)throw Error(result?.error||'工作台未确认收到采集批次');
 return result.result;
}
async function inspect(tabId){
 await chrome.scripting.executeScript({target:{tabId},files:['capture.js']});
 const rows=await chrome.scripting.executeScript({target:{tabId},func:()=>{
  try{return globalThis.GinkgoCapture.inspectPublicPage()}
  catch(e){return {pending:true,error:String(e.message||'原帖正文尚未加载'),display_url:location.href}}
 }});
 return rows[0]?.result;
}
async function openTitle(s,title){
 const rows=await chrome.scripting.executeScript({target:{tabId:s.tab_id},func:t=>{
  try{return globalThis.GinkgoCapture.openSearchTitle(t)}catch(e){return {failed:String(e.message||'搜索标题无法打开')}}
 },args:[title]});
 const ack=rows[0]?.result;if(ack?.failed)throw Error(ack.failed);
 // A missing return value is not proof that navigation failed. Do not click
 // twice: inspect the real URL and detail page on the next scheduled step.
 s.open_acknowledged=!!(ack?.scheduled||ack?.clicked);s.phase='await_title';
}
async function recentSearchReady(s,page){
 if(s.platform!=='douyin')return true;
 if(page.search_sort==='latest'){s.sort_checks=0;s.wait_reason='';return true}
 s.sort_checks=(s.sort_checks||0)+1;
 if(s.sort_checks>3)throw Error('最新发布筛选连续3次未确认，已暂停；未采集旧排序结果');
 const rows=await chrome.scripting.executeScript({target:{tabId:s.tab_id},func:()=>{
  try{return globalThis.GinkgoCapture.ensureRecentSearch()}catch(e){return {failed:String(e.message||'最新发布筛选无法核对')}}
 }});
 const result=rows[0]?.result;if(result?.failed)throw Error(result.failed);
 if(s.sort_checks>=3)throw Error('最新发布筛选连续3次未确认，已暂停；未计为空轮');
 s.wait_reason='正在确认最新发布排序（'+s.sort_checks+'/3）';await later(s);return false;
}
async function nextTarget(s,target,searchAlreadyOpen=false){
 s.navigation_checks=0;s.wait_reason='';s.attempted_page='';
 if(typeof target==='string'){
  if(!sameOrigin(target,s))throw Error('原帖链接离开授权平台');
  const exact=GinkgoCapture.canonicalUrl(target,s.platform);
  if(!sameOrigin(exact,s))throw Error('原帖规范链接离开授权平台');
  s.current_target={url:exact};s.attempted_page=exact;
  s.phase='detail';await save(s);await chrome.tabs.update(s.tab_id,{url:exact});
 }else{
  if(!target?.title||target.title.length>500)throw Error('搜索标题无效');
   s.current_target=target;s.phase=searchAlreadyOpen?'await_title':'open_title';await save(s);
  if(searchAlreadyOpen)await openTitle(s,target.title);
  else await chrome.tabs.update(s.tab_id,{url:s.search_url});
 }
 await later(s);
}
async function waitForPage(s,reason){
 s.navigation_checks=(s.navigation_checks||0)+1;s.wait_reason=reason+'（'+s.navigation_checks+'/3）';
 if(s.navigation_checks>=3){
  // Only skip a known detail target. Never discard an uncertain delivery or
  // reinterpret a login, foreign page or unconfirmed click as a finished scan.
  if(s.phase==='detail'&&s.current_target&&!s.pending_batch){
   s.round_failed=(s.round_failed||0)+1;s.failed_posts=(s.failed_posts||0)+1;
   s.last_skipped_reason=reason+'；原帖连续3次未就绪，已跳过';
   s.navigation_checks=0;s.wait_reason='';
   if(s.queue.length){const next=s.queue.shift();await nextTarget(s,next);return}
   await completeRound(s);return;
  }
  throw Error(reason+'；连续3次检查仍未就绪，已暂停，未重复点击或读取搜索列表');
 }
 await later(s);
}
async function completeRound(s){
 s.completed_at=new Date().toISOString();
 if(s.round_failed){
  s.partial_rounds=(s.partial_rounds||0)+1;
  s.failed_rounds=s.round_added?0:(s.failed_rounds||0)+1;
  if(s.failed_rounds>=3){await pause(s,'连续3轮有未能加载的原帖且没有有效新增，已暂停；未计为无需求空轮');return}
 }else{
  s.completed_rounds=(s.completed_rounds||0)+1;s.failed_rounds=0;
  s.empty_rounds=s.round_added?0:(s.empty_rounds||0)+1;
  if(s.empty_rounds>=3){await pause(s,'连续3轮没有有效新线索，已暂停；可手动重新启动');return}
 }
 if(!s.search_url){await pause(s,'当前原帖采集完成；请从搜索结果页启动以连续扫描新作品');return}
 s.phase='cooldown';await later(s,8*60000);
}
async function tick(){
 if(executing)return;
 executing=true;let s;
 try{
  s=await state();if(s.status!=='running')return;
  if(s.next_at&&s.next_at>Date.now()+1000)return;
  const tab=await chrome.tabs.get(s.tab_id);
  if(!tab||!sameOrigin(tab.url,s))throw Error('采集标签已关闭或离开授权平台，请在原平台重新启动');
  if(s.phase==='cooldown'){
   s.phase='search';s.queue=[];s.visited=[];s.round_added=0;s.round_failed=0;s.round_started_at=new Date().toISOString();
   await save(s);await chrome.tabs.update(s.tab_id,{url:s.search_url});await later(s);return;
  }
  const page=await inspect(s.tab_id);
  if(!page){await waitForPage(s,'页面读取上下文仍在切换');return}
  if(page.blocked)throw Error(page.blocked);
  const displayed=page.display_url||tab.url;
  if(!sameOrigin(displayed,s))throw Error('页面实际地址离开授权平台，已停止读取');
  s.observed_page=displayed;
  // A rendered modal id already pins the selected public original. Resolve it
  // before media readiness checks: a streaming resource can keep readyState at
  // loading indefinitely. Never redirect away from a batch awaiting a receipt.
  if(s.platform==='douyin'&&page.kind==='detail'&&new URL(displayed).pathname.startsWith('/search/')){
   if(s.pending_batch)throw Error('已有批次等待工作台确认，已暂停并保留原批次，未跳转或重复发送');
   const original=GinkgoCapture.canonicalUrl(displayed,s.platform);
   if(original===displayed||!sameOrigin(page.source_url,s)||original!==GinkgoCapture.canonicalUrl(page.source_url,s.platform))
    throw Error('弹窗地址与原帖身份不一致，已停止读取');
   await nextTarget(s,original);return;
  }
  const readable=(page.kind==='search'&&((page.links||[]).length||(page.targets||[]).length))||
   (page.kind==='detail'&&page.source_url&&Array.isArray(page.items)&&!page.needs_canonical);
  if(page.pending||(page.ready_state==='loading'&&!readable)){await waitForPage(s,page.error||'页面仍在加载');return}
  if(page.kind==='search'){
   if(['search','open_title'].includes(s.phase)&&!await recentSearchReady(s,page))return;
   if(s.phase==='open_title'){
    if(!(page.targets||[]).length&&!(page.links||[]).length){await waitForPage(s,'搜索结果仍在加载');return}
    await openTitle(s,s.current_target.title);await later(s);return;
   }
   if(s.phase==='await_title'||s.phase==='detail'){
    await waitForPage(s,'正在等待原帖详情显示');return;
   }
   if(s.phase!=='search')throw Error('当前页面不是预期原帖，已停止本轮');
   s.queue=[...(page.links||[]).filter(x=>sameOrigin(x,s)),...(page.targets||[]).map(title=>({title}))].slice(0,5);
   if(!s.queue.length){await waitForPage(s,'当前搜索页未显示可核对的公开作品');return}
   s.phase='detail';s.visited=[];s.round_added=0;
   const target=s.queue.shift();await nextTarget(s,target,true);return;
  }
  if(page.kind!=='detail')throw Error('此页面暂未支持连续采集，请打开公开搜索或作品详情');
  if(s.phase==='search'){await waitForPage(s,'正在等待搜索结果页加载');return}
  const canonical=new URL(page.source_url);canonical.search='';canonical.hash='';
  if(s.visited.includes(canonical.href)){await waitForPage(s,'页面仍显示上一条原帖');return}
  if(s.current_target?.url){
   const expected=new URL(s.current_target.url);expected.search='';expected.hash='';
   if(expected.pathname.startsWith('/video/')&&canonical.href!==expected.href){await waitForPage(s,'尚未显示目标原帖');return}
  }
  s.navigation_checks=0;s.wait_reason='';
  // Persist the batch before transmission: network retries reuse the same id/body.
  if(!s.pending_batch&&page.items.length){
   s.pending_batch={batch_id:crypto.randomUUID(),items:page.items,observation:{
    page_url:page.source_url,observed_at:page.captured_at,read_scope:'rendered_public_page'}};
   await save(s);
  }
  if(s.pending_batch){
   const r=await sendToWorkbench(s,s.pending_batch);
   s.round_added+=(r.added_valid||0);s.total_added=(s.total_added||0)+(r.added_valid||0);
   s.last_receipt=r;s.pending_batch=null;
  }
  s.visited.push(canonical.href);s.last_page=page.source_url;s.last_read_at=new Date().toISOString();
  if(s.queue.length){const target=s.queue.shift();await nextTarget(s,target);return}
  await completeRound(s);
 }catch(e){if(s)await pause(s,e.message||'采集失败，请查看工作台')}
 finally{executing=false}
}
chrome.alarms.onAlarm.addListener(a=>{if(a.name===ALARM)tick()});
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
 // Only the extension popup can start or stop a session; content pages cannot.
 if(sender.id!==chrome.runtime.id||!sender.url?.startsWith(chrome.runtime.getURL('popup.html')))return;
 (async()=>{
  if(m?.type==='GINKGO_CONTINUOUS_STATUS')return {ok:true,state:await state()};
  if(m?.type==='GINKGO_CONTINUOUS_STOP')return {ok:true,state:await pause(await state(),'用户停止连续采集')};
  if(m?.type!=='GINKGO_CONTINUOUS_START')return {ok:false,error:'未知操作'};
  if(!DESTINATIONS.includes(m.destination))throw Error('工作台地址无效');
  const tab=await chrome.tabs.get(m.tab_id),platform=GinkgoCapture.platformForUrl(tab.url);
  if(!['douyin','xiaohongshu','kuaishou'].includes(platform))throw Error('此平台尚未支持连续采集');
  const p=await inspect(tab.id);if(p?.blocked)throw Error(p.blocked);
  const search=searchReturnUrl(tab.url,p.kind);
  const s={status:'running',session_id:crypto.randomUUID(),tab_id:tab.id,origin:new URL(tab.url).origin,
   platform,destination:m.destination,phase:p.kind==='search'?'search':'detail',search_url:search,
   queue:[],visited:[],empty_rounds:0,completed_rounds:0,total_added:0,round_added:0,
   round_failed:0,failed_rounds:0,failed_posts:0,partial_rounds:0,
   round_started_at:new Date().toISOString(),next_at:Date.now()};
  if(!['search','detail'].includes(p.kind))throw Error('请从公开搜索结果或作品详情页启动');
  if(p.kind==='detail'){
   const original=GinkgoCapture.canonicalUrl(p.source_url||tab.url,platform);
   if(!sameOrigin(original,s))throw Error('原帖地址离开授权平台');
   s.current_target={url:original};
  }
  await save(s);await chrome.alarms.create(ALARM,{when:Date.now()+1000});return {ok:true,state:s};
 })().then(reply,e=>reply({ok:false,error:e.message}));return true;
});
// activeTab access does not survive a browser restart; require an explicit fresh start.
chrome.runtime.onStartup.addListener(async()=>{const s=await state();if(s.status==='running')await pause(s,'浏览器已重启，请在原平台手动重新启动以取得临时访问权限')});
