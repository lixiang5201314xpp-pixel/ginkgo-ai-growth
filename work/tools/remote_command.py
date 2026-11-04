"""Run one non-secret administrative diagnostic command on the production host."""
from pathlib import Path
import os
import sys
sys.stdout.reconfigure(encoding='utf-8',errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-deps"))
import pymssql


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: remote_command.py COMMAND")
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
        cur.execute("EXEC master..xp_cmdshell %s", (sys.argv[1],))
        for row in cur.fetchall():
            if row["output"] is not None:
                print(row["output"])
    finally:
        if not original:
            cur.execute("EXEC sp_configure 'xp_cmdshell',0; RECONFIGURE; EXEC sp_configure 'show advanced options',0; RECONFIGURE;")
        conn.close()


if __name__ == "__main__":
    main()
