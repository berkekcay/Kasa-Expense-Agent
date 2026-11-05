"""Run Kasa on the SQL Server on this computer (LocalDB, Express or Developer). From backend/:

    python -m scripts.local_sqlserver                          # (localdb)\\MSSQLLocalDB
    python -m scripts.local_sqlserver --server "localhost\\SQLEXPRESS"

Same layout as production (deploy/digitalocean/sql): a `kasa` database, a `kasa_app` login
that can only read and write rows, migrations run as you (Windows authentication, so you
need to be an admin of that server), then `kasa_app` may not touch alembic_version. Every
query of the app passes the row-level security policy.

It only creates the `kasa` database and the `kasa_app` login; other databases on the server
are not touched. The kasa_app password is generated once and kept in .env (gitignored).
.env gets DATABASE_URL (kasa_app), MIGRATION_DATABASE_URL (you) and AUTO_MIGRATE=false; the
old SQLite URL stays as a comment. Run it again after pulling new migrations.

Needs `pip install -r requirements-mssql.txt` and Microsoft ODBC Driver 18 for SQL Server.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

ENV = Path(".env")
SQL_DIR = Path(__file__).resolve().parents[2] / "deploy" / "digitalocean" / "sql"
DRIVER = "ODBC Driver 18 for SQL Server"


def odbc_url(server: str, extra: str, database: str = "kasa") -> str:
    raw = f"DRIVER={{{DRIVER}}};SERVER={server};DATABASE={database};Encrypt=no;{extra}"
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(raw)


def run_batches(server: str, path: Path, variables: dict[str, str]) -> None:
    """Run a sqlcmd-style script (GO separators, $(VAR) variables) as the Windows user."""
    import pyodbc

    text = path.read_text(encoding="utf-8")
    for name, value in variables.items():
        text = text.replace(f"$({name})", value.replace("'", "''"))
    conn = pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;Encrypt=no",
        autocommit=True,
    )
    try:
        for batch in re.split(r"^\s*GO\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
            if batch.strip():
                conn.execute(batch)
    finally:
        conn.close()


def read_env() -> dict[str, str]:
    if not ENV.exists():
        return {}
    pairs = (line.split("=", 1) for line in ENV.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {k.strip(): v.strip() for k, v in pairs if not k.lstrip().startswith("#")}


def write_env(values: dict[str, str]) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key == "DATABASE_URL" and line.split("=", 1)[1].startswith("sqlite"):
            out.append("# SQLite (before SQL Server): " + line)
            continue
        if key in values:
            if key not in seen:
                out.append(f"{key}={values[key]}")
                seen.add(key)
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--server", default=r"(localdb)\MSSQLLocalDB", help="SQL Server instance")
    args = parser.parse_args()
    if not ENV.exists():
        sys.exit("Run this from backend/ (where .env lives). Copy .env.example to .env first.")

    password = read_env().get("KASA_APP_PASSWORD") or "Kx9" + secrets.token_hex(16)
    print(f"1/4 Database kasa and login kasa_app on {args.server}")
    run_batches(args.server, SQL_DIR / "init.sql", {"KASA_APP_PASSWORD": password})

    admin_url = odbc_url(args.server, "Trusted_Connection=yes")
    write_env(
        {
            "DATABASE_URL": odbc_url(args.server, f"UID=kasa_app;PWD={password}"),
            "MIGRATION_DATABASE_URL": admin_url,
            "KASA_APP_PASSWORD": password,
            "AUTO_MIGRATE": "false",
        }
    )
    print("2/4 .env points at SQL Server (kasa_app); the SQLite line is kept as a comment")

    print("3/4 Migrations (alembic upgrade head, as you)")
    env = {**os.environ, "MIGRATION_DATABASE_URL": admin_url}
    done = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=False)
    if done.returncode:
        return done.returncode

    print("4/4 kasa_app may read the schema version but not change it")
    run_batches(args.server, SQL_DIR / "lockdown.sql", {})
    print("Done. Demo data: python -m scripts.seed_demo --user demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
