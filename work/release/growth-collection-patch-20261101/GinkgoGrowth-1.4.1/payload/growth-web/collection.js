'use strict';
const collectionExternalBase=externalPage;
externalPage=async function(){
 await collectionExternalBase();
 const s=await api('/api/collection');
 const card=document.createElement('section');card.className='card sectionGap';
 card.innerHTML=`<p class="eyebrow">CONTINUOUS COLLECTION</p><h2>启动一次，连续整理公开需求</h2><p>当前：<strong>${s.enabled?'已开启自动入库与AI准备':'已停止自动入库'}</strong>。浏览器助手每轮最多读取5个已展示的原帖链接，明确的新需求自动去重入库并准备回复；明确超过30天的旧原文自动排除，日期或城市证据不足留待核实。</p><div class="actions"><button id="collectionToggle" class="primary">${s.enabled?'停止自动入库':'开启自动入库与AI准备'}</button><button id="collectionRefresh">刷新采集记录</button></div><p class="muted">先在本机已登录的平台搜索页点击银杏助手“启动本平台连续采集”，保留一个已登录工作台标签。浏览器关闭、登录失效、验证码或页面无法识别时暂停。微信视频号暂无浏览器自动采集适配。</p><p class="muted">公开内容采集和AI草稿可自动执行；外部平台评论／私信自动发送尚未连接，草稿不计为已联系。</p><div>${s.receipts.map(r=>`<div class="jobRow"><span>${esc(datetime(r.created_at))}</span><span>有效新增 ${Number(r.result.added_valid)} · 待核实 ${Number(r.result.pending_review)} · 重复 ${Number(r.result.duplicates)} · 排除 ${Number(r.result.skipped||0)} · 发送 ${Number(r.result.sent)}</span></div>`).join('')||'<p class="muted">尚无浏览器自动采集批次。</p>'}</div>`;
 $('#page .titleRow').after(card);
 $('#collectionToggle').onclick=async()=>{try{await api('/api/collection',{method:'PUT',body:JSON.stringify({enabled:!s.enabled})});await externalPage()}catch(e){toast(e.message)}};
 $('#collectionRefresh').onclick=externalPage;
};
const collectionBatches=new Map();
window.addEventListener('message',async e=>{
 if(e.source!==window||e.origin!==location.origin||e.data?.type!=='GINKGO_AUTO_CAPTURE')return;
 const d=e.data.payload,id=d?.batch_id;
 if(!id||!Array.isArray(d?.items)||!d.items.length||d.items.length>20)return;
 let pending=collectionBatches.get(id);
 if(!pending){pending=post('/api/collection/batches',d);collectionBatches.set(id,pending)}
 try{
  const result=await pending;
  window.postMessage({type:'GINKGO_AUTO_CAPTURE_RESULT',batch_id:id,ok:true,result},location.origin);
  // A capture receipt is not a customer message. Keep the page/active modal in place.
  toast(`自动采集：有效新增 ${result.added_valid} 条，待核实 ${result.pending_review} 条；未发送消息`);
 }catch(err){collectionBatches.delete(id);window.postMessage({type:'GINKGO_AUTO_CAPTURE_RESULT',batch_id:id,ok:false,error:err.message},location.origin)}
 if(collectionBatches.size>50)collectionBatches.delete(collectionBatches.keys().next().value);
});
