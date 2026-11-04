"""Called by the owner-run installer; real API key never printed or returned."""
from pathlib import Path
import json
import sys
import traceback
sys.dont_write_bytecode=True
PHASE='initialization'

def main():
    global PHASE
    target=Path(sys.argv[1]);check_only='--check-access' in sys.argv[2:]
    verify_only='--verify-ai' in sys.argv[2:];enable_only='--enable-only' in sys.argv[2:]
    sys.path.insert(0,str(Path(__file__).resolve().parent/'payload' if (check_only or verify_only) else target))
    PHASE='load_modules'
    from growth_acquisition import Store
    from growth_ai import AIService,AIError
    PHASE='open_acquisition_store'
    store=Store(target/'growth-data');ai=AIService(store)
    PHASE='read_encrypted_credential'
    status=ai.status()
    if status.get('key_error'):
        print('Credential access check: '+status['key_error']);return 1
    if not status['enabled'] or not status['key_configured']:
        print('AI is not configured. Run Configure-AI.cmd, then rerun this installer.');return 1
    if check_only:
        print('PASS: existing encrypted key can be read and machine-DPAPI decrypted before service restart.')
        return 0
    if not enable_only:
        shape={}
        original_transport=ai.transport
        def checked_transport(*args,**kwargs):
            response=original_transport(*args,**kwargs)
            # Only this installer instance uses known synthetic questions. Record
            # schema diagnostics, never request headers, keys or generated prose.
            if args[1]=='/chat/completions':
                try:
                    obj=json.loads(response['choices'][0]['message']['content'])
                    if isinstance(obj,dict):
                        shape.clear();shape.update(types={k:type(v).__name__ for k,v in obj.items() if k in ('intent','explicit_need','reply','confidence','event_id','followup_hours')})
                        val=obj.get('intent')
                        if isinstance(val,str) and len(val)<=32 and all(c.isalpha() or c in '_-/ ' for c in val):shape['intent_label']=val
                except Exception:pass
            return response
        ai.transport=checked_transport
        PHASE='model_connection'
        checked=ai.test_connection()
        if not checked['ok']:print('AI connection check: '+checked['message']);return 1
        # Validate both customer replies and background classifications before any restart.
        try:
            PHASE='synthetic_generation'
            checks=[('inbound_question','儿童每周来两次，25次卡每次多长时间、多少钱？'),
                    ('inbound_question','银杏1600分组以下限分比赛获得前三名，成人训练课程怎么获得？'),
                    ('reply','我在成都，想找乒乓球基础教练，请问哪里有合适的训练？')]
            for task,question in checks:
                r=ai.analyze({'platform':'douyin','excerpt':question},[],task)
                if not r['reply']:raise AIError('AI returned no reply','empty')
            print('PASS: three real DeepSeek synthetic checks: children fees, adult auto-issued courses and background JSON classification.')
        except AIError as e:
            print('AI generation check: '+str(e))
            print('Synthetic output schema only: '+json.dumps(shape,ensure_ascii=True))
            return 1
    if verify_only:
        print('PASS: live AI validation completed BEFORE service restart; no customer messages.')
        return 0
    # Store just a nonsensitive switch; preserve credential, daily limits and explicit purpose consent.
    cfg=ai.config();cfg['automatic']=True
    PHASE='enable_schedule'
    with store.db() as c:
        c.execute("INSERT INTO settings(key,value) VALUES('ai_config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(cfg),))
        store.audit(c,None,'ai_activation','启用定时 AI 工作流；真实生成预检仅使用模拟问题；未发送客户消息','管理员安装器')
    print('PASS: automatic scheduling enabled; existing encrypted credential and daily caps retained.')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        # No traceback or request/credential values in a copied console result.
        diagnostic={'phase':PHASE,'error_type':type(e).__name__,'errno':getattr(e,'errno',None),
                    'path':str(getattr(e,'filename','') or ''),
                    'frames':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(e.__traceback__)[-4:]]}
        print('AI activation did not complete: '+json.dumps(diagnostic,ensure_ascii=True));sys.exit(1)
