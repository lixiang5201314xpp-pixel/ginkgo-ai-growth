/* Club-owned workbench only. Never reads tokens, cookies or customer records. */
(()=>{if(globalThis.ginkgoCaptureBridgeInstalled)return;globalThis.ginkgoCaptureBridgeInstalled=true;
 const allowed=(location.origin==='https://qiuchen.yinxingpingpang.com'||location.origin==='http://127.0.0.1:8796')&&location.pathname.startsWith('/api/match-center/growth/');
 if(!allowed)return;
 chrome.runtime.onMessage.addListener((message,sender,reply)=>{
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
