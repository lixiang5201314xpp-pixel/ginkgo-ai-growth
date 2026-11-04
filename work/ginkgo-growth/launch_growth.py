"""Start only a loopback service, then open its private desktop entry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

BASE = Path(__file__).resolve().parent
PORT = int(os.getenv('GINKGO_GROWTH_PORT', '8796'))
ROOT = BASE / 'growth-data'


def ready():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/match-center/growth/health', timeout=2) as r:
            return str(json.load(r).get('version','')).startswith('ginkgo-growth-')
    except Exception:
        return False


def main():
    ROOT.mkdir(exist_ok=True)
    if not ready():
        # Development workspace runtime only; production Flask is already installed.
        deps = BASE.parent / 'python-deps'
        env = dict(os.environ)
        if deps.is_dir(): env['PYTHONPATH'] = str(deps) + os.pathsep + env.get('PYTHONPATH', '')
        log = open(ROOT / 'server.log', 'ab')
        subprocess.Popen([sys.executable, str(BASE/'growth_acquisition.py')], cwd=BASE, env=env,
                         stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        log.close()
        for _ in range(50):
            if ready(): break
            time.sleep(.2)
        else:
            raise RuntimeError('工作台启动失败，请查看 growth-data/server.log')
    token = json.loads((ROOT/'local-access.json').read_text('utf-8'))['token']
    if '--no-browser' not in sys.argv:
        webbrowser.open(f'http://127.0.0.1:{PORT}/api/match-center/growth/#token={token}')
    print('Local workbench is ready on port ' + str(PORT) + '. Access token is not printed.')


if __name__ == '__main__': main()
