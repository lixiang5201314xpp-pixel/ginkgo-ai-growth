from pathlib import Path
root=Path(__file__).resolve().parent/'growth-web'
p=root/'index.html';s=p.read_text('utf-8')
if 'assets/automation.js' not in s:s=s.replace('<script src="assets/app.js" defer></script>','<script src="assets/app.js" defer></script><script src="assets/automation.js" defer></script>')
if 'data-page="automate"' not in s:s=s.replace('<button data-page="content">','<button data-page="automate">✧ <span>AI 自动执行</span></button><button data-page="aiSettings">⚙ <span>AI 设置</span></button><button data-page="content">')
s=s.replace('银杏获客 1.0','银杏获客 1.1')
s=s.replace('俱乐部管理员专用。使用银杏奖牌已有账号登录。','无需重新注册。俱乐部管理员使用银杏奖牌已有的姓名、手机号和密码登录。')
p.write_text(s,'utf-8')
p=root/'app.js';s=p.read_text('utf-8')
s=s.replace('content,campaigns,inquiries,connections}[name]','content,campaigns,inquiries,connections,automate,aiSettings}[name]')
s=s.replace('JSON.parse(decodeURIComponent(capture))','JSON.parse(capture)')
if s.rstrip().endswith('boot();'):s=s.rstrip()[:-7]+"document.addEventListener('DOMContentLoaded',boot,{once:true});\n"
p.write_text(s,'utf-8')
p=root/'app.css';s=p.read_text('utf-8')
if '.automationBar{' not in s:s+='''
.automationBar{background:#edf4e7;border:1px solid #d4e3c7;border-radius:12px;padding:20px 24px;display:flex;align-items:center;gap:14px;margin-bottom:22px}.automationBar>div{flex:1}.automationBar strong{font-size:14px}.automationBar p{font-size:11px;color:#87987b;margin:6px 0 0}.stepAction{width:100%;border:0;border-top:1px solid #edf0e7;border-radius:0;text-align:left;background:none}.stepAction:hover{background:#f4f8ef}.jobProgress{width:100%;height:12px;accent-color:#57814e}.jobResult{margin-top:20px;padding:18px;border:1px solid #e1e6d7;background:#fff;border-radius:10px}.jobResult h3{margin:0 0 10px}.jobResult p{font-size:12px;margin:7px 0}.taskCard{text-align:left}.taskCard h2{font-size:16px;margin:18px 0 12px}.taskCard p{font-size:12px;color:#819178}.jobRow{display:flex;align-items:center;gap:16px;padding:16px 0;border-top:1px solid #e7ebdf;font-size:12px}.jobRow>div{flex:1}.jobRow p{font-size:11px;color:#94a088;margin:7px 0 0}.candidate{padding:20px 0;border-top:1px solid #e5eadc}.candidate h3{margin:15px 0 8px}.candidate p{font-size:12px;color:#7c8e70;line-height:1.9}.connectionStatus{padding:12px 0 18px}.connectionStatus p{font-size:12px;margin:15px 0 0}
@media(max-width:750px){.automationBar{flex-wrap:wrap;padding:18px}.automationBar>div{flex-basis:100%}.jobRow{flex-wrap:wrap}.jobRow>div{flex-basis:100%}.sidebarBottom{display:flex;align-items:center;justify-content:space-between;padding:12px 0 0}.sidebarBottom p{display:none}.jobResult{padding:14px}}
'''
p.write_text(s,'utf-8')
print('AI navigation, clickable steps and secure configuration UI prepared.')
