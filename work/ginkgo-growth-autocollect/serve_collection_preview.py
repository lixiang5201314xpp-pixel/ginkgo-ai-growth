"""Loopback-only synthetic UI; no API keys or production data."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'python-deps'))
from flask import Flask,send_from_directory
import growth_acquisition as growth

temp=tempfile.TemporaryDirectory(prefix='ginkgo-collection-preview-')
app=Flask('synthetic-collection-preview')
app.testing=True
growth.register(app,data_dir=temp.name,local_token='synthetic-collection-test',catalog_fetcher=lambda:{'items':[]})
@app.get('/capture-test')
def capture_test():
    return send_from_directory(Path(__file__).parent,'test_capture_browser.html')
@app.get('/capture-script')
def capture_script():
    return send_from_directory(Path(__file__).parent/'browser-helper','capture.js')
if __name__=='__main__':
    app.run(host='127.0.0.1',port=8796,debug=False,use_reloader=False)
