'use strict';
let jobPoll=null;
const jobLabels={discover:'寻找当前需求',respond:'回应具体问题',followup:'邀请报名，跟进结果',all:'一键运行三步'};
const stateLabels={queued:'等待执行',running:'正在执行',completed:'执行完成',needs_setup:'需要接入或核实',failed:'执行未完成',cancelled:'已取消',interrupted:'上次执行中断'};

async function startJob(kind){
  try{const d=await post('/api/automation/jobs',{kind});showJob(d.job)}catch(e){toast(e.message)}
}

function resultHtml(result){
  const out=[];
  if(result.discover){const r=result.discover;out.push(`<section class="jobResult"><h3>01 寻找需求</h3><p>搜索 ${Number(r.queries_completed||0)} 次 · 新增 ${Number(r.new_web_candidates||0)} 个待核实网页 · AI 初筛 ${Number(r.ai_screened||0)} 条</p><p>同步 ${Number(r.catalog_events||0)} 场比赛，导入 ${Number(r.owned_inquiries_imported||0)} 条自己账号的咨询。</p><p class="muted">${esc(r.blocked_reason||r.note||'')}</p>${r.analysis_note?`<p class="warn">${esc(r.analysis_note)}</p>`:''}</section>`)}
  if(result.respond){const r=result.respond;out.push(`<section class="jobResult"><h3>02 回应准备</h3><p>分析 ${Number(r.analyzed||0)} 条需求 · 准备 ${Number(r.drafts_prepared||0)} 条回复 · ${Number(r.needs_source_review||0)} 条待核实</p><p class="muted">${esc(r.note||'')}</p>${(r.errors||[]).map(e=>`<p class="warn">${esc(e)}</p>`).join('')}</section>`)}
  if(result.followup){const r=result.followup;out.push(`<section class="jobResult"><h3>03 报名与跟进准备</h3><p>整理 ${Number(r.plans_prepared||0)} 份邀请计划 · ${Number(r.waiting_for_reply||0)} 条等待对方回复</p><p class="muted">${esc(r.blocked_reason||'')}</p>${(r.errors||[]).map(e=>`<p class="warn">${esc(e)}</p>`).join('')}</section>`)}
  return out.join('')||'<p class="muted">任务执行后会在此显示结果。</p>';
}

function showJob(job){
  if(jobPoll)clearTimeout(jobPoll);
  modal(`<p class="eyebrow">AI WORKFLOW · 执行记录</p><h2>${esc(jobLabels[job.kind]||job.kind)}</h2><span class="tag ${job.status==='completed'?'green':'gold'}">${esc(stateLabels[job.status]||job.status)}</span><p class="sectionGap">${esc(job.message)}</p><progress class="jobProgress" max="100" value="${Number(job.progress)||0}"></progress><div>${resultHtml(job.result||{})}</div><div class="actions">${['queued','running'].includes(job.status)?'<button id="cancelJob">停止后续执行</button>':''}<button id="viewAutomation">查看任务中心</button>${['needs_setup','failed'].includes(job.status)?'<button id="openAISetup" class="primary">检查 AI 配置</button>':''}</div><p class="muted">已发生的 API 调用不会因关闭窗口或取消任务而撤销；未接通的平台发送不会标记成功。</p>`);
  $('#viewAutomation').onclick=()=>{closeModal();navigate('automate')};
  if($('#openAISetup'))$('#openAISetup').onclick=()=>{closeModal();navigate('aiSettings')};
  if($('#cancelJob'))$('#cancelJob').onclick=async()=>{await post('/api/automation/jobs/'+job.id+'/cancel');toast('已请求停止后续执行')};
  if(['queued','running'].includes(job.status))jobPoll=setTimeout(async()=>{if($('#modal').classList.contains('hidden'))return;try{const d=await api('/api/automation/jobs/'+job.id);showJob(d.job)}catch(e){toast(e.message)}},1800);
}

