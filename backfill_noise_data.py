import os
import requests
import time
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import pytz

# === Configuration from environment variables ===
INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "sensor_data")

# List of Sensor.Community sensor IDs
env_sensors = os.environ.get("SENSOR_IDS")
if env_sensors:
    SENSOR_IDS = [int(s) for s in env_sensors.split(',')]
else:
    SENSOR_IDS = [
        13492675, 4697349, 13485578, 6365646, 13486994, 13490756,
        7974125, 6564283, 7366586, 1165775, 4498201, 13491599,
        15180296, 13491199, 13485069, 8292136, 13487297, 13492648,
        13485694, 976045, 7874199, 6563185, 13487070, 13491187,
        13492369, 13261816, 15188288, 7811716, 13491144, 13491372,
        94695, 94686, 94687, 94448, 94688, 94449, 94689, 94693,
        94284, 94696, 94735, 94701, 94447, 94692
    ]

BASE_URL = "https://archive.sensor.community"
CET = pytz.timezone("Europe/Amsterdam")

# Initialize InfluxDB client and write API
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Calculate days: last 7 full days (yesterday back to 7 days ago)
# Calculate day to update: yesterday only
today = datetime.now(tz=CET).date()
yesterday = today - timedelta(days=1)
DAYS = [yesterday.isoformat()][::-1]


def fetch_and_push(sensor_id: int, day: str):
    """Fetch CSV for a given sensor and day, then push 5-min points to InfluxDB."""
    url = f"{BASE_URL}/{day}/{day}_laerm_sensor_{sensor_id}.csv"
    try:
        print(f"Fetching: {url}")
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"❌ No file for sensor {sensor_id} on {day}: {resp.status_code}")
            return
        lines = resp.text.strip().split("\n")
        headers = lines[0].split(";")
        for line in lines[1:]:
            parts = line.split(";")
            data = dict(zip(headers, parts))
            # parse timestamp in CET
            ts_local = datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M:%S")
            ts_local = CET.localize(ts_local)
            # only 5-minute marks
            if ts_local.minute % 5 != 0:
                continue
            # push each noise field
            for field in ["noise_LAeq", "noise_LA_min", "noise_LA_max"]:
                value = data.get(field)
                if not value:
                    continue
                point = (
                    Point("noise")
                    .tag("sensor_id", str(sensor_id))
                    .field(field, float(value))
                    .time(ts_local.astimezone(pytz.UTC), WritePrecision.S)
                )
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(f"✅ Done sensor {sensor_id} for {day}")
    except Exception as e:
        print(f"⚠️ Error for sensor {sensor_id} on {day}: {e}")


if __name__ == "__main__":
    print(f"Starting backfill for days: {DAYS}")
    for sensor in SENSOR_IDS:
        for day in DAYS:
            fetch_and_push(sensor, day)
            time.sleep(1)
    client.close()
    print("🎉 Backfill complete.")
