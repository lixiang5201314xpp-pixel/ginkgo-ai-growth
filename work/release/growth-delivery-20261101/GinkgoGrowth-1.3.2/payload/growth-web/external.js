'use strict';
let externalPlatform='douyin',captureBusy=false;
const priorExternalNavigate=navigate;
navigate=async function(name){
 if(name!=='external')return priorExternalNavigate(name);
 pageName=name;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===name));$('#pageCrumb').textContent='外部平台获客';
 try{await externalPage()}catch(e){$('#page').innerHTML=empty('暂时没有加载完成',e.message)}
};

async function externalPage(){
 const d=await api('/api/external'),p=d.platforms.find(x=>x.id===externalPlatform)||d.platforms[0];externalPlatform=p.id;
 $('#page').innerHTML=title('EXTERNAL PLATFORMS','去外部平台找客户。','从抖音、快手、视频号、小红书等外部平台的公开内容与评论找人，银杏奖牌只承接报名。','<button id="externalIntake" class="primary">录入平台原文 →</button>')+
 `<div class="platformTabs">${d.platforms.map(x=>`<button data-external-platform="${x.id}" class="${x.id===p.id?'on':''}">${esc(x.name)}</button>`).join('')}</div><div class="metrics">${[['本平台原文需求',p.counts.recorded],['已核实可回应',p.counts.ready],['已登记联系',p.counts.contacted],['有凭据报名',p.counts.booked]].map(x=>`<div class="metric"><span class="metricLabel">${esc(x[0])}</span><strong>${Number(x[1])}</strong></div>`).join('')}</div>`+
 `<div class="twoCols"><section class="card"><p class="eyebrow">01 · ${esc(p.name)}站内查找</p><h2>打开具体内容，再看评论</h2><p class="muted">${esc(p.mode)}。优先查看原文明示的成都训练、参赛或约球需求。</p>${p.searches.map(x=>`<div class="jobRow"><div><strong>${esc(x.query)}</strong></div>${x.url?`<a class="externalOpen" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">去${esc(p.name)}搜索 ↗</a>`:'<span class="tag">请在手机视频号搜索</span>'}</div>`).join('')}<p class="muted">打开这些站内搜索链接不会消耗 DeepSeek 的网页搜索次数。需要登录时，请在平台正常登录后操作。</p></section><section class="card"><p class="eyebrow">02 · 原文采集与 AI 整理</p><h2>减少复制、逐条录入</h2><ol class="externalSteps"><li>安装一次“银杏外部平台获客助手”。</li><li>打开相关视频／笔记／帖子，展开评论，点助手“读取当前已展示评论”。</li><li>送到工作台，核对原文和时间；勾选后导入并自动排队准备回复。</li></ol><div class="actions"><a href="${esc(d.helper)}" download>下载采集助手 ZIP</a><button id="helperHelp">安装与使用步骤</button></div><div class="note">助手每次最多读取20条已展示的明确求助；不读取私信或 Cookie，不在后台滚动抓取。站点改版未识别时，可选中一条原文读取。视频号目前使用手机检索并复制原文。</div></section></div>`+
 `<section class="card sectionGap"><p class="eyebrow">03 · 在原平台回应，邀请到小程序</p><h2>回复和报名分开留证</h2><p>AI 根据已核对的需求准备回复，说明真实比赛或训练信息，并引导本平台“银杏奖牌”小程序。平台自动发评论／私信尚未接入，发送后再登记实际联系和报名凭据。</p><div class="actions"><button id="externalLeads">查看外部需求与回复 →</button><button id="externalDrafts">准备已有需求的回复</button><button id="externalSupplement">补充网页搜索（${d.public_index_candidates} 条待核实）</button><button id="externalBatch">粘贴采集批次</button></div></section>`;
 document.querySelectorAll('[data-external-platform]').forEach(b=>b.onclick=()=>{externalPlatform=b.dataset.externalPlatform;externalPage()});
 $('#externalIntake').onclick=manualExternalIntake;$('#helperHelp').onclick=helperInstructions;
 $('#externalBatch').onclick=batchExternalIntake;
 $('#externalLeads').onclick=()=>{searchPlatform=p.id;navigate('leads')};$('#externalDrafts').onclick=()=>startJob('respond');$('#externalSupplement').onclick=()=>navigate('discover');
}

