"""
诊断脚本：定位 /api/routes/compare 返回 sensory_status="NO DATA" 的原因。

用法（在 backend 目录下，激活 .venv 后）：
    python ../diagnose_no_data.py

需要环境变量 DB_PASSWORD（同 .env 里的密码）。
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pymysql
from dotenv import dotenv_values

cfg = dotenv_values(".env")
password = os.environ.get("DB_PASSWORD") or cfg.get("DB_PASSWORD")

conn = pymysql.connect(
    host=cfg.get("DB_HOST"),
    port=int(cfg.get("DB_PORT", 3306)),
    user=cfg.get("DB_USER"),
    password=password,
    database=cfg.get("DB_NAME"),
    cursorclass=pymysql.cursors.DictCursor,
)

MELBOURNE = ZoneInfo("Australia/Melbourne")
now = datetime.now(timezone.utc)
now_mel = now.astimezone(MELBOURNE)
weekday, hour = now_mel.weekday(), now_mel.hour

print(f"当前 UTC 时间: {now}")
print(f"当前 Melbourne 时间: {now_mel} -> day_of_week={weekday}, hourday={hour}")
print()

with conn.cursor() as cur:
    # 0. config 表里实际生效的 live_max_age_minutes（DB 覆盖值，优先于代码默认值30）
    cur.execute("SELECT config_key, value FROM config")
    config_rows = cur.fetchall()
    config_map = {row["config_key"]: row["value"] for row in config_rows}
    print("0) config 表全部内容:", config_map)
    effective_max_age = int(config_map.get("live_max_age_minutes", 30))
    print(f"   -> 实际生效的 live_max_age_minutes = {effective_max_age} "
          f"({'来自 config 表' if 'live_max_age_minutes' in config_map else '代码默认值,config表里没有这个key'})")
    print()

    # 1. sensor 数量
    cur.execute("SELECT COUNT(*) AS n FROM location WHERE location_type='sensor'")
    print("1) sensor 总数:", cur.fetchone()["n"])

    # 2. 最新一条 pedestrian_count_minute 的时间，判断是否 stale
    cur.execute("SELECT MAX(sensing_datetime) AS latest FROM pedestrian_count_minute")
    latest = cur.fetchone()["latest"]
    print("2) pedestrian_count_minute 最新记录时间:", latest)
    if latest:
        age_min = (now.replace(tzinfo=None) - latest).total_seconds() / 60
        stale = age_min > effective_max_age
        print(f"   距现在 {age_min:.1f} 分钟 (阈值 {effective_max_age} 分钟) -> "
              f"{'STALE, 会判 NO DATA' if stale else 'OK, 未超过阈值'}")

    # 3. 当前时段有没有 baseline
    cur.execute(
        "SELECT COUNT(*) AS n FROM baseline WHERE day_of_week=%s AND hourday=%s",
        (weekday, hour),
    )
    print(f"3) 当前时段 (day_of_week={weekday}, hourday={hour}) 的 baseline 行数:", cur.fetchone()["n"])

    # 4. observation_count 是否都 >= minimum_observations(默认10)
    cur.execute(
        "SELECT COUNT(*) AS n FROM baseline WHERE day_of_week=%s AND hourday=%s AND observation_count < 10",
        (weekday, hour),
    )
    print("4) 当前时段 observation_count < 10 的行数 (会被判为 NO DATA):", cur.fetchone()["n"])

conn.close()
print()
print("排查结论提示：")
print("- 如果 0) 里没有 live_max_age_minutes 这个 key，或者值不是120 -> 你改的那次没有真正写进这张 config 表")
print("  （比如改在了 ds3-sensory-scoring/sensory_scoring.py 或 backend/app/services/sensory_scoring.py 的代码默认值里，")
print("   但 config 表里已经有一行 live_max_age_minutes，DB 里的值会覆盖代码默认值，等于白改）")
print("- 如果 2) 显示 STALE -> 距现在的时间超过了实际生效的阈值，检查 GitHub Actions 轮询有没有按时跑")
print("- 如果 3) 为 0 -> DS2 还没为当前 day_of_week/hourday 生成 baseline")
print("- 如果 4) 数量较多 -> baseline 观测样本不足，也会被判 NO DATA")
