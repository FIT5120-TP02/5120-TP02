"""
逐条追踪某条具体路线为什么被判 NO DATA。

复用真实的 app 代码（sensor 匹配、读数、baseline、score_route），
在每一步打印中间结果，而不是只看聚合统计。

用法（在 backend 目录下，激活 .venv 后）：
    DB_PASSWORD=你的密码 python trace_no_data.py \
        --origin-lat -37.8183 --origin-lng 144.9671 \
        --dest-lat -37.8098 --dest-lng 144.9654
"""
import argparse
from datetime import datetime, timezone

from app.database import SessionLocal
from app.services import routing_service, sensory_scoring
from app.services.scoring_config import load_scoring_config
from app.services.sensory_scoring import match_sensors_to_route, melbourne_baseline_slot
from app.routers.routes import _sensor_locations, _latest_readings, _baselines_for_slot

parser = argparse.ArgumentParser()
parser.add_argument("--origin-lat", type=float, required=True)
parser.add_argument("--origin-lng", type=float, required=True)
parser.add_argument("--dest-lat", type=float, required=True)
parser.add_argument("--dest-lng", type=float, required=True)
args = parser.parse_args()

db = SessionLocal()

candidates = routing_service.get_candidate_routes(
    args.origin_lat, args.origin_lng, args.dest_lat, args.dest_lng
)
print(f"拿到 {len(candidates)} 条候选路线\n")

cfg = load_scoring_config(db)
print("生效的 ScoringConfig:", cfg, "\n")

now = datetime.now(timezone.utc)
day_of_week, hourday = melbourne_baseline_slot(now)
print(f"当前 baseline 时段: day_of_week={day_of_week}, hourday={hourday}\n")

sensors = _sensor_locations(db)
print(f"全部 sensor 数量: {len(sensors)}\n")

for candidate in candidates:
    print(f"=== {candidate.label} ({candidate.route_id}) ===")
    matched_ids = match_sensors_to_route(candidate.geometry, sensors, cfg.buffer_radius_m)
    print(f"buffer_radius_m={cfg.buffer_radius_m} 内匹配到 {len(matched_ids)} 个 sensor: {matched_ids}")

    if len(matched_ids) < cfg.minimum_sensors:
        print(f"-> 匹配到的 sensor 数 < minimum_sensors({cfg.minimum_sensors})，直接 NO DATA\n")
        continue

    matched_location_ids = [int(sid) for sid in matched_ids]
    readings = _latest_readings(db, matched_location_ids)
    baselines = _baselines_for_slot(db, matched_location_ids, day_of_week, hourday)

    for sid in matched_ids:
        reading = readings.get(sid)
        baseline = baselines.get(sid)
        problems = []
        if reading is None:
            problems.append("没有最新读数(readings里查不到)")
        if baseline is None:
            problems.append(f"没有当前时段(day={day_of_week},hour={hourday})的baseline")
        if reading and reading.current_count < 0:
            problems.append("读数是负数")
        if baseline and baseline.median_count <= 0:
            problems.append("baseline median_count <= 0")
        if baseline and baseline.observation_count < cfg.minimum_observations:
            problems.append(f"baseline observation_count({baseline.observation_count}) < minimum_observations({cfg.minimum_observations})")
        if reading and sensory_scoring._is_stale(reading.observed_at, now, cfg.live_max_age_minutes):
            age = (now.replace(tzinfo=None) - reading.observed_at.replace(tzinfo=None)).total_seconds() / 60
            problems.append(f"读数 stale，距现在 {age:.1f} 分钟 > 阈值 {cfg.live_max_age_minutes} 分钟")

        status = "OK" if not problems else "PROBLEM: " + "; ".join(problems)
        print(f"  sensor {sid}: reading={reading}, baseline={baseline} -> {status}")

    status, notification = sensory_scoring.score_route(matched_ids, readings, baselines, cfg, now)
    print(f"-> 最终 sensory_status = {status}\n")

db.close()