function helperInstructions(){modal('<h2>安装外部平台采集助手</h2><ol class="externalSteps"><li>下载助手 ZIP，解压到本机固定文件夹。</li><li>在 Chrome 打开“扩展程序 → 管理扩展程序”，由你开启开发者模式。</li><li>点击“加载已解压的扩展程序”，选择解压后的 browser-helper 文件夹。</li><li>打开具体视频／笔记／帖子，展开评论，再点击助手。</li><li>送到已登录的获客工作台核对。助手不会读取或保存工作台登录令牌。</li></ol><p class="muted">平台页面结构会变化，目前适配器已做模拟页面检查，实际页面仍需验证；识别不到时用“读取我选中的一条原文”。</p>')}

function manualExternalIntake(){
 modal(`<h2>录入外部平台公开原文</h2><form id="externalManualForm"><label>平台<select name="platform">${Object.entries(meta.platforms).map(([k,p])=>`<option value="${k}" ${k===externalPlatform?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><label>原帖／视频／笔记链接<input name="source_url" type="url" required></label><label>评论或求助原文<textarea name="excerpt" rows="4" required minlength="6" maxlength="800"></textarea></label><label>发布内容原文（用于核对成都语境，选填）<textarea name="source_context" rows="2" maxlength="500"></textarea></label><label>原文发布时间<input name="posted_at" type="datetime-local"><span class="muted">不清楚就留空，不能用采集时间代替原文时间。</span></label><button class="primary">初筛并核对</button><p id="externalManualError" class="error"></p></form>`);
 $('#externalManualForm').onsubmit=async e=>{e.preventDefault();try{const row=Object.fromEntries(new FormData(e.target));row.captured_at=new Date().toISOString();await captureReview({items:[row]})}catch(err){$('#externalManualError').textContent=err.message}};
}

function parseExternalBundle(raw){
 if(typeof raw!=='string'||raw.length>120000)throw Error('采集批次过大，请每批最多20条');
 let bundle;try{bundle=JSON.parse(raw)}catch{throw Error('不是有效的采集 JSON，请粘贴完整内容')}
 if(!bundle||!Array.isArray(bundle.items)||bundle.items.length<1||bundle.items.length>20)throw Error('每批需要1至20条公开原文');
 return bundle;
}
function batchExternalIntake(){
 modal('<h2>粘贴采集批次</h2><p class="muted">内置浏览器核对的公开需求也可整批导入。仍会先预览、逐条核对，不会发送消息或创建报名。</p><form id="externalBatchForm"><label>采集 JSON<textarea name="bundle" rows="10" maxlength="120000" required></textarea></label><button class="primary">初筛并核对</button><p id="externalBatchError" class="error"></p></form>');
 $('#externalBatchForm').onsubmit=async e=>{e.preventDefault();try{await captureReview(parseExternalBundle(e.target.elements.bundle.value))}catch(err){$('#externalBatchError').textContent=err.message}};
}

async function captureReview(bundle){
 const d=await post('/api/external/preview',{items:bundle.items});
 modal(`<p class="eyebrow">外部平台原文 · 尚未导入</p><h2>核对这 ${d.items.length} 条需求</h2><p class="muted">只勾选确有求助意图的原文；缺少成都或时间证据会保留待核实，不生成可发送邀请。</p><div class="externalCaptureList">${d.items.map((x,i)=>`<article class="candidate"><label class="check"><input data-external-row="${i}" type="checkbox" ${x.assessment.explicit_demand&&!x.assessment.rejected?'checked':'disabled'}><span>${esc(meta.platforms[x.platform].name)} · ${x.assessment.eligible?'可核实需求':'待补证据'}</span></label><p>${esc(x.excerpt)}</p><a href="${esc(x.source_url)}" target="_blank" rel="noopener noreferrer">回到原文 ↗</a><p class="muted">原时间标签：${esc(x.posted_text||'无')} · 识别时间：${esc(x.posted_at?datetime(x.posted_at):'未知')}</p><p class="muted">${esc(x.city_evidence||'尚无成都证据')}</p>${x.assessment.warnings.map(v=>`<p class="warn">${esc(v)}</p>`).join('')}</article>`).join('')}</div><label class="check"><input id="externalReviewed" type="checkbox"><span>我已在原平台查看并核对所选公开原文、来源和时间，未把搜索词或 IP 属地当作成都需求证据。</span></label><label class="check"><input id="externalPrepare" type="checkbox" checked><span>导入后自动排队，让 AI 准备回复（使用现有每日额度，不发送消息）。</span></label><button id="externalImportConfirm" class="primary">导入所选原文并整理</button><p id="externalImportError" class="error"></p>`);
 $('#externalImportConfirm').onclick=async()=>{try{
  if(!$('#externalReviewed').checked)throw Error('请先核对并勾选原文确认');
  const items=[...document.querySelectorAll('[data-external-row]:checked')].map(b=>d.items[Number(b.dataset.externalRow)]);
  if(!items.length)throw Error('请至少选择一条明确需求');
  const r=await post('/api/external/import',{items,source_reviewed:true,prepare_replies:$('#externalPrepare').checked});
  closeModal();sessionStorage.removeItem('ginkgo_external_capture');toast(`已导入 ${r.added} 条，重复 ${r.duplicates} 条；未发送消息`);await navigate('external');if(r.job)showJob(r.job);
 }catch(e){$('#externalImportError').textContent=e.message}};
}

async function flushExternalCapture(){
 if(captureBusy||!meta||$('#shell').classList.contains('hidden'))return;
 const raw=sessionStorage.getItem('ginkgo_external_capture');if(!raw)return;
 captureBusy=true;sessionStorage.removeItem('ginkgo_external_capture');
 try{const d=JSON.parse(raw);if(!Array.isArray(d.items)||d.items.length>20)throw Error('采集批次无效');await captureReview(d)}catch(e){toast(e.message)}finally{captureBusy=false}
}
window.addEventListener('message',e=>{if(e.source===window&&e.origin===location.origin&&e.data?.type==='GINKGO_EXTERNAL_CAPTURE')flushExternalCapture()});
document.addEventListener('DOMContentLoaded',()=>{setInterval(flushExternalCapture,1000)});
const externalOverviewBase=overview;
overview=async function(){
 await externalOverviewBase();
 const delivery=await api('/api/delivery-summary'),dc=delivery.counts;
 $('#discoverNow').textContent='去外部平台找客户 ↗';$('#discoverNow').onclick=()=>navigate('external');
 $('#page .titleRow h1').textContent='到外部平台，找真正的打球需求。';
 const box=document.createElement('div');box.className='note sectionGap';box.innerHTML='<strong>获客来源：抖音、快手、视频号、小红书、哔哩哔哩、贴吧。</strong><p>先去站内搜索和评论找需求，再导入原文让 AI 整理。小程序客服是后续接待，不能代替外部找客户。“一键运行”只处理已有线索与补充网页索引。</p><button id="externalStartHome" class="primary">进入外部平台获客 →</button>';
 $('#page .titleRow').after(box);$('#externalStartHome').onclick=()=>navigate('external');
 const status=document.createElement('section');status.className='card sectionGap';status.innerHTML=`<h2>外部平台执行进度</h2><p>公开原文采集、AI分析和草稿准备可用。抖音、快手、小红书、视频号的自动评论／私信发送尚未接通；微信小程序AI客服单独配置和统计。</p><div class="metrics">${[['已提交待核实',dc.pending],['核对未显示',dc.not_visible],['平台提示失败',dc.failed]].map(x=>`<div class="metric"><span class="metricLabel">${esc(x[0])}</span><strong>${Number(x[1])}</strong></div>`).join('')}</div><p class="muted">未确认发布不算已联系，不自动重发。草稿、联系、报名分别留证。</p><button id="deliveryReviewHome">查看发送核对 →</button>`;box.after(status);$('#deliveryReviewHome').onclick=()=>navigate('leads');
};
