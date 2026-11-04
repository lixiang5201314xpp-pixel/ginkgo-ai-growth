"""Compare the frozen release and local receipt-source fix without live access."""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'work/ginkgo-growth-autocollect'
R=ROOT/'work/release/growth-dev-20261102'
BASELINE=R/'GinkgoGrowth-1.4.5/payload'
env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'}

code='''import sys,runpy
from pathlib import Path
sys.path[:0]=[BASELINE,SRC,DEPS]
import growth_acquisition as g
g.BASE=Path(SRC)
runpy.run_path(TEST,run_name='__main__')
'''.replace('BASELINE',repr(str(BASELINE))).replace('SRC',repr(str(SRC))).replace('DEPS',repr(str(ROOT/'work/python-deps'))).replace('TEST',repr(str(SRC/'test_delivery_source.py')))
baseline=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,encoding='utf-8',env=env,timeout=90)
assert baseline.returncode!=0 and 'FAILED (failures=7)' in baseline.stderr,baseline.stderr[-3000:]
(R/'round-010-frozen-baseline-reproduction.txt').write_text(baseline.stderr,encoding='utf-8')
checks=[]
for name,count in [('test_delivery_source.py',12),('test_delivery.py',28),('test_growth.py',50),('test_workflow.py',20)]:
    result=subprocess.run([sys.executable,str(SRC/name)],capture_output=True,text=True,encoding='utf-8',env=env,cwd=SRC,timeout=90)
    summary=re.search(r'Ran (\d+) tests?',result.stderr)
    assert result.returncode==0 and summary and int(summary[1])==count,(name,result.stderr[-4000:])
    checks.append({'suite':name,'tests':count,'passed':True})
    print('PASS: '+name+' / '+str(count),flush=True)

archive=R/'GinkgoGrowth-1.4.5.zip'
meta=json.loads((R/'backend-package-1.4.5.json').read_text('utf-8'))
assert hashlib.sha256(archive.read_bytes()).hexdigest()==meta['sha256']
manifest=json.loads((BASELINE/'external-manifest.json').read_text('utf-8'))
for item in manifest['files']:
    assert hashlib.sha256((BASELINE/item['path']).read_bytes()).hexdigest()==item['sha256']
old=(BASELINE/'growth_acquisition.py').read_text('utf-8').replace('growth-external-1.4.5','growth-external-1.4.3')
new=(SRC/'growth_acquisition.py').read_text('utf-8')
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='frozen-1.4.5/growth_acquisition.py',tofile='candidate/growth_acquisition.py'))
(R/'round-010-delivery-source.patch').write_text(patch,encoding='utf-8')
report={'passed':True,'checked_at':datetime.now(timezone.utc).isoformat(),
    'baseline':'frozen growth-external-1.4.5','baseline_reproduced_failures':7,'baseline_reproduction_cases':12,
    'checks':checks,'candidate_checks':sum(x['tests'] for x in checks),
    'candidate_source_sha256':hashlib.sha256((SRC/'growth_acquisition.py').read_bytes()).hexdigest(),
    'frozen_1_4_5_unchanged':True,'runtime_deployed':False,'staged_package_updated':False,
    'live_api_calls':0,'platform_messages':0,'production_data_changes':0,
    'note':'Only local candidate source and temporary SQLite tests; no real publication confirmation or booking is asserted.'}
(R/'round-010-delivery-source-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
