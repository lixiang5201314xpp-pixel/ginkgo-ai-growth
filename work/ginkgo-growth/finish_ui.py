from pathlib import Path
root=Path(__file__).resolve().parent/'growth-web'
p=root/'app.js';s=p.read_text('utf-8')
s=s.replace('overview,discover,leads,campaigns,inquiries,connections','overview,discover,leads,content,campaigns,inquiries,connections')
s=s.replace('class="card row" style="margin-top:22px"','class="card row sectionGap"')
s=s.replace('class="card" style="margin-top:24px"','class="card sectionGap"')
s=s.replace('class="twoCols" style="margin-top:24px"','class="twoCols sectionGap"')
s=s.replace("meta=await api('/api/meta');", "meta=await api('/api/meta');meta.platforms=Object.fromEntries(['douyin','kuaishou','channels','xiaohongshu','bilibili','tieba'].map(p=>[p,meta.platforms[p]]));")
fn='''async function content(){const d=await api('/api/content-plan');const entries=d.items.filter(x=>x.platform===searchPlatform);if(!entries.length){searchPlatform='douyin';return content()}$('#page').innerHTML=title('CONTENT THAT ANSWERS REAL QUESTIONS','让想打球的人，也能找到你。','七天选题与真实内容草稿；核对、拍摄后再到自己的平台账号发布。')+`<div class="pillTabs">${['douyin','kuaishou','channels','xiaohongshu'].map(p=>`<button data-content-p="${p}" class="${p===searchPlatform?'active':''}">${esc(meta.platforms[p].name)}</button>`).join('')}</div><div class="grid3">${entries.map((x,i)=>`<article class="card"><span class="tag">第 ${x.day} 天 · ${esc(x.kind)}</span><h3 class="sectionGap">${esc(x.title)}</h3><p class="muted">拍摄建议：${esc(x.shot_list)}</p><p class="muted">${x.tags.map(esc).join(' · ')}</p><button class="small" data-content-item="${i}">查看完整草稿 ↗</button></article>`).join('')}</div><div class="note">使用俱乐部真实画面与信息，并取得出镜许可。草稿没有发布，不冒充学员评价，不承诺效果或赠送不存在的优惠。</div>`;document.querySelectorAll('[data-content-p]').forEach(b=>b.onclick=()=>{searchPlatform=b.dataset.contentP;content()});document.querySelectorAll('[data-content-item]').forEach(b=>b.onclick=()=>{const x=entries[Number(b.dataset.contentItem)];modal(`<p class="eyebrow">待核对 · 尚未发布</p><h2>${esc(x.title)}</h2><p class="muted">${esc(x.shot_list)}</p><textarea class="replyBox" id="contentDraft" rows="10">${esc(x.body+'\\n#'+x.tags.join(' #'))}</textarea><div class="actions"><button id="copyContent">复制内容草稿</button><a target="_blank" rel="noopener noreferrer" href="${esc(meta.platforms[x.platform].console)}">打开自己的平台工作台 ↗</a></div>`);$('#copyContent').onclick=()=>copy($('#contentDraft').value)})}
'''
if 'async function content()' not in s:s=s.replace('async function connections(){',fn+'async function connections(){')
p.write_text(s,'utf-8')
css=root/'app.css';t=css.read_text('utf-8')
if '.sectionGap{' not in t:t+='\n.sectionGap{margin-top:24px}\n'
css.write_text(t,'utf-8')
for name,path in [('index.html','assets/favicon.svg'),('club.html','../assets/favicon.svg')]:
 p=root/name;t=p.read_text('utf-8')
 if 'rel="icon"' not in t:t=t.replace('</title>',f'</title><link rel="icon" href="{path}" type="image/svg+xml">')
 p.write_text(t,'utf-8')
print('UI content page, fixed channel order and CSP-compatible spacing prepared.')
