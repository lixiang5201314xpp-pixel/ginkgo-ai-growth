"""Small checked edits to the existing UI, preserving its deployed layout."""
from pathlib import Path
p=Path(__file__).with_name('growth-web')/'app.js'
s=p.read_text('utf-8')
edits=[
 ('</div><h3>跟进结果</h3>', '</div>${deliveryPanel(l,d.delivery||[])}<h3>跟进结果</h3>'),
 ("};bindReply();$('#draftReply')", "};bindReply();bindDelivery(l,d.delivery||[]);$('#draftReply')"),
 ('此处只做人工记录，不能验证平台送达。','请先确认原平台已经显示该回复；仅点击发送但未看到，请返回使用“记录发送核对”。此处只做人工记录，不能验证平台送达。'),
 ('<select id="leadStage">','<select id="leadDelivery" aria-label="发送核对状态"><option value="">所有发送状态</option><option value="none">尚无发送记录</option><option value="pending">已提交待核实</option><option value="not_visible">核对未显示</option><option value="failed">平台提示失败</option><option value="confirmed">已登记发布</option></select><select id="leadStage">'),
 ("s=$('#leadStage').value;const list=rows.filter", "s=$('#leadStage').value,v=$('#leadDelivery').value;const list=rows.filter"),
 ("&&(!s||x.stage===s));$('#leadRows')", "&&(!s||x.stage===s)&&(!v||x.delivery_status===v));$('#leadRows')"),
 ("${esc(meta.stages[l.stage])}</span></td>", "${esc(meta.stages[l.stage])}</span><p>${esc(deliveryLabel(l.delivery_status))}</p></td>"),
 ("$('#leadStage').onchange=render;", "$('#leadStage').onchange=render;$('#leadDelivery').onchange=render;")
]
for old,new in edits:
    assert s.count(old)==1,(old,s.count(old))
    s=s.replace(old,new)
p.write_text(s,'utf-8')
print('Updated detail, notes and delivery-state filtering with checked markers.')
