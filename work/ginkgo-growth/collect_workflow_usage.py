"""Read-only aggregate workflow diagnostics. No credentials, customer text, API calls or restart."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import sqlite3

TARGET=Path(r'C:\Services\KaiqiuMatch_20260915\growth-data\acquisition.sqlite3')
OUT=Path(__file__).with_name('workflow-usage-diagnostics.json')


def main():
    result={'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'read_only':True,'api_calls':0,'contains_credentials_or_customer_text':False}
    try:
        with sqlite3.connect(TARGET.as_uri()+'?mode=ro',uri=True,timeout=8) as c:
            c.row_factory=sqlite3.Row
            row=c.execute("SELECT value FROM settings WHERE key='ai_config'").fetchone()
            config=json.loads(row[0]) if row else {}
            fields=['provider','model','enabled','search_enabled','automatic','daily_ai_limit','daily_search_limit',
                    'interval_minutes','paid_usage_authorized','data_processing_authorized']
            result['config']={k:config.get(k) for k in fields}
            result['usage']=[dict(r) for r in c.execute('SELECT day,kind,status,COUNT(*) AS n FROM ai_usage GROUP BY day,kind,status ORDER BY day DESC LIMIT 40')]
            result['search_runs']=[dict(r) for r in c.execute('SELECT day,platform,intent,state,updated_at FROM growth_search_runs ORDER BY updated_at DESC LIMIT 16')]
            result['counts']={}
            for table in ('growth_candidates','leads','inquiries','growth_content'):
                result['counts'][table]=c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
            jobs=[]
            for r in c.execute('SELECT id,kind,status,error,created_at,result FROM growth_jobs ORDER BY created_at DESC LIMIT 10'):
                d=dict(r);parts=json.loads(d.pop('result'));safe={}
                allowed=('error_code','queries_completed','searches_skipped','new_web_candidates','ai_screened','analysis_note',
                         'blocked_reason','errors','analyzed','drafts_prepared','plans_prepared','channel_drafts')
                for section,v in parts.items():
                    if isinstance(v,dict):safe[section]={k:v[k] for k in allowed if k in v}
                d['result']=safe;jobs.append(d)
            result['jobs']=jobs
    except (sqlite3.Error,OSError) as e:
        result.update(ok=False,error=type(e).__name__,message='Read-only usage inspection could not access the dedicated store.')
    else:result['ok']=True
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
