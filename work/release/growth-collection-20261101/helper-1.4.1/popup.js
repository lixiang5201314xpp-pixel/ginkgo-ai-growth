 'use strict';
let captured=null;
const destinations=['https://qiuchen.yinxingpingpang.com/api/match-center/growth/','http://127.0.0.1:8796/api/match-center/growth/'];
const result=document.querySelector('#result'),send=document.querySelector('#send');
chrome.storage.local.get(['destination']).then(d=>{if(destinations.includes(d.destination))document.querySelector('#destination').value=d.destination});
async function capture(mode){try{
 const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 if(!tab?.id||!GinkgoCapture.platformForUrl(tab.url))throw Error('请在外部平台的一条视频、笔记或帖子页面打开助手。');
 await chrome.scripting.executeScript({target:{tabId:tab.id},files:['capture.js']});
 const rows=await chrome.scripting.executeScript({target:{tabId:tab.id},func:(mode)=>globalThis.GinkgoCapture.collect({mode}),args:[mode]});
 captured=rows[0]?.result;if(!captured?.items.length)throw Error('没有识别到明确乒乓球求助。请展开评论，或选中一条需求再读取。');
 result.textContent='读取 '+captured.items.length+' 条待核对原文。不会自动发送消息。';
 document.querySelector('#samples').textContent=captured.items.slice(0,3).map(x=>x.excerpt).join('\n\n');send.disabled=false;
}catch(e){captured=null;send.disabled=true;result.textContent=e.message}}
document.querySelector('#capture').onclick=()=>capture('visible');
document.querySelector('#selection').onclick=()=>capture('selection');
document.querySelector('#post').onclick=()=>capture('post');
async function continuous(type){
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const r=await chrome.runtime.sendMessage({type,tab_id:tab?.id,destination:document.querySelector('#destination').value});
  if(!r?.ok)throw Error(r?.error||'连续采集没有启动');
  const s=r.state;
  const phase={search:'正在读取搜索结果',open_title:'正在打开下一条原帖',detail:'正在读取原帖',cooldown:'本轮结束，等待下一轮'}[s.phase]||'准备中';
  const next=s.next_at?`；下次执行 ${new Date(s.next_at).toLocaleTimeString('zh-CN',{hour12:false})}`:'';
  document.querySelector('#continuousState').textContent=s.status==='running'?`运行中 ${s.platform}：${phase}${next}。已完成 ${s.completed_rounds||0} 轮，连续无有效新增 ${s.empty_rounds||0} 轮，累计有效新增 ${s.total_added||0} 条。请保持浏览器与工作台登录。`:`已暂停：${s.reason||'尚未启动'}。累计有效新增 ${s.total_added||0} 条。`;
 }catch(e){document.querySelector('#continuousState').textContent=e.message}
}
document.querySelector('#continuousStart').onclick=()=>continuous('GINKGO_CONTINUOUS_START');
document.querySelector('#continuousStop').onclick=()=>continuous('GINKGO_CONTINUOUS_STOP');
continuous('GINKGO_CONTINUOUS_STATUS');
// Refresh status only while the popup is open; never leave an old “started”
// message on screen after the worker has paused or entered its cooldown.
setInterval(()=>continuous('GINKGO_CONTINUOUS_STATUS'),5000);
send.onclick=async()=>{try{
 if(!captured?.items.length)throw Error('请先读取原文');
 const destination=document.querySelector('#destination').value;if(!destinations.includes(destination))throw Error('工作台地址无效');
 await chrome.storage.local.set({destination});
 const tabs=await chrome.tabs.query({url:destination+'*'});let tab=tabs[0];
 if(!tab){tab=await chrome.tabs.create({url:destination});await new Promise(resolve=>setTimeout(resolve,1000))}
 await chrome.scripting.executeScript({target:{tabId:tab.id},files:['bridge.js']});
 await chrome.tabs.sendMessage(tab.id,{type:'GINKGO_CAPTURE',payload:captured});
 await chrome.tabs.update(tab.id,{active:true});result.textContent='已送到工作台核对；勾选确认后才会导入。';
}catch(e){result.textContent=e.message}};
