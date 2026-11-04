'use strict';
const workflowOverview=overview;
overview=async function(){
  await workflowOverview();
  const d=await api('/api/workflow');
  $('#liveState').textContent=d.active_reception.length?d.active_reception.join('、')+' AI 接待运行中':'AI 整理与内容准备';
  const section=document.createElement('section');section.className='card workflowQueue sectionGap';
  const tasks=[['主动咨询待跟进',d.new_inquiries,'inquiries'],['客服需人工处理',d.customer_service_human,'connections'],['跟进计划待处理',d.pending_plans,'automate'],['推广文案待发布',d.draft_content,'content'],['网页原文待核实',d.pending_sources,'discover']];
  section.innerHTML='<div class="cardHead"><div><p class="eyebrow">NEXT ACTIONS</p><h2>AI 已整理，接下来做这些</h2></div><button id="refreshWorkflow">刷新</button></div><div class="workflowTasks">'+tasks.map(([label,count,page])=>`<button data-workflow-page="${page}"><span>${esc(label)}</span><strong>${Number(count)}</strong><span>查看 →</span></button>`).join('')+`</div><p class="muted">已核实需求 ${d.verified_needs} · 已登记联系 ${d.contacted_needs} · 有报名凭据 ${d.bookings_with_receipt} · 已登记发布 ${d.published_content} 篇</p><p class="muted">${esc(d.note)}</p><div class="note">${d.active_reception.length?esc(d.active_reception.join('、'))+' AI 接待已启用。':''}抖音、快手、小红书的小程序客服接入暂缓；四平台内容准备继续运行。后台优先整理新咨询，重复运行跳过未变化的需求；搜索额度用完不影响其余处理。</div>`;
  $('#page .metrics').after(section);
  section.querySelectorAll('[data-workflow-page]').forEach(b=>b.onclick=()=>navigate(b.dataset.workflowPage));
  $('#refreshWorkflow').onclick=()=>overview();
};

const workflowDiscover=discover;
discover=async function(){
  await workflowDiscover();
  const d=await api('/api/candidates');
  document.querySelectorAll('[data-candidate]').forEach(b=>{
    const row=d.items.find(x=>x.id===b.dataset.candidate);if(!row)return;
    const article=b.closest('article');
    if(row.status==='ignored'){article.remove();return;}
    const ignore=document.createElement('button');ignore.className='small';ignore.textContent='忽略无关网页';
    ignore.onclick=async()=>{try{await api('/api/candidates/'+row.id,{method:'PATCH',body:JSON.stringify({status:'ignored'})});article.remove();toast('已忽略，后台不会重复初筛这条网页')}catch(e){toast(e.message)}};
    b.after(ignore);
  });
};

const workflowAutomate=automate;
automate=async function(){
  await workflowAutomate();
  const d=await api('/api/workflow/plans');
  const section=$('#page>section:last-child');
  section.innerHTML='<h2>邀请与跟进待办</h2><p class="muted">标记已处理只收起计划，不会标记已联系或已报名。实际联系与报名仍在需求记录中登记。</p>'+ (d.items.length?d.items.map(x=>`<article class="candidate ${x.status==='done'?'workflowDone':''}"><span class="tag">${x.subject_type==='inquiry'?'主动咨询':'已录入需求'} · ${x.status==='done'?'已处理':'待处理'}</span><p class="preserveLines">${esc(x.body)}</p><p class="muted">${esc(x.next_action)} · 建议 ${esc(datetime(x.due_at))}</p><div class="actions"><button class="small" data-workflow-copy="${esc(x.id)}">复制建议</button><button class="small" data-workflow-plan="${esc(x.id)}">${x.status==='done'?'恢复待办':'标记已处理'}</button><button class="small" data-workflow-source="${esc(x.id)}">打开咨询记录 →</button></div></article>`).join(''):'<p class="muted">新咨询进入后，定时任务会整理下一步建议；没有新内容时不重复生成。</p>');
  section.querySelectorAll('[data-workflow-copy]').forEach(b=>b.onclick=()=>copy(d.items.find(x=>x.id===b.dataset.workflowCopy).body));
  section.querySelectorAll('[data-workflow-plan]').forEach(b=>b.onclick=async()=>{try{const x=d.items.find(x=>x.id===b.dataset.workflowPlan);await api('/api/workflow/plans/'+x.id,{method:'PATCH',body:JSON.stringify({status:x.status==='done'?'pending':'done'})});await automate()}catch(e){toast(e.message)}});
  section.querySelectorAll('[data-workflow-source]').forEach(b=>b.onclick=()=>{const x=d.items.find(x=>x.id===b.dataset.workflowSource);if(x.subject_type==='lead'){selectedLead=x.subject_id;navigate('leads')}else navigate('inquiries')});
};

