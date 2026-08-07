"""Create the database tables.

    python init_db.py           create tables
    python init_db.py --reset   drop everything first, then create
"""

import sys

import pymysql

# Local Docker MySQL. Port 3307 avoids the 13306 used by the demo3 project.
DB = dict(
    host="127.0.0.1", port=3307, user="root", password="devpassword",
    database="onboarding", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

# Dropped in reverse dependency order: a table pointed at by a foreign key
# has to go last.
TABLES = ["job_run", "config", "baseline",
          "pedestrian_count_minute", "pedestrian_count_hour", "location"]

conn = pymysql.connect(**DB)
with conn.cursor() as cur:
    if "--reset" in sys.argv:
        for table in TABLES:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            print("dropped", table)

    # pymysql runs one statement per execute, so split the file on semicolons.
    for statement in open("schema.sql", encoding="utf-8").read().split(";"):
        if statement.strip():
            cur.execute(statement)

    cur.execute("SHOW TABLES")
    created = [list(row.values())[0] for row in cur.fetchall()]

conn.commit()
conn.close()
print(f"\n{len(created)} tables created: {created}")
