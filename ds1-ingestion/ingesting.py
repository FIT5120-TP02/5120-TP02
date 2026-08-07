
import csv
import datetime
import io
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter

import pymysql

import db


Sensor_location_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-sensor-locations/records"
Landmark_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/landmarks-and-places-of-interest-including-schools-theatres-health-services-spor/records"
Hourly_csv_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-monthly-counts-per-hour/exports/csv"
Minute_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-past-hour-counts-per-minute/records"
Address_csv_url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/street-addresses/exports/csv"

# The records API refuses limit > 100 and offset >= 10000.
PAGE = 100
MAX_OFFSET = 9900

BATCH = 5000

LANDMARK_ID_BASE = 100000


refuge_place = {
    "Informal Outdoor Facility (Park/Garden/Reserve)": "Park",
    "Outdoor Recreation Facility (Zoo, Golf Course)": "Park",
    "Library": "Library",
    "Art Gallery/Museum": "Gallery or museum",
    "Church": "Quiet place of worship",
    "Synagogue": "Quiet place of worship",
}

# the rectangular box around the Melbourne CBD, used to filter out addresses outside it
melbourne_cbd_area = dict(lat_min=-37.829, lat_max=-37.786, lon_min=144.926, lon_max=144.989)


# define a function to check if a given latitude and longitude are within the Melbourne CBD area
def in_cbd(lat, lon):
    b = melbourne_cbd_area
    return (lat is not None and lon is not None
            and b["lat_min"] <= lat <= b["lat_max"]
            and b["lon_min"] <= lon <= b["lon_max"])


# Landmarks a person actually names as the start or end of a walk. Deliberately
# narrow: a dropdown of 35 places is usable, one of 199 is not.
PLACE_SUB_THEMES = {
    "Railway Station",
    "Tertiary (University)",
    "Function/Conference/Exhibition Centre",
    "Major Sports & Recreation Facility",
    "Department Store",
}

# SQL statement to upsert location data
UPSERT_LOCATION = (
    "INSERT INTO location "
    "(location_id, location_name, latitude, longitude, "
    " address, location_type, category, placement) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE "
    "  location_name = VALUES(location_name), "
    "  latitude      = VALUES(latitude), "
    "  longitude     = VALUES(longitude), "
    "  location_type = VALUES(location_type), "
    "  category      = VALUES(category), "
    "  placement     = VALUES(placement)"
)


# ───────────────────────────── helpers ─────────────────────────────

def fetch_all(url):
    """Every record of a small dataset. The API caps a page at 100, so keep
    asking for the next 100 until a short page says that was the last of them."""
    records = []
    while True:
        params = {"limit": PAGE, "offset": len(records)}
        full_url = url + "?" + urllib.parse.urlencode(params)

        with urllib.request.urlopen(full_url, timeout=60) as response:
            body = response.read().decode("utf-8")
        page = json.loads(body)["results"]

        records = records + page

        if len(page) < PAGE:
            return records          # a short page is the last page
        if len(records) >= MAX_OFFSET:
            return records          # the API refuses to look past offset 10000


def write_batches(conn, sql, rows):
    """Send rows to MySQL a few thousand at a time. One executemany holding a
    million tuples builds a single enormous query and runs out of memory."""
    with conn.cursor() as cur:
        start = 0
        while start < len(rows):
            batch = rows[start:start + BATCH]
            cur.executemany(sql, batch)
            start = start + BATCH
    conn.commit()


def sensor_ids(conn):
    """The location_ids we actually measure. Counts for anything else get dropped."""
    with conn.cursor() as cur:
        cur.execute("SELECT location_id FROM location WHERE location_type = 'sensor'")
        found_rows = cur.fetchall()

    ids = set()
    for row in found_rows:
        ids.add(row["location_id"])
    return ids


# low frequency data
# ingesting location, sensor,lat,lon,landmark,place data into location table

def load_sensors(conn):
    """Sensor locations -> location table."""
    records = fetch_all(Sensor_location_url)

    rows = [(
        record["location_id"],
        record["sensor_description"],
        record["latitude"],
        record["longitude"],
        None,                          # address: the feed has none
        "sensor",
        None,                          # category: only refuges have one
        record.get("location_type"),   # 'Outdoor' / 'Indoor' -> our `placement`
    ) for record in records]

    write_batches(conn, UPSERT_LOCATION, rows)

    outdoor = sum(1 for row in rows if row[7] == "Outdoor")
    return {
        "rows_in": len(records),
        "rows_written": len(rows),
        "rows_rejected": 0,
        "message": f"{len(rows)} sensors synced ({outdoor} outdoor, {len(rows) - outdoor} indoor)",
    }



