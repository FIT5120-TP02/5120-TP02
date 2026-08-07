
import pathlib
import re
import sys

import pymysql

import db

MIGRATIONS = pathlib.Path(__file__).parent / "migrations"


def applied_versions(cur):
    """Which migrations this database has already run."""
    cur.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  version INT PRIMARY KEY,"
        "  filename VARCHAR(255) NOT NULL,"
        "  applied_at DATETIME NOT NULL)"
    )
    cur.execute("SELECT version FROM schema_version")
    return {row["version"] for row in cur.fetchall()}


def files():
    """Every migration on disk, oldest first. 001_initial.sql -> (1, path)."""
    found = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        found.append((int(path.name.split("_")[0]), path))
    return found


def run_file(cur, path):
    sql = re.sub(r"(^|\s)--[^\n]*", r"\1", path.read_text(encoding="utf-8"))
    for statement in sql.split(";"):
        if statement.strip():
            cur.execute(statement)


def status(conn):
    with conn.cursor() as cur:
        done = applied_versions(cur)
    for version, path in files():
        print(f"  {'applied' if version in done else 'PENDING'}  {path.name}")


def migrate(conn, baseline=False):
    with conn.cursor() as cur:
        done = applied_versions(cur)
        pending = [(v, p) for v, p in files() if v not in done]

        if not pending:
            print("nothing to do; the database is up to date")
            return

        for version, path in pending:
            if baseline:
                print(f"marked  {path.name}  (not executed)")
            else:
                run_file(cur, path)
                print(f"applied {path.name}")
            cur.execute(
                "INSERT INTO schema_version (version, filename, applied_at) VALUES (%s, %s, NOW())",
                (version, path.name),
            )
    conn.commit()


def reset(conn):
    """Drop every table, including schema_version. Sandbox only."""
    if not db.is_local():
        sys.exit(f"refusing to --reset {db.host()}\n"
                 f"That is the shared database - dropping it stops five other people.\n"
                 f"Point DB_HOST at a local sandbox if you really mean to wipe one.")

    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = [list(row.values())[0] for row in cur.fetchall()]
        if not tables:
            print("nothing to drop")
            return

        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in tables:
            cur.execute(f"DROP TABLE `{table}`")
            print("dropped", table)
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()


if __name__ == "__main__":
    # Checked before connecting, so the refusal arrives even when the password
    # is missing - the point is to stop the command, not to reach the database.
    if "--reset" in sys.argv and not db.is_local():
        sys.exit(f"refusing to --reset {db.host()}\n"
                 f"That is the shared database - dropping it stops five other people.\n"
                 f"Point DB_HOST at a local sandbox if you really mean to wipe one.")

    conn = db.connect()
    if "--status" in sys.argv:
        status(conn)
    elif "--reset" in sys.argv:
        reset(conn)
    else:
        migrate(conn, baseline="--baseline" in sys.argv)
    conn.close()
