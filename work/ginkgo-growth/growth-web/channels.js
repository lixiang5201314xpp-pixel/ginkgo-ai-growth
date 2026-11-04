'use strict';
const oldConnections=connections;
const inboxStates={queued:'等待AI',prepared:'已准备回复',sending:'发送中',sent:'已确认发送',human:'人工处理',uncertain:'请人工核对发送结果',expired:'已过回复时间',event:'平台事件'};
connections=async function(){
  await oldConnections();
  document.querySelectorAll('.channelCard .tag').forEach(t=>t.textContent='公开评论接口未接入');
  const legacyNote=$('#page .twoCols .note');
  if(legacyNote)legacyNote.textContent='搜索任务、需求整理、草稿和人工跟进继续可用。小程序客服接入状态以上方各平台卡片为准；全站评论搜索和订单自动归因尚未接入。';
  const d=await api('/api/channels');
  const section=document.createElement('section');section.className='sectionGap';
  section.innerHTML='<h2>小程序客服接入</h2><p class="muted">只处理经营账号实际收到的咨询。各平台状态独立，发送失败不会记为成功。</p><div class="twoCols">'+d.items.map(x=>`<article class="card"><h3>${esc(x.name)} · 银杏奖牌</h3><span class="tag ${x.automatic&&x.verified_at?'green':'gold'}">${x.automatic&&x.verified_at?'AI回复已启用':x.verified_at?'回调已验证，AI尚未启用':x.configured?'待平台验证':'待配置'}</span><p>${esc(x.reason)}</p>${x.callback?`<p class="muted">接收地址</p><input readonly value="${esc(x.callback)}" aria-label="${esc(x.name)}回调地址"><div class="actions"><button class="small" data-channel-copy="${x.platform}">复制接收地址</button><button class="small" data-channel-settings="${x.platform}">接待开关</button></div>`:''}</article>`).join('')+'</div><div class="actions sectionGap"><button id="channelInbox">查看客服接收记录</button></div>';
  $('#page').prepend(section);
  section.querySelectorAll('[data-channel-copy]').forEach(b=>b.onclick=()=>copy(d.items.find(x=>x.platform===b.dataset.channelCopy).callback));
  section.querySelectorAll('[data-channel-settings]').forEach(b=>b.onclick=()=>channelSwitch(d.items.find(x=>x.platform===b.dataset.channelSettings)));
  $('#channelInbox').onclick=showChannelInbox;
  const active=d.items.filter(x=>x.automatic&&x.verified_at).map(x=>x.name);
  $('#liveState').textContent=active.length?active.join('、')+'客服AI已启用':'平台客服AI尚未启用';
};
function channelSwitch(x){
  modal(`<h2>${esc(x.name)}客服接待</h2><p>密钥仅在服务器的 Configure-Channels.cmd 窗口配置；不要发送到聊天。</p><p>${x.verified_at?'已收到通过验签的回调。':'请先配置密钥，在平台提交接收地址并完成验证。'}</p><label class="check"><input id="channelReceive" type="checkbox" ${x.receive?'checked':''} ${!x.configured?'disabled':''}><span>接收官方消息推送</span></label><label class="check"><input id="channelAutomatic" type="checkbox" ${x.automatic?'checked':''} ${!x.verified_at?'disabled':''}><span>使用已配置的 DeepSeek 脱敏处理咨询并自动回复，受每日限额约束</span></label><p class="muted">用户提出转人工、投诉、退费或停止回复后，暂停该会话的AI；不批量私信陌生人。</p><button id="saveChannelSwitch" ${!x.configured?'disabled':''}>保存接待开关</button>`);
  $('#saveChannelSwitch').onclick=async()=>{try{await post('/api/channels/'+x.platform,{receive:$('#channelReceive').checked,automatic:$('#channelAutomatic').checked});closeModal();await connections();toast('接待设置已保存')}catch(e){toast(e.message)}};
}
async function showChannelInbox(){
  try{
    const d=await api('/api/channels/inbox');
    modal('<h2>客服接收记录</h2><p class="muted">最近80条。内容加密保存，7天后清理；这里显示脱敏文字。</p>'+d.items.map(x=>`<article class="card sectionGap"><b>${esc(x.platform)} · ${esc(inboxStates[x.state]||x.state)}</b><p>${esc(x.text)}</p>${x.reply?`<p>${esc(x.reply)}</p>`:''}<small>${esc(x.detail)}</small>${x.state!=='event'?`<div class="actions"><button data-handoff="${x.id}">转人工</button><button data-resume="${x.id}">恢复后续AI接待</button></div>`:''}</article>`).join('')+(d.items.length?'':'<p>尚未收到官方客服消息。</p>'));
    $('#modalBody').querySelectorAll('[data-handoff],[data-resume]').forEach(b=>b.onclick=async()=>{try{const id=b.dataset.handoff||b.dataset.resume;await post('/api/channels/inbox/'+id+'/handoff',{action:b.dataset.handoff?'pause':'resume'});toast(b.dataset.handoff?'已转人工':'后续新消息恢复AI；旧回复不会重发')}catch(e){toast(e.message)}});
  }catch(e){toast(e.message)}
}
