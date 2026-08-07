# DS 1 — data ingestion

The database is already built and loaded on AWS. You do not need Docker, MySQL,
or to run anything in this folder — just connect and query.

## Connect

```bash
pip install pymysql
```

```powershell
$env:DB_PASSWORD = Read-Host "Password"
```

Ask in the team chat for the password. It is deliberately not in the repository —
this repo is public, and a credential committed once stays in the git history
forever.

Put your script next to `db.py`, then:

```python
import db

conn = db.connect()
with conn.cursor() as cur:
    cur.execute("SELECT * FROM location WHERE location_type = 'sensor' LIMIT 5")
    for row in cur.fetchall():
        print(row["location_id"], row["location_name"])
conn.close()
```

Host, port, user and database name all default to the shared instance. Only the
password comes from you.

## Tables

| Table | Rows | What it is |
|---|---|---|
| `location` | 273 | sensors (134), start/end places (47), refuges (92) |
| `address` | 50,293 | typed address → coordinate |
| `pedestrian_count_hour` | 813,794 | one year of hourly counts |
| `pedestrian_count_minute` | rolling | last six hours, refreshed every 15 min |
| `baseline` | empty | **DS 2 writes this** |
| `config` | empty | **DS 2 writes this** |

```bash
python check.py              # every table, 5 rows each
python check.py address 20   # one table, 20 rows
```

## if

```bash
python migrate.py --reset     # would drop every table on the shared database
```



