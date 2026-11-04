from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent
RELEASE=ROOT.parent/'release/growth-channels-20261030'
PACKAGE=RELEASE/'GinkgoOfficialChannels-1.0.0'
BASELINE=ROOT.parent/'release/growth-ai-20261030/GinkgoGrowth-1.1.0/payload/manifest.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    names=['growth_acquisition.py','growth_channels.py','growth-web/index.html','growth-web/channels.js']
    names += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'channel-vendor').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    old={x['path']:x['sha256'] for x in json.loads(BASELINE.read_text('utf-8'))['files']}
    manifest={'version':'growth-channels-1.0.0','baseline':{k:old[k] for k in ('growth_acquisition.py','growth-web/index.html')},'files':[]}
    for name in names:
        dest=payload/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        manifest['files'].append({'path':name,'sha256':sha(dest)})
    (payload/'channels-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    for name in ['install_growth_channels.py','Install-Official-Channels.cmd','configure_channels.py','Configure-Channels.cmd','growth_permissions.py','test_channels.py']:
        shutil.copy2(ROOT/name,PACKAGE/name)
    note='''银杏官方客服接入 1.0.0

先运行 Install-Official-Channels.cmd：离线预检、备份、短暂重启，失败还原。
再运行 Configure-Channels.cmd：只在独立窗口中配置官方消息凭据。

微信：开发管理→消息推送，安全模式、JSON。填写窗口给出的地址、Token、EncodingAESKey。
抖音：开发配置→Webhook，先启用独立Webhook密钥；经营账号OpenID可从已授权经营账号详情查看。
回调地址验证成功后，只订阅 im_receive_msg 和 im_send_msg；不订阅不需要的营销／群发事件。
平台验证后，在获客工作台→渠道接入→接待开关启用AI；用自己的测试账号发一句训练问题验证实际回复。
没有完成这些步骤前，不能称为已接通。

快手：已在官方客服工作台保存团队报名话术；这不是DeepSeek接入。当前后台没有已验证的外部AI消息接口。
小红书：消息解密文档跳到了登录数据解密说明，缺少消息推送SDK／测试向量，暂不启用，以免接入后丢消息。
小程序客服不等于四个平台全部公开评论权限，也不等于视频号私信权限。

保留现有账号、比赛、积分、奖牌、加密AI密钥；不上传或提交小程序版本。
新咨询加密存储，7天清理；用户转人工／拒绝联系后停止AI。发送结果不明时人工核对，绝不自动重复发送。
'''
    (PACKAGE/'使用说明.txt').write_text(note,'utf-8')
    archive=RELEASE/'GinkgoOfficialChannels-1.0.0.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in PACKAGE.rglob('*'):
            if path.is_file():z.write(path,path.relative_to(PACKAGE.parent))
    report={'version':'growth-channels-1.0.0','archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'files':len(names),'installed':False,'platform_messages_sent':0}
    (RELEASE/'status.json').write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))
if __name__=='__main__':main()