const plainOverview=overview;
overview=async function(){
  await plainOverview();
  const d=await api('/api/automation');
  const three=[['discover','自动搜索公开网页、导入咨询并做 AI 初筛'],['respond','AI 分析已有需求，批量准备有针对性的回复'],['followup','生成报名邀请与跟进计划，等待平台发送接入']];
  document.querySelectorAll('#page .step').forEach((el,i)=>{if(!three[i])return;const btn=document.createElement('button');btn.className='step stepAction';btn.innerHTML=el.innerHTML;btn.querySelector('p').textContent=three[i][1];btn.setAttribute('aria-label','执行：'+jobLabels[three[i][0]]);btn.onclick=()=>startJob(three[i][0]);el.replaceWith(btn)});
  $('#discoverNow').textContent='一键运行三步 ↗';$('#discoverNow').onclick=()=>startJob('all');
  const bar=document.createElement('div');bar.className='automationBar';
  bar.innerHTML=`<div><strong>${d.ai.enabled?'AI 已启用':'AI 尚未配置'}</strong><p>${d.ai.automatic?'定时运行：每 '+d.ai.interval_minutes+' 分钟执行一次':'可以点击执行任务，或在 AI 设置中开启定时运行'}</p></div><button id="overviewAI">${d.ai.key_configured?'AI 设置':'配置 DeepSeek 密钥'}</button><button id="overviewTasks">执行记录 →</button>`;
  $('#page .metrics').before(bar);$('#overviewAI').onclick=()=>navigate('aiSettings');$('#overviewTasks').onclick=()=>navigate('automate');
  $('#liveState').textContent=d.ai.enabled?'AI 处理已启用 · 平台发送未接通':'等待配置 AI';
};

const plainDiscover=discover;
discover=async function(){
  await plainDiscover();
  const bar=document.createElement('div');bar.className='automationBar';
  bar.innerHTML='<div><strong>AI 公开需求搜索</strong><p>搜索四个平台的公开网页索引，去重并做 AI 初筛；站内评论不保证可被搜索。</p></div><button class="primary" id="aiDiscover">开始自动搜索 ↗</button>';
  $('#page .titleRow').after(bar);$('#aiDiscover').onclick=()=>startJob('discover');
  const d=await api('/api/candidates');
  const box=document.createElement('section');box.className='card sectionGap';
  box.innerHTML=`<div class="cardHead"><h2>AI 搜索到的待核实网页</h2><span class="tag">${d.items.length} 个网页</span></div><p class="muted">搜索摘要可能不完整或已过时。核对原文后再作为客户需求录入，不能把搜索结果数当作客户数。</p>${d.items.length?d.items.map(x=>`<article class="candidate"><span class="tag">${esc(meta.platforms[x.platform].name)} · 待核实</span><h3>${esc(x.title)}</h3><p>${esc(x.excerpt)}</p>${x.ai_result?`<div class="note">AI 初筛：${esc(x.ai_result.summary)}<br>建议：${esc(x.ai_result.next_action)}</div>`:''}<div class="actions"><a target="_blank" rel="noopener noreferrer" href="${esc(x.url)}">查看原文 ↗</a><button class="small" data-candidate="${esc(x.id)}">核实后录入</button></div></article>`).join(''):'<p class="muted">尚未执行搜索，或没有找到公开索引结果。点击“开始自动搜索”运行一次。</p>'}`;
  $('#page').append(box);box.querySelectorAll('[data-candidate]').forEach(b=>b.onclick=()=>{const row=d.items.find(x=>x.id===b.dataset.candidate);leadForm({platform:row.platform,source_url:row.url})});
};

