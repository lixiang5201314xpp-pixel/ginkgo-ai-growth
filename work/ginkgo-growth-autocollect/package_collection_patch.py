"""Freeze the small server filter patch; browser helper 1.4.3 is compatible."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from package_collection import BASE,WORK,CHAIN as PRIOR_CHAIN

CHAIN=PRIOR_CHAIN+[('growth-collection-20261101/GinkgoGrowth-1.4.0','external-manifest.json')]
RELEASE=WORK/'release/growth-collection-patch-20261101'
PACKAGE=RELEASE/'GinkgoGrowth-1.4.1'
FILES=['growth_collection.py','growth_external.py','growth-web/collection.js','growth-web/browser-helper.zip']
TESTS=['test_growth.py','test_ai.py','test_workflow.py','test_external.py','test_delivery.py','test_collection.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for name in ('continuous-verification.json','capture-browser-verification.json','status-bridge-verification.json'):
        assert json.loads((BASE/name).read_text(encoding='utf-8'))['passed'],name
    prior=WORK/'release/growth-collection-20261101/GinkgoGrowth-1.4.0'
    manifest=json.loads((prior/'payload/external-manifest.json').read_text(encoding='utf-8'))
    old={item['path']:item['sha256'] for item in manifest['files']}
    for name,value in old.items():assert sha(prior/'payload'/name)==value,name
    with zipfile.ZipFile(prior/'payload/growth-web/browser-helper.zip') as z:
        old_helper=json.loads(z.read('browser-helper/manifest.json'))
    new_helper=json.loads((BASE/'browser-helper/manifest.json').read_text(encoding='utf-8'))
    assert old_helper['permissions']==new_helper['permissions']
    assert old_helper['host_permissions']==new_helper['host_permissions']
    assert new_helper['version']=='1.4.3'
    with zipfile.ZipFile(BASE/'growth-web/browser-helper.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((BASE/'browser-helper').iterdir()):
            if p.is_file():z.write(p,'browser-helper/'+p.name)
    payload=PACKAGE/'payload';payload.mkdir(parents=True,exist_ok=True)
    result={'version':'growth-external-1.4.1','installer_version':'1.4.1',
            'baseline':{n:[old[n]] for n in FILES},'files':[]}
    for name in FILES:
        target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/name,target)
        result['files'].append({'path':name,'sha256':sha(target)})
    (payload/'external-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    installer=(prior/'install_growth_external.py').read_text(encoding='utf-8').replace('1.4.0','1.4.1')
    installer=installer.replace('Adds a delivery receipt table in the acquisition store only. No channel settings, existing customer records or mini-app uploads are changed.',
        'Skips confirmed old public content and deduplicates formatting-only post titles. No account, schema, credential, existing-record repair or mini-app upload changes.')
    installer=installer.replace('SUCCESS: bounded browser collection, automatic intake/AI preparation and delivery review installed and verified.',
        'SUCCESS: old-content filtering and same-post duplicate protection installed and verified. Existing reception and helper retained.')
    installer=installer.replace('NEXT: refresh the workbench, enable Automatic Intake and reload the local browser helper 1.4.1. Start collection on a logged-in public search page. External auto-sending and Channels collection are NOT connected.',
        'NEXT: refresh the workbench. Helper 1.4.3 is compatible. External auto-sending and Channels collection are NOT connected.')
    (PACKAGE/'install_growth_external.py').write_text(installer,encoding='utf-8')
    shutil.copy2(prior/'Install-Growth-External.cmd',PACKAGE/'Install-Growth-External.cmd')
    for name in TESTS:shutil.copy2(BASE/name,PACKAGE/name)
    (PACKAGE/'使用说明.txt').write_text('''银杏获客后台小补丁1.4.1（配合本机助手1.4.3）
兼容已安装后台1.4.0。只更新4个获客文件：过滤模块、外部模块版本号、采集记录显示、助手下载包。
已核对超过30天的旧原文自动排除；未知日期仍待核实。原视频较旧但新评论有近期日期时，仍按评论自己的时间判断。
同一原帖的第9集：与第9集 |等格式差异不再新建重复需求；不同原帖以及同帖不同评论不会合并。
不会清理、合并、修改原客户记录，不修改账号、奖牌、积分、密钥、调用上限或微信AI接待设置。
服务器管理员运行Install-Growth-External.cmd，先预检备份，短暂重启；失败自动还原。
本机助手1.4.3已更新到原桌面文件夹，在Chrome扩展管理页刷新一次后可启动；后台补丁安装完成后刷新获客工作台即可。外部自动发评论/私信和视频号浏览器采集仍未连接。
''',encoding='utf-8')
    archive=RELEASE/'GinkgoGrowth-1.4.1.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACKAGE.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,p.relative_to(PACKAGE.parent))
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'payload_files':len(FILES)}))

if __name__=='__main__':main()
