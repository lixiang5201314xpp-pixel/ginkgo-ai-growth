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
 function ownNodes(row,selector,rows){return [...row.querySelectorAll(selector)].filter(n=>n.closest(rows)===row)}
 function pageScope(doc,win,platform,source){
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
  else if(options.mode==='post'){
   if(platform!=='douyin')throw Error('当前作品求助读取暂适配抖音；其他平台可选中原文读取。');
   add(text(scope.post),postDate(scope.root,win,adapter.rows),'post');
  }
  else for(const row of scope.root.querySelectorAll(adapter.rows)){
   if(items.length>=20)break;if(!visible(row,win))continue;
   const body=ownNodes(row,adapter.body,adapter.rows).find(n=>visible(n,win));if(!body)continue;
   const dates=ownNodes(row,adapter.time,adapter.rows).map(n=>n.getAttribute('datetime')||text(n));
   const date=dates.find(x=>/^(刚刚|刚才|\d+\s*(分钟|小时|天)前|今天|昨天|前天|\d{4}[-/.]\d|\d\d?[-/]\d)/.test(x))||'';
   add(text(body),date.slice(0,60));
  }
  return {version:'1.3.1',platform,source_url:canonical,items,captured_at:now,read_scope:options.mode==='selection'?'selected_public_text':options.mode==='post'?'current_public_post':'displayed_comment_nodes',automatically_sent:false};
 }
 globalThis.GinkgoCapture={platformForUrl,redact,looksRelevant,canonicalUrl,collect};
})();
