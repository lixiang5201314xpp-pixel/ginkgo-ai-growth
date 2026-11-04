from pathlib import Path
root=Path(__file__).parent
source=(root.parent/'ginkgo-growth/test_capture_browser.html').read_text(encoding='utf-8')
source=source.replace('browser-helper/capture.js','/capture-script')
extra=r'''
 await test('小红书正文与评论各保留自己的时间','<section><div class="note-content"><h1>找一位成都乒乓球教练</h1><div id="detail-desc">希望提高正手</div><span class="date">3天前 四川</span></div><div class="comment-item"><div class="content">成都想找乒乓球球搭子</div><span class="date">昨天 14:26四川</span></div></section>',doc=>{const b=read(doc,'all','https://www.xiaohongshu.com/explore/6ae233c7000000003501eedb');check(b.items.length===2,'没有同时采集作品与评论');check(b.items[0].posted_text==='3天前 四川','作品日期被评论覆盖');check(b.items[1].posted_text==='昨天 14:26四川','评论日期错误')});
 await test('搜索仅收同源真实求助链接','<a href="https://www.xiaohongshu.com/search_result/6ae233c7000000003501eedb">成都找乒乓球教练</a><a href="https://evil.invalid/explore/a">成都找乒乓球教练</a><a href="https://www.xiaohongshu.com/user/profile/a">成都找乒乓球教练</a><a href="https://www.xiaohongshu.com/explore/6ae233c7000000003501eedc">乒乓球培训班招生，欢迎报名</a>',doc=>{const b=GinkgoCapture.inspectPublicPage({document:doc,source_url:'https://www.xiaohongshu.com/search_result?keyword=成都乒乓球'});check(b.kind==='search'&&b.links.length===1,'混入异站、个人主页或广告')});
 await test('验证码停止采集而非尝试绕过','<div role="dialog">请完成安全验证</div>',doc=>{const b=GinkgoCapture.inspectPublicPage({document:doc,source_url:'https://www.douyin.com/search/成都乒乓球'});check(!!b.blocked,'验证码未阻止自动读取')});
 await test('私信页不会读取','<h1>成都想找乒乓球教练</h1>',doc=>{const b=GinkgoCapture.inspectPublicPage({document:doc,source_url:'https://www.xiaohongshu.com/chat'});check(!!b.blocked,'读取了私信页')});
 await test('抖音搜索标题通过真实点击打开','<div class="BjLsdJMi">成都想找乒乓球教练</div>',doc=>{let clicks=0;doc.querySelector('.BjLsdJMi').onclick=()=>clicks++;const r=GinkgoCapture.openSearchTitle('成都想找乒乓球教练',{document:doc,source_url:'https://www.douyin.com/search/成都乒乓球'});check(r.clicked&&clicks===1,'没有准确点击原文标题')});
 await test('抖音搜索弹窗识别为具体作品','<div data-e2e="feed-active-video"><div data-e2e="video-desc">成都想找乒乓球教练</div><span>发布时间：2026-10-27 23:38</span></div>',doc=>{const b=GinkgoCapture.inspectPublicPage({document:doc,source_url:source});check(b.kind==='detail'&&b.source_url==='https://www.douyin.com/video/7701372394577607067','误把作品弹窗当搜索页')});
'''
source=source.replace(' document.title=results.every',extra+'\n document.title=results.every')
(root/'test_capture_browser.html').write_text(source,encoding='utf-8')