content=async function(){
  await plainContent();
  const d=await api('/api/workflow/content');
  const section=document.createElement('section');section.className='card sectionGap';
  section.innerHTML='<div class="cardHead"><div><p class="eyebrow">FOUR CHANNELS · ONE MINIAPP NAME</p><h2>今日内容，准备好带去发布</h2></div><button id="prepareWorkflowContent" class="primary">准备今日四平台内容</button></div><p class="muted">主题每日轮换，优先使用实时比赛和已确认课程。各自关联本平台「银杏奖牌」小程序。登记作品链接后才计入已发布记录。</p><div class="actions"><button id="exportContentMarkdown">下载发布包</button><button id="exportContentCsv">导出 CSV</button></div>'+ (d.items.length?d.items.map(x=>`<article class="candidate"><span class="tag ${x.status==='published'?'green':'gold'}">${esc(meta.platforms[x.platform].name)} · ${x.status==='published'?'已登记发布':'待发布'} · ${esc(datetime(x.created_at))}</span><h3>${esc(x.title)}</h3><p class="preserveLines">${esc(x.body)}</p><p>拍摄建议：${esc(x.shot_list)}</p><div class="actions"><button class="small" data-workflow-content="${esc(x.id)}">复制文案</button><a target="_blank" rel="noopener noreferrer" href="${esc(meta.platforms[x.platform].console)}">打开本平台发布台 ↗</a><button class="small" data-workflow-publish="${esc(x.id)}">${x.status==='published'?'修改作品链接':'登记已发布作品'}</button>${x.published_url?`<a target="_blank" rel="noopener noreferrer" href="${esc(x.published_url)}">查看作品 ↗</a>`:''}</div></article>`).join(''):'<p class="muted">点击上方按钮，AI 会在已有额度内准备四个平台文案。</p>');
  $('#page .titleRow').after(section);
  $('#prepareWorkflowContent').onclick=()=>startJob('followup');
  section.querySelectorAll('[data-workflow-content]').forEach(b=>b.onclick=()=>copy(d.items.find(x=>x.id===b.dataset.workflowContent).body));
  section.querySelectorAll('[data-workflow-publish]').forEach(b=>b.onclick=()=>{
    const x=d.items.find(x=>x.id===b.dataset.workflowPublish);
    modal(`<h2>登记${esc(meta.platforms[x.platform].name)}作品链接</h2><p>先在平台发布，再粘贴这篇作品的实际链接。此操作不会代为发布，也不会计作报名。</p><form id="publicationForm"><label>作品链接<input id="publicationUrl" type="url" required value="${esc(x.published_url||'')}" placeholder="https://…"></label><button class="primary">保存发布记录</button><p id="publicationError" class="error"></p></form>`);
    $('#publicationForm').onsubmit=async e=>{e.preventDefault();try{await post('/api/workflow/content/'+x.id+'/published',{url:$('#publicationUrl').value});closeModal();await content();toast('作品链接已登记')}catch(err){$('#publicationError').textContent=err.message}};
  });
  async function download(format){try{const res=await fetch(ROOT+'/api/workflow/content/export?format='+format,{headers:{Authorization:'Bearer '+token}});if(!res.ok)throw Error('导出失败，请重新登录后重试');const url=URL.createObjectURL(await res.blob());const a=document.createElement('a');a.href=url;a.download='银杏内容发布包.'+(format==='csv'?'csv':'md');a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message)}}
  $('#exportContentMarkdown').onclick=()=>download('markdown');$('#exportContentCsv').onclick=()=>download('csv');
};
