"""Ephemeral browser QA instance, never production customer data."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
from flask import Flask
import growth_acquisition as growth
root=tempfile.TemporaryDirectory(prefix='ginkgo-growth-ui-')
app=Flask(__name__)
growth.register(app,data_dir=root.name,local_token='fixture-only',catalog_fetcher=lambda:{'items':[]})
if __name__=='__main__': app.run('127.0.0.1',8817,debug=False)
