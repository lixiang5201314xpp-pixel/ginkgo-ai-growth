"""Loopback-only UI test. Synthetic local account/data; no live API or worker."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
from flask import Flask
import growth_acquisition

data=tempfile.TemporaryDirectory(prefix='ginkgo-external-ui-')
app=Flask('synthetic-external-ui')
growth_acquisition.register(app,data_dir=data.name,local_token='synthetic-browser-test',catalog_fetcher=lambda:{'items':[]})
if __name__=='__main__':app.run(host='127.0.0.1',port=8799,debug=False,use_reloader=False)
