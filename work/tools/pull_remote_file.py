"""Copy one production text file through the existing SQL administration channel.

The database password is read from KAIQIU_DB_PASSWORD and is never printed.
xp_cmdshell is restored to its original state before exit.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-deps"))
import pymssql


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("remote")
    parser.add_argument("local", type=Path)
    args = parser.parse_args()

    conn = pymssql.connect(
        server="139.155.99.55",
        user="lixiang",
        password=os.environ["KAIQIU_DB_PASSWORD"],
        database="master",
        as_dict=True,
        charset="UTF-8",
        autocommit=True,
        login_timeout=10,
        timeout=90,
    )
    cur = conn.cursor(as_dict=True)
    cur.execute(
        "SELECT CAST(value_in_use AS int) enabled "
        "FROM sys.configurations WHERE name='xp_cmdshell'"
    )
    original = int(cur.fetchone()["enabled"])
    try:
        if not original:
            cur.execute(
                "EXEC sp_configure 'show advanced options',1; RECONFIGURE; "
                "EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;"
            )
        remote = args.remote.replace("'", "''")
        command = (
            "powershell -NoProfile -NonInteractive -Command "
            f'"$b=[IO.File]::ReadAllBytes(\'{remote}\'); '
            "[Console]::Out.Write([Convert]::ToBase64String($b))\""
        )
        cur.execute("EXEC master..xp_cmdshell %s", (command,))
        chunks = [str(row["output"]) for row in cur.fetchall() if row["output"]]
        encoded = "".join(chunks).strip()
        payload = base64.b64decode(encoded, validate=True)
        args.local.parent.mkdir(parents=True, exist_ok=True)
        args.local.write_bytes(payload)
        print(f"copied {len(payload)} bytes to {args.local}")
    finally:
        if not original:
            cur.execute(
                "EXEC sp_configure 'xp_cmdshell',0; RECONFIGURE; "
                "EXEC sp_configure 'show advanced options',0; RECONFIGURE;"
            )
        conn.close()


if __name__ == "__main__":
    main()
