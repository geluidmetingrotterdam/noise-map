import os
import time
import pytz
import requests
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from http.client import IncompleteRead

# === Config ===
INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "sensor_data")

env_sensors = os.environ.get("SENSOR_IDS")
SENSOR_IDS = [int(s) for s in env_sensors.split(",")] if env_sensors else [
    13492675, 4697349, 13485578, 6365646, 13486994, 13490756,
    7974125, 6564283, 7366586, 1165775, 4498201, 13491599,
    15180296, 13491199, 13485069, 8292136, 13487297, 13492648,
    13485694, 976045, 7874199, 6563185, 13487070, 13491187,
    13492369, 13261816, 15188288, 7811716, 13491144, 13491372,
    94695, 94686, 94687, 94448, 94688, 94449, 94689, 94693,
    94284, 94696, 94735, 94701, 94447, 94692, 89747
]

BASE_URL = "https://archive.sensor.community"
CET = pytz.timezone("Europe/Amsterdam")

today = datetime.now(tz=CET).date()
yesterday = today - timedelta(days=1)
DAYS = [yesterday.isoformat()]

print(f"🕓 Backfilling for day(s): {DAYS}", flush=True)

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Setup session with retry logic
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("http://", adapter)
session.mount("https://", adapter)

successful_fetches = 0

def fetch_and_push(sensor_id: int, day: str) -> bool:
    url = f"{BASE_URL}/{day}/{day}_laerm_sensor_{sensor_id}.csv"
    try:
        print(f"🔄 Fetching: {url}", flush=True)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except IncompleteRead as e:
            print(f"💥 Incomplete read for sensor {sensor_id} on {day}: {e}", flush=True)
            return False

        lines = resp.text.strip().split("\n")
        if not lines or len(lines) < 2:
            print(f"⚠️ No data rows found for sensor {sensor_id}.", flush=True)
            return False

        headers = lines[0].split(";")
        seen_timestamps = set()
        points_written = 0

        for line in lines[1:]:
            parts = line.split(";")
            data = dict(zip(headers, parts))

            try:
                ts_local = datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M:%S")
                ts_local = CET.localize(ts_local)
            except Exception:
                continue

            bucket_time = ts_local.replace(second=0, microsecond=0)
            if bucket_time in seen_timestamps:
                continue
            seen_timestamps.add(bucket_time)

            fields = {}
            for field in ["noise_LAeq", "noise_LA_min", "noise_LA_max"]:
                value = data.get(field)
                if value:
                    try:
                        fields[field] = float(value)
                    except ValueError:
                        continue

            if not fields:
                continue

            point = Point("noise").tag("sensor_id", str(sensor_id))
            for key, val in fields.items():
                point = point.field(key, val)
            point = point.time(bucket_time.astimezone(pytz.UTC), WritePrecision.S)

            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            points_written += 1

        if points_written > 0:
            print(f"✅ Sensor {sensor_id} on {day}: {points_written} points written.", flush=True)
            return True
        else:
            print(f"⚠️ No valid data for sensor {sensor_id} on {day}.", flush=True)
            return False

    except Exception as e:
        print(f"💥 Error for sensor {sensor_id} on {day}: {e}", flush=True)
        return False

# Main loop
for sensor in SENSOR_IDS:
    for day in DAYS:
        if fetch_and_push(sensor, day):
            successful_fetches += 1
        time.sleep(1)

client.close()

if successful_fetches == 0:
    print("❌ No data fetched from any sensor — archive may not be ready.", flush=True)
    exit(1)

print(f"🎉 Backfill complete: {successful_fetches} sensors processed.", flush=True)