async function automate(){
  const [d,p]=await Promise.all([api('/api/automation'),api('/api/followup-plans')]);
  $('#page').innerHTML=title('AI WORKFLOW','把三步，交给执行任务。','AI 负责搜索、分析与准备；执行记录会区分完成、待配置、失败和待核实。','<button class="primary" id="runAll">一键运行三步 ↗</button>')+
    `<div class="metrics">${[['公开网页待核实',d.sources.web_candidates],['已有需求',d.sources.existing_leads],['主动咨询',d.sources.opt_in_inquiries],['跟进计划',p.items.length]].map(x=>`<div class="metric"><span class="metricLabel">${esc(x[0])}</span><strong>${x[1]}</strong></div>`).join('')}</div><div class="grid3">${[['discover','01','寻找当前需求','同步比赛、搜索公开网页、导入自己账号的咨询，并做 AI 初筛。'],['respond','02','回应具体问题','批量分析已有需求，准备带有俱乐部身份说明的个性化回复。'],['followup','03','邀请报名，跟进结果','给已核实需求和主动咨询准备邀请及后续计划，不虚报发送和报名。']].map(x=>`<button class="card taskCard" data-task="${x[0]}"><span class="stepNumber">${x[1]}</span><h2>${esc(x[2])} ↗</h2><p>${esc(x[3])}</p></button>`).join('')}</div><div class="note">${d.ai.automatic?'定时自动运行已开启，每 '+d.ai.interval_minutes+' 分钟执行一次。':'定时自动运行当前关闭，可在 AI 设置中开启。'} 每日 AI 上限 ${d.ai.daily_ai_limit} 次、搜索上限 ${d.ai.daily_search_limit} 次。平台评论与私信发送仍未接通。</div><section class="card sectionGap"><div class="cardHead"><h2>最近执行</h2><button id="refreshTasks">刷新</button></div>${d.jobs.length?d.jobs.map(j=>`<div class="jobRow"><div><strong>${esc(jobLabels[j.kind])}</strong><p>${esc(j.message)} · ${esc(datetime(j.created_at))}</p></div><span class="tag">${esc(stateLabels[j.status]||j.status)}</span><button class="small" data-job="${j.id}">查看结果 →</button></div>`).join(''):empty('任务准备好了。','点击上面任一步，或直接一键运行三步。')}</section><section class="card sectionGap"><h2>已准备的邀请与跟进</h2>${p.items.length?p.items.map(x=>`<article class="candidate"><span class="tag">${x.subject_type==='inquiry'?'主动咨询':'已录入需求'} · 尚未发送</span><p>${esc(x.body)}</p><p class="muted">${esc(x.next_action)} · 建议时间 ${esc(datetime(x.due_at))}</p><button class="small" data-plan="${x.id}">复制邀请内容</button></article>`).join(''):'<p class="muted">执行第三步后，会在这里显示已经生成的邀请与跟进计划。</p>'}</section>`;
  $('#runAll').onclick=()=>startJob('all');$('#refreshTasks').onclick=()=>automate();
  document.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>startJob(b.dataset.task));
  document.querySelectorAll('[data-job]').forEach(b=>b.onclick=()=>showJob(d.jobs.find(j=>j.id===b.dataset.job)));
  document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>copy(p.items.find(x=>x.id===b.dataset.plan).body));
}

