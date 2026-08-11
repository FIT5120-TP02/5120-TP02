"""
查 sensor 89、99 在数据库里历史上是否曾经有过任何读数/baseline。

用法（在 backend 目录下）：
    DB_PASSWORD=你的密码 python check_sensor_89_99.py
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

SENSOR_IDS = [89, 99]

with conn.cursor() as cur:
    for sid in SENSOR_IDS:
        print(f"===== sensor {sid} =====")

        cur.execute(
            "SELECT location_id, location_name, latitude, longitude, placement "
            "FROM location WHERE location_id=%s",
            (sid,),
        )
        loc = cur.fetchone()
        print("location 表记录:", loc)

        cur.execute(
            "SELECT COUNT(*) AS n, MIN(sensing_datetime) AS earliest, "
            "MAX(sensing_datetime) AS latest "
            "FROM pedestrian_count_minute WHERE location_id=%s",
            (sid,),
        )
        row = cur.fetchone()
        print(f"pedestrian_count_minute: 总行数={row['n']}, "
              f"最早={row['earliest']}, 最晚={row['latest']}")

        cur.execute(
            "SELECT COUNT(*) AS n, MIN(sensing_date) AS earliest, "
            "MAX(sensing_date) AS latest "
            "FROM pedestrian_count_hour WHERE location_id=%s",
            (sid,),
        )
        row = cur.fetchone()
        print(f"pedestrian_count_hour(历史小时数据): 总行数={row['n']}, "
              f"最早={row['earliest']}, 最晚={row['latest']}")

        cur.execute(
            "SELECT COUNT(*) AS n FROM baseline WHERE location_id=%s",
            (sid,),
        )
        row = cur.fetchone()
        print(f"baseline 表: 总行数(所有时段加起来)={row['n']}")
        print()

conn.close()
print("结论提示：")
print("- 如果三张表 count 都是 0 -> 这个 sensor 从来没上报过数据，大概率是"
      "开放数据里新加入/未激活的点位")
print("- 如果 pedestrian_count_hour 有历史数据但 pedestrian_count_minute 是0"
      " -> DS1的实时轮询(minutes job)从来没抓到过它，可能是Minute_url这个"
      "接口本身不包含它")
print("- 如果 pedestrian_count_hour 有数据但 baseline 是0"
      " -> DS2的baseline.py还没针对它跑过/算过")
