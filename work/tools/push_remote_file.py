"""Copy a local file to a public production-server path through xp_cmdshell."""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-deps"))
import pymssql


def execute(cur, command: str):
    cur.execute("EXEC master..xp_cmdshell %s", (command,))
    return [str(row["output"]) for row in cur.fetchall() if row["output"] is not None]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local", type=Path)
    parser.add_argument("remote")
    args = parser.parse_args()
    payload = args.local.read_bytes()
    encoded = base64.b64encode(payload).decode("ascii")
    remote = args.remote
    remote_dir = str(Path(remote).parent)
    staging = remote + ".b64"
    conn = pymssql.connect(
        server="139.155.99.55", user="lixiang",
        password=os.environ["KAIQIU_DB_PASSWORD"], database="master",
        as_dict=True, charset="UTF-8", autocommit=True,
        login_timeout=10, timeout=120,
    )
    cur = conn.cursor(as_dict=True)
    cur.execute("SELECT CAST(value_in_use AS int) enabled FROM sys.configurations WHERE name='xp_cmdshell'")
    original = int(cur.fetchone()["enabled"])
    try:
        if not original:
            cur.execute("EXEC sp_configure 'show advanced options',1; RECONFIGURE; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;")
        execute(cur, f'cmd /d /c if not exist "{remote_dir}" mkdir "{remote_dir}"')
        execute(cur, f'cmd /d /c type nul > "{staging}"')
        for offset in range(0, len(encoded), 3000):
            chunk = encoded[offset:offset + 3000]
            execute(cur, f'cmd /d /c <nul set /p="{chunk}" >> "{staging}"')
        command = (
            "powershell -NoProfile -NonInteractive -Command "
            f'"$b=[Convert]::FromBase64String([IO.File]::ReadAllText(\'{staging}\')); '
            f'[IO.File]::WriteAllBytes(\'{remote}\',$b); Remove-Item -LiteralPath \'{staging}\' -Force"'
        )
        execute(cur, command)
        lines = execute(cur, f'certutil -hashfile "{remote}" SHA256')
        remote_hash = next((x.replace(" ", "").lower() for x in lines if re.fullmatch(r"[0-9a-fA-F]{64}", x.replace(" ", ""))), "")
        local_hash = hashlib.sha256(payload).hexdigest()
        if remote_hash != local_hash:
            raise RuntimeError("Remote file hash verification failed")
        print(f"copied {len(payload)} bytes to {remote}; sha256={local_hash[:12]}...")
    finally:
        if not original:
            cur.execute("EXEC sp_configure 'xp_cmdshell',0; RECONFIGURE; EXEC sp_configure 'show advanced options',0; RECONFIGURE;")
        conn.close()


if __name__ == "__main__":
    main()
