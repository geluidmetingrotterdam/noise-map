import os
import requests
import gzip
import csv
import io
import datetime
import time
from influxdb_client import InfluxDBClient, Point, WriteOptions

# ✅ Cleaned sensor list (duplicates removed, comma separated)
SENSOR_IDS = [
    93868, 94284, 94447, 94448, 94449, 94686, 94687, 94688, 94689,
    94692, 94693, 94695, 94696, 94701, 94735, 95432, 95482, 95483,
    95484, 95485, 95486, 95487, 95488, 95489, 95490, 95491, 95492,
    95493, 95494, 95495, 89747
]

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

def fetch_and_push(sensor_id, day):
    url = f"https://archive.sensor.community/{day}_laerm_sensor_{sensor_id}.csv.gz"
    print(f"Fetching {url} ...", flush=True)

    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to fetch {url} (status {response.status_code})", flush=True)
            return False

        compressed_file = io.BytesIO(response.content)
        with gzip.open(compressed_file, mode="rt") as f:
            reader = csv.DictReader(f, delimiter=";")
            rows = list(reader)

        if not rows:
            print(f"⚠️ No data in {url}", flush=True)
            return False

        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=WriteOptions(batch_size=1000, flush_interval=10000))
            points = []
            for row in rows:
                try:
                    timestamp = datetime.datetime.fromisoformat(row["timestamp"])
                    fields = {}
                    for key in ["LAeq", "LAmin", "LAmax"]:
                        if row.get(key):
                            fields[key] = float(row[key])
                    if fields:
                        point = Point("noise") \
                            .tag("sensor_id", str(sensor_id)) \
                            .time(timestamp) \
                            .field("LAeq", fields.get("LAeq", 0)) \
                            .field("LAmin", fields.get("LAmin", 0)) \
                            .field("LAmax", fields.get("LAmax", 0))
                        points.append(point)
                except Exception as e:
                    print(f"⚠️ Skipping row due to error: {e}", flush=True)
            if points:
                write_api.write(bucket=INFLUX_BUCKET, record=points)
        print(f"✅ Wrote {len(points)} points for sensor {sensor_id} on {day}", flush=True)
        return True
    except Exception as e:
        print(f"❌ Error processing {url}: {e}", flush=True)
        return False

def backfill_day(day: str):
    print(f"🕓 Processing {day}", flush=True)
    successful_fetches = 0
    for sensor in SENSOR_IDS:
        if fetch_and_push(sensor, day):
            successful_fetches += 1
        time.sleep(1)
    print(f"🎉 Finished {day}: {successful_fetches} sensors processed", flush=True)
    return successful_fetches > 0

if __name__ == "__main__":
    today = datetime.date.today()
    target_day = today - datetime.timedelta(days=1)
    day_str = target_day.strftime("%Y-%m-%d")

    print(f"🚀 Starting backfill for {day_str}", flush=True)
    success = backfill_day(day_str)
    if not success:
        print(f"⚠️ No data fetched for {day_str}", flush=True)
