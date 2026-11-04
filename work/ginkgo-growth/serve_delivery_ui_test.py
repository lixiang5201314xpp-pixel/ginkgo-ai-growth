"""Loopback UI preview with synthetic receipts. No real accounts, AI calls or messages."""
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
from flask import Flask
import growth_acquisition as growth

tmp=tempfile.TemporaryDirectory(prefix='ginkgo-delivery-preview-')
app=Flask('synthetic-delivery-preview')
growth.register(app,data_dir=tmp.name,local_token='synthetic-browser-test',catalog_fetcher=lambda:{'items':[]})
store=app.extensions['ginkgo_growth']['store']
for i in range(3):
    lead,_=store.add({'platform':'xiaohongshu' if i<2 else 'kuaishou',
        'source_url':'https://www.xiaohongshu.com/explore/synthetic'+str(i) if i<2 else 'https://www.kuaishou.com/short-video/synthetic2',
        'excerpt':['模拟需求A：成都想找乒乓球教练，请问怎么上课？','模拟需求B：成都有乒乓球训练吗，想问价格？','模拟需求C：成都哪里能找乒乓球球搭子？'][i],
        'posted_at':datetime.now(timezone.utc).isoformat(),'confirmed':True},'本机隔离预览')
    with store.db() as c:
        c.execute('UPDATE leads SET latest_reply=? WHERE id=?',('模拟草稿：请查看本平台课程安排。',lead['id']))
    if i<2:
        with app.test_client() as client:
            r=client.post(growth.PREFIX+'/api/leads/'+lead['id']+'/delivery-attempts',headers={'Authorization':'Bearer synthetic-browser-test'},json={
                'account':'模拟俱乐部账号','content':'模拟回复，不会发到任何真实平台。','evidence_url':lead['source_url'],
                'status':'pending' if i==0 else 'not_visible','note':'' if i==0 else '模拟手机核对：未显示，保留草稿。',
                'submitted_in_platform':True,'checked_in_platform':True,'request_id':'synthetic-preview-'+str(i)})
            assert r.status_code==201,r.json
if __name__=='__main__':
    app.run(host='127.0.0.1',port=8798,debug=False,use_reloader=False)
