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
  const report={helper_version:'1.4.2',status:s.status,platform:s.platform,phase:s.phase,
   reason:s.reason||'',completed_rounds:s.completed_rounds||0,empty_rounds:s.empty_rounds||0,
   total_added:s.total_added||0,next_at:s.next_at||null,last_page:s.last_page||'',
   updated_at:new Date().toISOString()};
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
 const rows=await chrome.scripting.executeScript({target:{tabId},func:()=>globalThis.GinkgoCapture.inspectPublicPage()});
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
async function nextTarget(s,target,searchAlreadyOpen=false){
 if(typeof target==='string'){
  if(!sameOrigin(target,s))throw Error('原帖链接离开授权平台');
  s.phase='detail';await save(s);await chrome.tabs.update(s.tab_id,{url:target});
 }else{
  if(!target?.title||target.title.length>500)throw Error('搜索标题无效');
   s.current_target=target;s.phase=searchAlreadyOpen?'await_title':'open_title';await save(s);
  if(searchAlreadyOpen)await openTitle(s,target.title);
  else await chrome.tabs.update(s.tab_id,{url:s.search_url});
 }
 await later(s);
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
   s.phase='search';s.queue=[];s.visited=[];s.round_added=0;s.round_started_at=new Date().toISOString();
   await save(s);await chrome.tabs.update(s.tab_id,{url:s.search_url});await later(s);return;
  }
  const page=await inspect(s.tab_id);
  if(!page||page.blocked)throw Error(page?.blocked||'公开页面适配器未返回结果');
  if(page.kind==='search'){
   if(s.phase==='open_title'){
    await openTitle(s,s.current_target.title);await later(s);return;
   }
   if(s.phase==='await_title')throw Error('点击后尚未出现原帖详情，已暂停；未重复点击或把搜索列表当原文');
   if(s.phase!=='search')throw Error('原帖未能打开，已停止本轮，避免把搜索页当原文');
   s.queue=[...(page.links||[]).filter(x=>sameOrigin(x,s)),...(page.targets||[]).map(title=>({title}))].slice(0,5);
   if(!s.queue.length)throw Error('当前搜索页没有可核对的公开作品链接，请先正常打开结果');
   s.phase='detail';s.visited=[];s.round_added=0;
   const target=s.queue.shift();await nextTarget(s,target,true);return;
  }
  if(page.kind!=='detail')throw Error('此页面暂未支持连续采集，请打开公开搜索或作品详情');
  // Search modals can omit the work's own publication date. Open the canonical
  // URL derived from that displayed work id, then read it again on its own page.
  // Never substitute a comment's timestamp for the original work's timestamp.
  if(s.platform==='douyin'&&new URL(tab.url).pathname.startsWith('/search/')&&sameOrigin(page.source_url,s)){
   s.phase='detail';await save(s);await chrome.tabs.update(s.tab_id,{url:page.source_url});await later(s);return;
  }
  const canonical=new URL(page.source_url);canonical.search='';canonical.hash='';
  if(s.visited.includes(canonical.href))throw Error('页面跳转到已处理原帖，停止重复采集');
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
  s.completed_rounds=(s.completed_rounds||0)+1;s.empty_rounds=s.round_added?0:(s.empty_rounds||0)+1;
  s.completed_at=new Date().toISOString();
  if(s.empty_rounds>=3){await pause(s,'连续3轮没有有效新线索，已暂停；可手动重新启动');return}
  if(!s.search_url){await pause(s,'当前原帖采集完成；请从搜索结果页启动以连续扫描新作品');return}
  s.phase='cooldown';await later(s,8*60000);
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
   round_started_at:new Date().toISOString(),next_at:Date.now()};
  if(!['search','detail'].includes(p.kind))throw Error('请从公开搜索结果或作品详情页启动');
  await save(s);await chrome.alarms.create(ALARM,{when:Date.now()+1000});return {ok:true,state:s};
 })().then(reply,e=>reply({ok:false,error:e.message}));return true;
});
// activeTab access does not survive a browser restart; require an explicit fresh start.
chrome.runtime.onStartup.addListener(async()=>{const s=await state();if(s.status==='running')await pause(s,'浏览器已重启，请在原平台手动重新启动以取得临时访问权限')});
