"""Owner-run settings change and one bounded search probe. No restart or social messages."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import sys

BASE=Path(__file__).resolve().parent
RUNTIME=Path(r'C:\Services\KaiqiuMatch_20260915')


def configure_and_probe(store,ai):
    before=ai.config()
    state=ai.configure({'daily_search_limit':20})
    after=ai.config()
    for key,value in before.items():
        if key!='daily_search_limit' and after.get(key)!=value:raise RuntimeError('Unrelated AI setting changed')
    result={'search_limit_before':before['daily_search_limit'],'daily_search_limit':state['daily_search_limit'],
            'daily_ai_limit':state['daily_ai_limit'],'enabled':state['enabled'],'search_enabled':state['search_enabled'],
            'automatic':state['automatic'],'key_configured':state['key_configured'],
            'service_restarted':False,'social_messages_sent':0,'usage_reset':False}
    day=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    def usage():
        with store.db() as c:
            return [dict(x) for x in c.execute('SELECT kind,status,COUNT(*) AS n FROM ai_usage WHERE day=? GROUP BY kind,status',(day,))]
    result['usage_before_probe']=usage()
    try:
        items=ai.search('成都 乒乓球 训练 site:douyin.com')
        result['probe']={'ok':True,'result_count':len(items),'note':'Search API responded; result count is not customer count.'}
    except Exception as e:
        from growth_ai import AIError
        if not isinstance(e,AIError):raise
        result['probe']={'ok':False,'error_code':e.code,'message':str(e)}
    result['usage_after_probe']=usage()
    return result


def main():
    sys.path.insert(0,str(RUNTIME))
    from growth_acquisition import Store
    from growth_ai import AIService
    store=Store(RUNTIME/'growth-data');ai=AIService(store)
    result=configure_and_probe(store,ai)
    (BASE/'search-limit-20-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('SUCCESS: daily search limit is 20; other settings and existing usage retained. Probe result is recorded above.')


if __name__=='__main__':main()
