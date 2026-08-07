# look at what is in the database
#
#     python check.py              every table, 5 rows each
#     python check.py address      one table only
#     python check.py address 20   one table, 20 rows

import sys

import pymysql

from ingesting import DB

conn = pymysql.connect(**DB)
with conn.cursor() as cur:
    cur.execute("SHOW TABLES")
    tables = [list(row.values())[0] for row in cur.fetchall()]

    wanted = [sys.argv[1]] if len(sys.argv) > 1 else tables
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    for table in wanted:
        if table not in tables:
            print(f"no table called {table}; pick from {tables}")
            continue

        cur.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
        total = cur.fetchone()["n"]
        print(f"\n{'=' * 78}\n{table}   {total:,} rows\n{'=' * 78}")

        if total == 0:
            print("  (empty)")
            continue

        cur.execute(f"SELECT * FROM `{table}` LIMIT {limit}")
        rows = cur.fetchall()

        # Widths sized to the longest value actually printed, so the columns
        # line up without a table library.
        columns = list(rows[0])
        width = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in columns}
        print("  " + "  ".join(c.ljust(width[c]) for c in columns))
        print("  " + "  ".join("-" * width[c] for c in columns))
        for row in rows:
            print("  " + "  ".join(str(row[c]).ljust(width[c]) for c in columns))

conn.close()
