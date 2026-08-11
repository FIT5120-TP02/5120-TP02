"""
确认 "Indoor 传感器 = 永远没数据" 这个规律是否100%成立。

用法（在 backend 目录下）：
    DB_PASSWORD=你的密码 python check_indoor_pattern.py
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
    cur.execute("""
        SELECT placement, COUNT(*) AS n
        FROM location
        WHERE location_type='sensor'
        GROUP BY placement
    """)
    print("sensor 按 placement 分组总数:", cur.fetchall())

    cur.execute("""
        SELECT l.placement, COUNT(*) AS n
        FROM location l
        WHERE l.location_type = 'sensor'
        AND NOT EXISTS (SELECT 1 FROM baseline b WHERE b.location_id = l.location_id)
        GROUP BY l.placement
    """)
    print("其中没有 baseline 的，按 placement 分组:", cur.fetchall())

    # 反过来看：有没有 Indoor 但其实有 baseline 数据的
    cur.execute("""
        SELECT l.location_id, l.location_name
        FROM location l
        WHERE l.location_type = 'sensor' AND l.placement = 'Indoor'
        AND EXISTS (SELECT 1 FROM baseline b WHERE b.location_id = l.location_id)
    """)
    indoor_with_data = cur.fetchall()
    print(f"\nIndoor 但其实有 baseline 数据的 sensor: {indoor_with_data}")

    # 反过来看：有没有 Outdoor 但其实没有 baseline 数据的
    cur.execute("""
        SELECT l.location_id, l.location_name
        FROM location l
        WHERE l.location_type = 'sensor' AND l.placement = 'Outdoor'
        AND NOT EXISTS (SELECT 1 FROM baseline b WHERE b.location_id = l.location_id)
    """)
    outdoor_without_data = cur.fetchall()
    print(f"Outdoor 但其实没有 baseline 数据的 sensor: {outdoor_without_data}")

conn.close()

print()
if not indoor_with_data and not outdoor_without_data:
    print("结论: 100%成立 -> Indoor 全部没数据, Outdoor 全部有数据. "
          "用 placement='Outdoor' 过滤是安全、干净的修复方式。")
else:
    print("结论: 规律不是100%成立，不能简单按 placement 过滤，"
          "需要按 location_id 精确排除幽灵传感器，或换别的判断依据。")
