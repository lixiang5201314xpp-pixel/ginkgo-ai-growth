/* Invoked with activeTab only. No cookies, network, private APIs, scrolling or sending. */
(()=>{'use strict';
 const platforms=[['douyin',['douyin.com','iesdouyin.com']],['kuaishou',['kuaishou.com','gifshow.com']],['xiaohongshu',['xiaohongshu.com','xhslink.com']],['channels',['weixin.qq.com','weixinbridge.com']],['bilibili',['bilibili.com','b23.tv']],['tieba',['tieba.baidu.com']]];
 const adapters={
  douyin:{rows:'[data-e2e="comment-item"]',body:'[data-e2e="comment-content"],.comment-content,.sU2yAQQU,.FduGc_lz',time:'[data-e2e="comment-time"],time,.GOkWHE6S span,.VAQA49VP span',context:'[data-e2e="video-desc"]',detail:/\/video\/|\/note\/|[?&]modal_id=/},
  kuaishou:{rows:'.comment-item,[data-testid="comment-item"]',body:'.comment-content,.comment-text',time:'.comment-time,time',context:'.video-info .caption,.video-info .description',detail:/\/short-video\/|\/f\//},
  xiaohongshu:{rows:'.comment-item',body:'.content .note-text,.content',time:'.date,time',context:'#detail-desc',detail:/\/explore\/|\/discovery\/item\//},
  bilibili:{rows:'.reply-item,.root-reply-container',body:'.reply-content,.reply-content-container',time:'.reply-time,time',context:'.video-desc-container',detail:/\/video\//},
  tieba:{rows:'.l_post',body:'.d_post_content',time:'.tail-info,time',context:'#j_core_title_wrap .core_title_txt',detail:/\/p\//}
 };
 function platformForUrl(value){try{const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password)return null;return platforms.find(([,hosts])=>hosts.some(h=>u.hostname===h||u.hostname.endsWith('.'+h)))?.[0]||null}catch{return null}}
 function redact(value){return String(value||'').replace(/sk-[a-zA-Z0-9_-]+/gi,'[密钥隐藏]').replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g,'[电话隐藏]').replace(/(微信|微号|vx|wechat|qq)\s*[:：号]?\s*[a-zA-Z0-9_-]{5,}/gi,'$1[联系方式隐藏]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[邮箱隐藏]')}
 function visible(node,win){const box=node.getBoundingClientRect();const s=win.getComputedStyle(node);return box.width>0&&box.height>0&&box.bottom>0&&box.right>0&&box.top<(win.innerHeight||Infinity)&&box.left<(win.innerWidth||Infinity)&&s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)!==0}
 function text(node){return String(node?.innerText||node?.textContent||'').replace(/\s+/g,' ').trim()}
 function looksRelevant(value){return /乒乓|学球|练球|球友|球搭子/.test(value)&&/哪[里儿]|找|想|求|推荐|怎么报|报名|有没有|能不能|请问|咨询/.test(value)&&!/不想|不要联系|别联系|拒绝|我们是.{0,24}(俱乐部|球馆)|培训班招生|欢迎.{0,12}(报名|咨询)/.test(value)}
 function canonicalUrl(value,platform){const u=new URL(value);if(platform==='douyin'){const id=u.searchParams.get('modal_id');if(id&&/^\d{10,25}$/.test(id))return 'https://www.douyin.com/video/'+id;const m=u.pathname.match(/^\/(video|note)\/(\d{10,25})\/?$/);if(m)return 'https://www.douyin.com/'+m[1]+'/'+m[2]}return value}
 // Observed public filter UI (2026-11-02). Sorting is not encoded in the URL.
 // Restore via these ordinary controls after navigation; never invent parameters
 // or silently collect the default ranking when the layout cannot be verified.
 function searchSortState(doc,win){
  const latest=[...doc.querySelectorAll('span.eXMmo3JR')].filter(n=>visible(n,win)&&text(n)==='最新发布');
  if(latest.length!==1)return 'unknown';
  return latest[0].classList.contains('sDNqBVWH')?'latest':'default';
 }
 function ensureRecentSearch(options={}){
  const doc=options.document||document,win=doc.defaultView,url=options.source_url||win.location.href,u=new URL(url);
  if(platformForUrl(url)!=='douyin'||!u.pathname.startsWith('/search/')||u.searchParams.has('modal_id'))throw Error('不是可核对的抖音搜索结果页');
  if(searchSortState(doc,win)==='latest')return {ready:true};
  const latest=[...doc.querySelectorAll('span.eXMmo3JR')].filter(n=>visible(n,win)&&text(n)==='最新发布');
  if(latest.length===1){latest[0].click();return {pending:true,action:'select_latest'}}
  if(latest.length>1)throw Error('最新发布筛选项不唯一，已停止');
  const filters=[...doc.querySelectorAll('span.P1BREWal')].filter(n=>visible(n,win)&&text(n)==='筛选');
  if(filters.length!==1)throw Error('未能核对最新发布筛选入口，请手动选择后重新启动');
  filters[0].click();return {pending:true,action:'open_filters'};
 }
 function ownNodes(row,selector,rows){return [...row.querySelectorAll(selector)].filter(n=>n.closest(rows)===row)}
 function pageScope(doc,win,platform,source){
  if(platform==='xiaohongshu'){
   const posts=[...doc.querySelectorAll('.note-content')].filter(n=>visible(n,win));
   if(posts.length!==1)throw Error('未能唯一确定当前笔记正文，请打开原帖详情后重试');
   return {root:posts[0].parentElement,post:posts[0].querySelector('h1'),body:posts[0].querySelector('#detail-desc'),date:posts[0].querySelector('.date')};
  }
  if(platform!=='douyin')return {root:doc,post:null};
  const active=[...doc.querySelectorAll('[data-e2e="feed-active-video"]')].filter(n=>visible(n,win));
  if(active.length===1)return {root:active[0],post:[...active[0].querySelectorAll(adapters.douyin.context)].find(n=>visible(n,win))||null};
  // Canonical detail pages use a single H1; search feeds preload adjacent works.
  if(/^\/(video|note)\/\d+\/?$/.test(new URL(source).pathname)){
   const headings=[...doc.querySelectorAll('h1')].filter(n=>visible(n,win));
   if(headings.length===1)return {root:doc,post:headings[0]};
  }
  throw Error('未能确定当前作品，请打开作品详情页后再读取，避免混入相邻视频。');
 }
 function postDate(root,win,rows){
  const values=[...root.querySelectorAll('time,span')].filter(n=>!n.closest(rows)&&visible(n,win))
   .map(n=>n.getAttribute('datetime')||text(n)).filter(x=>/^发布时间[：:]\s*\d{4}[-/.]\d/.test(x));
  const unique=[...new Set(values)];return unique.length===1?unique[0].replace(/^发布时间[：:]\s*/,''):'';
 }
 function collect(options={}){
  const doc=options.document||document,win=doc.defaultView,url=options.source_url||win.location.href,platform=platformForUrl(url);
  if(!platform)throw Error('请在支持的外部平台原文页面使用。');
  if(/\/(?:login|passport|settings?|privacy|messages?|im|chat|inbox)(?:\/|$)/i.test(new URL(url).pathname))throw Error('不读取登录、设置或私信页面。');
  const adapter=adapters[platform];
  if(!adapter)throw Error('视频号请在手机微信搜索，复制公开评论与分享链接到工作台核对。');
  if(!adapter.detail.test(url))throw Error('请先打开具体视频、笔记或帖子，并展开评论。');
  const scope=pageScope(doc,win,platform,url),canonical=canonicalUrl(url,platform);
  const now=options.captured_at||new Date().toISOString(),context=redact(text(scope.post||scope.root.querySelector(adapter.context))).slice(0,500),items=[],seen=new Set();
  function add(excerpt,postedText,kind='comment'){excerpt=redact(excerpt).slice(0,800);if(excerpt.length<6||seen.has(excerpt)||!looksRelevant(excerpt))return;seen.add(excerpt);items.push({platform,source_url:canonical,source_kind:kind,excerpt,posted_text:postedText||'',source_context:context,captured_at:now})}
  if(options.mode==='selection'){add(String(win.getSelection()||''),'','selection')}
  else if(options.mode==='post'||options.mode==='all'){
   if(!['douyin','xiaohongshu'].includes(platform)&&options.mode==='post')throw Error('此平台暂只读取已展示评论');
   if(platform==='xiaohongshu')add((text(scope.post)+' '+text(scope.body)).trim(),text(scope.date),'post');
   else if(platform==='douyin')add(text(scope.post),postDate(scope.root,win,adapter.rows),'post');
  }
  if(!['selection','post'].includes(options.mode))for(const row of scope.root.querySelectorAll(adapter.rows)){
   if(items.length>=20)break;if(!visible(row,win))continue;
   const body=ownNodes(row,adapter.body,adapter.rows).find(n=>visible(n,win));if(!body)continue;
   const dates=ownNodes(row,adapter.time,adapter.rows).map(n=>n.getAttribute('datetime')||text(n));
   const date=dates.find(x=>/^(刚刚|刚才|\d+\s*(分钟|小时|天)前|今天|昨天|前天|\d{4}[-/.]\d|\d\d?[-/]\d)/.test(x))||'';
   add(text(body),date.slice(0,60));
  }
  return {version:'1.4.6',platform,source_url:canonical,items,captured_at:now,read_scope:options.mode==='selection'?'selected_public_text':options.mode==='post'?'current_public_post':'displayed_comment_nodes',automatically_sent:false};
 }
 function inspectPublicPage(options={}){
  const doc=options.document||document,win=doc.defaultView,url=options.source_url||win.location.href,u=new URL(url),platform=platformForUrl(url);
  if(!platform||/\/(?:login|passport|settings?|privacy|messages?|im|chat|inbox|notification)(?:\/|$)/i.test(u.pathname))return {blocked:'不读取登录、设置、私信或通知页面'};
  const blockers=[...doc.querySelectorAll('[role="dialog"],.login-container,.login-modal,.captcha-container')].filter(n=>visible(n,win));
  if(blockers.some(n=>/扫码登录|验证码|安全验证|登录后/.test(text(n))))return {blocked:'平台需要登录或安全验证，请本人完成后再启动'};
  const adapter=adapters[platform];if(!adapter)return {blocked:'该平台尚未适配公开浏览器采集'};
  if(platform==='douyin'&&/^\d{10,25}$/.test(u.searchParams.get('modal_id')||'')){
   // The address bar identifies the selected work even while the modal's body
   // is being replaced. Read its canonical page instead of adjacent feed nodes.
   return {kind:'detail',needs_canonical:true,platform,source_url:canonicalUrl(url,platform),
    display_url:url,ready_state:doc.readyState,items:[],captured_at:new Date().toISOString()};
  }
  const isSearch=/^\/search(?:\/|$)|^\/search_result\/?$/.test(u.pathname);
  if(isSearch){
   const seen=new Set(),links=[];
   for(const a of doc.querySelectorAll('a[href]')){
    if(!visible(a,win))continue;
    let target;try{target=new URL(a.getAttribute('href'),url)}catch{continue}
    if(target.origin!==u.origin||!looksRelevant(text(a)))continue;
    if(!(adapter.detail.test(target.href)||(platform==='xiaohongshu'&&/^\/search_result\/[a-f0-9]{24}$/.test(target.pathname))))continue;
    const key=target.origin+target.pathname;if(seen.has(key))continue;seen.add(key);links.push(target.href);
    if(links.length>=5)break;
   }
   // The currently observed Douyin search layout exposes clickable titles, not hrefs.
   // Keep titles as UI targets; never inspect React state or manufacture video identifiers.
   const targets=platform==='douyin'?[...doc.querySelectorAll('.BjLsdJMi')]
    .filter(n=>{const r=n.getBoundingClientRect(),s=win.getComputedStyle(n);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'})
    .map(n=>text(n)).filter(t=>t.length<=500&&looksRelevant(t)).slice(0,5):[];
   return {kind:'search',platform,source_url:url,display_url:url,ready_state:doc.readyState,links,targets,
    search_sort:platform==='douyin'?searchSortState(doc,win):null};
  }
  if(!adapter.detail.test(url))return {blocked:'尚未显示可核对的原帖地址；不使用搜索页作为来源'};
  return {kind:'detail',display_url:url,ready_state:doc.readyState,...collect({...options,mode:'all'})};
 }
 function openSearchTitle(title,options={}){
  const doc=options.document||document,win=doc.defaultView,url=options.source_url||win.location.href;
  if(platformForUrl(url)!=='douyin'||!new URL(url).pathname.startsWith('/search/')||!looksRelevant(title)||title.length>500)throw Error('不是已核对的抖音搜索标题');
  const matches=[...doc.querySelectorAll('.BjLsdJMi')].filter(n=>text(n)===title);
  if(matches.length!==1)throw Error('搜索结果已变化或标题不唯一，停止自动打开');
  matches[0].scrollIntoView({block:'center'});
  // Return the preparation acknowledgement before a click can replace its
  // document/execution context. The worker verifies the resulting page later.
  win.setTimeout(()=>{if(matches[0].isConnected)matches[0].click()},150);
  return {scheduled:true,title};
 }
 globalThis.GinkgoCapture={platformForUrl,redact,looksRelevant,canonicalUrl,collect,inspectPublicPage,openSearchTitle,searchSortState,ensureRecentSearch};
})();
