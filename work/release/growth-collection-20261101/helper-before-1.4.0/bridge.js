/* Club-owned workbench only. Never reads tokens, cookies or customer records. */
(()=>{if(globalThis.ginkgoCaptureBridgeInstalled)return;globalThis.ginkgoCaptureBridgeInstalled=true;
 const allowed=(location.origin==='https://qiuchen.yinxingpingpang.com'||location.origin==='http://127.0.0.1:8796')&&location.pathname.startsWith('/api/match-center/growth/');
 if(!allowed)return;
 chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id!==chrome.runtime.id||message?.type!=='GINKGO_CAPTURE')return;
  const payload=message.payload;if(!Array.isArray(payload?.items)||!payload.items.length||payload.items.length>20)return;
  sessionStorage.setItem('ginkgo_external_capture',JSON.stringify(payload));
  window.postMessage({type:'GINKGO_EXTERNAL_CAPTURE',version:'1.3.0'},location.origin);reply({received:true,imported:false});
 });
})();