# identify landmark to place and refuge, ingesting into location table, by the set up REFUGE_CATEGORIES
def load_landmarks(conn):
    records = fetch_all(Landmark_url)

    kept, skipped = [], 0
    for record in records:
        point = record.get("co_ordinates")
        sub_theme = record.get("sub_theme")

        if not point or point.get("lat") is None or point.get("lon") is None:
            skipped += 1
            continue

        if sub_theme in refuge_place:
            location_type, category = "refuge", refuge_place[sub_theme]
        elif sub_theme in PLACE_SUB_THEMES:
            location_type, category = "place", None
        else:
            skipped += 1        # a car park, a construction site, an office
            continue

        kept.append((record["feature_name"], point["lat"], point["lon"],
                     location_type, category))

    # Sorted so the same feed always hands out the same ids, which makes a
    # re-sync boring to read in the database.
    kept.sort()

    rows = [(
        LANDMARK_ID_BASE + index,
        name,
        lat,
        lon,
        None,                 # address: the feed has none
        location_type,
        category,
        None,                 # placement: only sensors are indoor or outdoor
    ) for index, (name, lat, lon, location_type, category) in enumerate(kept)]

    with conn.cursor() as cur:
        cur.execute("DELETE FROM location WHERE location_type IN ('place', 'refuge')")
    write_batches(conn, UPSERT_LOCATION, rows)

    places = sum(1 for row in rows if row[5] == "place")
    return {
        "rows_in": len(records),
        "rows_written": len(rows),
        "rows_rejected": skipped,
        "message": (f"{places} places and {len(rows) - places} refuges kept; "
                    f"{skipped} landmarks are neither"),
    }


# turning a typed address into a coordinate: the address table is the lookup
# behind the search box on the front end

def load_addresses(conn):
    """Street addresses -> address table.

    The CSV export, not the paged records API: 63,721 rows is well past the
    offset 10000 the paged endpoint refuses to go beyond.

    The whole City of Melbourne, not just the CBD - somebody's home address is
    as likely to be in Carlton or Kensington as on Collins Street.
    """
    query = urllib.parse.urlencode({
        "select": "gisid,address_pnt,street_no,str_name,suburb,latitude,longitude",
        "limit": -1,
    })

    rows, rows_in, skipped = [], 0, 0
    with urllib.request.urlopen(f"{Address_csv_url}?{query}", timeout=300) as response:
        text = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        header = text.readline().rstrip("\r\n")
        delimiter = ";" if ";" in header else ","
        reader = csv.DictReader(text, fieldnames=header.split(delimiter), delimiter=delimiter)

        for record in reader:
            rows_in += 1
            # This feed sends the coordinates as text, unlike every other one we
            # read. Left as text they would go into a DOUBLE column as a string
            # conversion MySQL performs quietly and not always the way you want.
            if not record["latitude"] or not record["longitude"]:
                skipped += 1
                continue

            latitude, longitude = float(record["latitude"]), float(record["longitude"])
            if not in_cbd(latitude, longitude):
                skipped += 1
                continue

            rows.append((
                int(record["gisid"]),
                record["address_pnt"],
                record["street_no"],
                record["str_name"],
                record["suburb"],
                latitude,
                longitude,
            ))

    write_batches(
        conn,
        "INSERT INTO address "
        "(address_id, address_pnt, street_no, str_name, suburb, latitude, longitude) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "  address_pnt = VALUES(address_pnt), "
        "  street_no   = VALUES(street_no), "
        "  str_name    = VALUES(str_name), "
        "  suburb      = VALUES(suburb), "
        "  latitude    = VALUES(latitude), "
        "  longitude   = VALUES(longitude)",
        rows,
    )

    suburbs = len({row[4] for row in rows})
    return {
        "rows_in": rows_in,
        "rows_written": len(rows),
        "rows_rejected": skipped,
        "message": (f"{len(rows)} addresses inside the CBD box across {suburbs} suburbs; "
                    f"{skipped} outside it or missing coordinates"),
    }


# daily batch job of hourly counts