async function aiSettings(){
  const d=await api('/api/ai/settings');
  $('#page').innerHTML=title('AI CONNECTION','让 AI，开始为球馆工作。','密钥在服务器加密保存，不会返回浏览器或写入操作记录。')+
    `<div class="twoCols"><section class="card"><h2>DeepSeek 配置</h2><form id="aiForm"><div class="formGrid"><label>AI 服务商<select name="provider"><option value="deepseek" ${d.provider==='deepseek'?'selected':''}>DeepSeek（当前成都部署）</option><option value="openai" ${d.provider==='openai'?'selected':''} ${d.openai_environment_supported?'':'disabled'}>OpenAI（需官方支持的使用环境）</option></select></label><label>模型<select name="model">${d.providers[d.provider].models.map(m=>`<option ${m===d.model?'selected':''}>${esc(m)}</option>`).join('')}</select></label><label class="span2">API Key<input name="api_key" type="password" autocomplete="off" spellcheck="false" placeholder="${d.key_configured?'已保存 '+esc(d.key_fingerprint)+'，留空保持现有密钥':'粘贴完整 API Key'}"><span class="muted">仅在这个安全配置页输入，切勿发到聊天或截图。</span></label><label>每日 AI 调用上限<input name="daily_ai_limit" type="number" min="1" max="200" required value="${d.daily_ai_limit}"></label><label>每日公开搜索上限<input name="daily_search_limit" type="number" min="1" max="50" required value="${d.daily_search_limit}"></label><label class="span2">定时运行间隔（分钟）<input name="interval_minutes" type="number" min="30" max="1440" required value="${d.interval_minutes}"></label></div>${[['enabled','启用 AI 需求分析和回复准备'],['search_enabled','启用 DeepSeek 官方公开网页搜索'],['automatic','配置完成后定时自动运行三步'],['paid_usage_authorized','允许按上述次数上限调用付费 API；实际费用以服务商账户为准'],['data_processing_authorized','同意将脱敏需求及公开球馆信息发送给所选 AI 服务商处理']].map(([k,label])=>`<label class="check"><input type="checkbox" name="${k}" ${d[k]?'checked':''}><span>${esc(label)}</span></label>`).join('')}<div class="actions"><a href="${esc(d.providers[d.provider].keys_url)}" target="_blank" rel="noopener noreferrer">获取 API 密钥 ↗</a><button class="primary">加密保存配置</button></div><p id="aiSaveResult" role="status"></p></form></section><section class="card"><h2>连接与用量</h2><div class="connectionStatus"><span class="tag ${d.key_configured?'green':'gold'}">${d.key_configured?'密钥已配置 '+esc(d.key_fingerprint):'尚未配置密钥'}</span><p>${d.enabled?'AI 已启用':'AI 当前关闭'} · ${d.automatic?'定时运行开启':'定时运行关闭'}</p></div><button id="testAI">测试密钥和模型连接</button><div id="testAIResult" class="note">${esc(d.connection_test?.message||'保存配置后，可验证密钥和所选模型是否可访问。连接测试不生成文本。')}</div><h3>今日调用</h3>${d.usage.length?d.usage.map(x=>`<div class="jobRow"><span>${x.kind==='search'?'公开网页搜索':'AI 文本分析'}</span><strong>${x.n} 次</strong></div>`).join(''):'<p class="muted">今天尚无生成或搜索调用。</p>'}<div class="note">每日次数限制由本软件执行，失败尝试也计入上限。它不是服务商账户的金额硬上限。<br>AI 不会代填客户身份、不虚构价格、名额或报名成功。<br>平台评论／私信发送需要另外接通平台接口。</div><button id="goAITasks">前往 AI 执行任务 →</button></section></div>`;
  const form=$('#aiForm');form.provider.onchange=()=>{form.model.innerHTML=d.providers[form.provider.value].models.map(m=>`<option>${esc(m)}</option>`).join('')};
  form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button[type=submit]')||form.querySelector('button');button.disabled=true;const result=$('#aiSaveResult');result.textContent='正在加密保存…';
    try{const body={provider:form.provider.value,model:form.model.value,api_key:form.api_key.value.trim(),daily_ai_limit:Number(form.daily_ai_limit.value),daily_search_limit:Number(form.daily_search_limit.value),interval_minutes:Number(form.interval_minutes.value)};
      for(const k of ['enabled','search_enabled','automatic','paid_usage_authorized','data_processing_authorized'])body[k]=form[k].checked;
      const saved=await post('/api/ai/settings',body);form.api_key.value='';result.className='muted positive';result.textContent='已加密保存 '+saved.key_fingerprint+'。可以测试连接并运行任务。';
    }catch(e){result.className='error';result.textContent=e.message}finally{button.disabled=false;form.api_key.value=''}};
  $('#testAI').onclick=async()=>{const b=$('#testAI');b.disabled=true;$('#testAIResult').textContent='正在验证密钥与模型访问…';try{const r=await api('/api/ai/test',{method:'POST',body:'{}',signal:AbortSignal.timeout(35000)});$('#testAIResult').textContent=r.message}catch(e){$('#testAIResult').textContent=e.message}finally{b.disabled=false}};
  $('#goAITasks').onclick=()=>navigate('automate');
}

const plainContent=content;
content=async function(){
  await plainContent();
  const d=await api('/api/ai/content');
  const box=document.createElement('section');box.className='card sectionGap';
  box.innerHTML=`<div class="cardHead"><h2>四个平台 · AI 小程序引流内容</h2><button id="prepareAIContent">自动准备今日内容</button></div><p class="muted">各平台内容引导各自的“银杏奖牌”小程序。文字已准备，不等同平台已发布；发布时请关联账号已有的小程序入口。</p>${d.items.length?d.items.map(x=>`<article class="candidate"><span class="tag">${esc(meta.platforms[x.platform].name)} · 尚未发布</span><h3>${esc(x.title)}</h3><p class="preserveLines">${esc(x.body)}</p><p class="muted">拍摄建议：${esc(x.shot_list)}</p><div class="actions"><button class="small" data-ai-copy="${esc(x.id)}">复制本平台文案</button><a href="${esc(meta.platforms[x.platform].console)}" target="_blank" rel="noopener noreferrer">打开本平台发布台 ↗</a></div></article>`).join(''):'<p class="muted">执行自动任务第三步后，会生成今日四个平台的专属文案。</p>'}`;
  $('#page .titleRow').after(box);$('#prepareAIContent').onclick=()=>startJob('followup');
  box.querySelectorAll('[data-ai-copy]').forEach(b=>b.onclick=()=>copy(d.items.find(x=>x.id===b.dataset.aiCopy).body));
};
