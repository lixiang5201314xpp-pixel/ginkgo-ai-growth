/* Club-owned workbench only. Never reads tokens, cookies or customer records. */
(()=>{if(globalThis.ginkgoCaptureBridgeVersion==='1.4.5')return;globalThis.ginkgoCaptureBridgeVersion='1.4.5';
 const allowed=(location.origin==='https://qiuchen.yinxingpingpang.com'||location.origin==='http://127.0.0.1:8796')&&location.pathname.startsWith('/api/match-center/growth/');
 if(!allowed)return;
 chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id===chrome.runtime.id&&message?.type==='GINKGO_COLLECTION_STATUS'){
   const s=message.report;if(!s||s.helper_version!=='1.4.5'){reply({ok:false});return}
   let card=document.querySelector('#ginkgo-local-helper-status');
   if(!card){card=document.createElement('section');card.id='ginkgo-local-helper-status';card.className='card sectionGap';(document.querySelector('main')||document.body).prepend(card)}
   const phase={search:'读取搜索结果',open_title:'打开下一条原帖',await_title:'核验原帖已打开',detail:'读取原帖',cooldown:'本轮结束，等待下一轮'}[s.phase]||'准备中';
   const next=typeof s.next_at==='number'?new Date(s.next_at).toLocaleTimeString('zh-CN',{hour12:false}):'无';
   card.replaceChildren();
   for(const line of [`本机助手 ${s.helper_version} · ${s.platform||'未选择平台'}`,
    `${s.status==='running'?'运行中':'已暂停'} · ${phase}`,
    `已完成 ${Number(s.completed_rounds)||0} 轮；连续无有效新增 ${Number(s.empty_rounds)||0} 轮；累计有效新增 ${Number(s.total_added)||0} 条；下次执行 ${next}`,
    `未完整读取 ${Number(s.partial_rounds)||0} 轮；跳过未就绪原帖 ${Number(s.failed_posts)||0} 条。加载故障不计为空线索。`,
    s.reason?`暂停原因：${String(s.reason).slice(0,240)}`:'',
    s.last_skipped_reason?`最近跳过：${String(s.last_skipped_reason).slice(0,240)}`:'',
    s.wait_reason?`加载提示：${String(s.wait_reason).slice(0,240)}`:'',
    s.observed_page?`当前公开页：${String(s.observed_page).slice(0,240)}`:'',
    s.attempted_page?`目标公开页：${String(s.attempted_page).slice(0,240)}`:'',
    `最近状态：${new Date(s.updated_at).toLocaleString('zh-CN',{hour12:false})}。这是本机运行状态，不等于已联系客户。`]){
    if(!line)continue;const p=document.createElement('p');p.textContent=line;card.append(p);
   }
   reply({ok:true});return;
  }
  if(sender.id===chrome.runtime.id&&message?.type==='GINKGO_AUTO_CAPTURE'){
   const payload=message.payload;
   if(!Array.isArray(payload?.items)||!payload.items.length||payload.items.length>20||!payload.batch_id){reply({ok:false,error:'采集批次无效'});return}
   const finish=e=>{if(e.source!==window||e.origin!==location.origin||e.data?.type!=='GINKGO_AUTO_CAPTURE_RESULT'||e.data?.batch_id!==payload.batch_id)return;clearTimeout(timer);window.removeEventListener('message',finish);reply(e.data)};
   const timer=setTimeout(()=>{window.removeEventListener('message',finish);reply({ok:false,error:'工作台未响应；请刷新已更新的工作台并登录'})},20000);
   window.addEventListener('message',finish);window.postMessage({type:'GINKGO_AUTO_CAPTURE',payload},location.origin);return true;
  }
  if(sender.id!==chrome.runtime.id||message?.type!=='GINKGO_CAPTURE')return;
  const payload=message.payload;if(!Array.isArray(payload?.items)||!payload.items.length||payload.items.length>20)return;
  sessionStorage.setItem('ginkgo_external_capture',JSON.stringify(payload));
  window.postMessage({type:'GINKGO_EXTERNAL_CAPTURE',version:'1.3.0'},location.origin);reply({received:true,imported:false});
 });
})();