def load_hours(conn, weeks=52):
    """Historical hourly counts -> pedestrian_count_hour.

    Uses the bulk CSV export rather than the paged records API: a year is
    hundreds of thousands of rows, and the paged endpoint would need thousands
    of round trips and refuses to page past offset 10000 anyway.
    """
    since = (datetime.date.today() - datetime.timedelta(weeks=weeks)).isoformat()
    query = urllib.parse.urlencode({
        "select": "id,location_id,sensing_date,hourday,direction_1,direction_2,pedestriancount",
        "where": f"sensing_date >= date'{since}'",
        "limit": -1,
    })

    known = sensor_ids(conn)
    seen, duplicates = set(), Counter()
    rows, rows_in, outside = [], 0, 0

    with urllib.request.urlopen(f"{Hourly_csv_url}?{query}", timeout=600) as response:
        text = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        header = text.readline().rstrip("\r\n")
        delimiter = ";" if ";" in header else ","
        reader = csv.DictReader(text, fieldnames=header.split(delimiter), delimiter=delimiter)

        for record in reader:
            rows_in += 1
            location_id = int(record["location_id"])
            if location_id not in known:
                outside += 1              # a sensor outside the set we hold
                continue

            day = record["sensing_date"][:10]
            hourday = int(record["hourday"])

            key = (location_id, day, hourday)
            if key in seen:
                duplicates[location_id] += 1
                continue
            seen.add(key)

            # append a tuple of values to insert into pedestrian_count_hour
            rows.append((
                int(record["id"]),
                location_id,
                day,
                datetime.date.fromisoformat(day).weekday(),
                hourday,
                int(record["direction_1"] or 0),
                int(record["direction_2"] or 0),
                int(record["pedestriancount"] or 0),
            ))

    # Write the rows in batches, so no single query has to hold them all
    write_batches(
        conn,
        "INSERT INTO pedestrian_count_hour "
        "(id, location_id, sensing_date, day_of_week, hourday, "
        " direction_1, direction_2, pedestrian_count) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE pedestrian_count = VALUES(pedestrian_count)",
        rows,
    )

    worst = ", ".join(f"sensor {loc} x{n}" for loc, n in duplicates.most_common(5)) or "none"
    return {
        "rows_in": rows_in,
        "rows_written": len(rows),
        "rows_rejected": sum(duplicates.values()),
        "message": (f"{len(rows)} hourly rows since {since}; "
                    f"{sum(duplicates.values())} repeated sensor-date-hour rows "
                    f"(worst: {worst}); {outside} rows from sensors we do not hold"),
    }


# the current reading of the last hour, polled every 15 minutes

def poll_minutes(conn, keep_minutes=360):
    """Newest per-minute readings -> pedestrian_count_minute.

    Stops as soon as it reaches readings we already hold, so a routine poll costs
    one page instead of the two thousand the whole rolling window would need.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(sensing_datetime) AS newest FROM pedestrian_count_minute")
        stored_newest = cur.fetchone()["newest"]
    known = sensor_ids(conn)

    rows, rows_in, outside, pages = [], 0, 0, 0
    done = False
    while not done and pages * PAGE < MAX_OFFSET:
        query = urllib.parse.urlencode({
            "limit": PAGE,
            "offset": pages * PAGE,
            "order_by": "sensing_datetime desc",      # newest first
        })
        with urllib.request.urlopen(f"{Minute_url}?{query}", timeout=60) as response:
            page = json.loads(response.read().decode("utf-8"))["results"]
        pages += 1
        if not page:
            break

        for record in page:
            rows_in += 1
            stamp = record["sensing_datetime"][:19].replace("T", " ")

            if stored_newest and datetime.datetime.fromisoformat(stamp) < stored_newest:
                done = True
                break

            if record["location_id"] not in known:
                outside += 1
                continue

            
            rows.append((
                record["location_id"],
                stamp,
                record["sensing_date"],
                record["sensing_time"],
                record["direction_1"],
                record["direction_2"],
                record["total_of_directions"],
            ))

        if len(page) < PAGE:
            break

    write_batches(
        conn,
        "INSERT INTO pedestrian_count_minute "
        "(location_id, sensing_datetime, sensing_date, sensing_time, "
        " direction_1, direction_2, total_of_directions) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE total_of_directions = VALUES(total_of_directions)",
        rows,
    )

    with conn.cursor() as cur:
        cur.execute("SELECT MAX(sensing_datetime) AS newest FROM pedestrian_count_minute")
        newest = cur.fetchone()["newest"]
        deleted = 0
        if newest:
            horizon = newest - datetime.timedelta(minutes=keep_minutes)
            deleted = cur.execute(
                "DELETE FROM pedestrian_count_minute WHERE sensing_datetime < %s", (horizon,))
    conn.commit()

    return {
        "rows_in": rows_in,
        "rows_written": len(rows),
        "rows_rejected": outside,
        "message": (f"{len(rows)} readings over {pages} page(s); "
                    f"{outside} from sensors we do not hold; {deleted} rows aged out"),
    }


# run all jobs, printing the result of each
JOBS = {
    "sensors": load_sensors,
    "landmarks": load_landmarks,
    "addresses": load_addresses,
    "hours": load_hours,
    "minutes": poll_minutes,
}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(JOBS)
    unknown = [name for name in wanted if name not in JOBS]
    if unknown:
        sys.exit(f"unknown job {unknown}; pick from {list(JOBS)}")

    conn = db.connect()
    for name in wanted:
        print(f"--- {name}")
        print(json.dumps(JOBS[name](conn), indent=2))
    conn.close()
