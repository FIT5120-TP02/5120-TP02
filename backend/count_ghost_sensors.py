"""
统计全部 sensor 里，"幽灵传感器"（从没进过 baseline / 从没进过实时读数）
的规模，评估 score_route() 的一票否决规则会波及多大范围。

用法（在 backend 目录下）：
    DB_PASSWORD=你的密码 python count_ghost_sensors.py
"""
import os

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

with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) AS n FROM location WHERE location_type='sensor'")
    total = cur.fetchone()["n"]
    print(f"sensor 总数: {total}")

    # 从没进过 pedestrian_count_minute 的 sensor
    cur.execute("""
        SELECT l.location_id, l.location_name, l.placement
        FROM location l
        WHERE l.location_type = 'sensor'
        AND NOT EXISTS (
            SELECT 1 FROM pedestrian_count_minute p
            WHERE p.location_id = l.location_id
        )
    """)
    no_minute = cur.fetchall()
    print(f"\n从没进过 pedestrian_count_minute(实时) 的 sensor 数: {len(no_minute)}")

    # 从没进过 pedestrian_count_hour 的 sensor
    cur.execute("""
        SELECT l.location_id
        FROM location l
        WHERE l.location_type = 'sensor'
        AND NOT EXISTS (
            SELECT 1 FROM pedestrian_count_hour p
            WHERE p.location_id = l.location_id
        )
    """)
    no_hour = cur.fetchall()
    print(f"从没进过 pedestrian_count_hour(历史) 的 sensor 数: {len(no_hour)}")

    # 从没进过 baseline 的 sensor（这是 score_route 真正卡住的关键表）
    cur.execute("""
        SELECT l.location_id, l.location_name, l.placement
        FROM location l
        WHERE l.location_type = 'sensor'
        AND NOT EXISTS (
            SELECT 1 FROM baseline b
            WHERE b.location_id = l.location_id
        )
    """)
    no_baseline = cur.fetchall()
    print(f"从没进过 baseline 的 sensor 数: {len(no_baseline)}")

    # indoor vs outdoor 拆分，看是否集中在室内点位
    indoor = sum(1 for r in no_baseline if r["placement"] == "Indoor")
    outdoor = sum(1 for r in no_baseline if r["placement"] == "Outdoor")
    other = len(no_baseline) - indoor - outdoor
    print(f"  其中 Indoor={indoor}, Outdoor={outdoor}, 其他/未知={other}")

    print("\n幽灵传感器清单 (location_id, name, placement):")
    for r in no_baseline:
        print(f"  {r['location_id']:>4}  {r['location_name']}  ({r['placement']})")

conn.close()

print(f"\n结论提示：")
print(f"- 幽灵传感器占比: {len(no_baseline)}/{total} = {len(no_baseline)/total*100:.1f}%")
print("- 占比越高，说明 score_route 的一票否决规则波及范围越大，越值得优先修")
print("- 如果集中在 Indoor -> 大概率是 Melbourne 开放数据里室内点位普遍缺计数数据")
