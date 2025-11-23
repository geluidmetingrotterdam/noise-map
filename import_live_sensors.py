import os
import requests
import csv
import io
import datetime
import time
from influxdb_client import InfluxDBClient, Point, WriteOptions

# ✅ Only live sensors

SENSOR_IDS = [
89747, 94735, 94449, 94448, 94687, 94693, 94701,
95492, 95490, 95484, 94695
]

# InfluxDB credentials (from environment)

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

if not all([INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
raise ValueError("InfluxDB credentials not set in environment variables")

def fetch_and_push(sensor_id, day):
url = f"[https://archive.sensor.community/{day}/{day}_laerm_sensor_{sensor_id}.csv](https://archive.sensor.community/{day}/{day}_laerm_sensor_{sensor_id}.csv)"
print(f"Fetching {url} ...", flush=True)

```
try:
    response = requests.get(url, timeout=30)
    if response.status_code != 200 or not response.text.strip():
        print(f"❌ Failed to fetch {url} (status {response.status_code})", flush=True)
        return False

    reader = csv.DictReader(io.StringIO(response.text), delimiter=";")
    rows = list(reader)
    if not rows:
        print(f"⚠️ No data in {url}", flush=True)
        return False

    points = []
    for row in rows:
        try:
            timestamp = datetime.datetime.fromisoformat(row["timestamp"])
            fields = {}
            for key, field_name in [("noise_LAeq", "LAeq"), ("noise_LA_min", "LAmin"), ("noise_LA_max", "LAmax")]:
                if row.get(key):
                    fields[field_name] = float(row[key])
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
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=WriteOptions(batch_size=1000, flush_interval=10000))
            write_api.write(bucket=INFLUX_BUCKET, record=points)

    print(f"✅ Wrote {len(points)} points for sensor {sensor_id} on {day}", flush=True)
    return True
except Exception as e:
    print(f"❌ Error processing {url}: {e}", flush=True)
    return False
```

def backfill_days(n_days: int = 7):
today = datetime.date.today()
for i in range(n_days):
day = today - datetime.timedelta(days=i+1)
day_str = day.strftime("%Y-%m-%d")
print(f"🕓 Processing {day_str}", flush=True)
successful_fetches = 0
for sensor in SENSOR_IDS:
if fetch_and_push(sensor, day_str):
successful_fetches += 1
time.sleep(1)
print(f"🎉 Finished {day_str}: {successful_fetches} sensors processed", flush=True)

if **name** == "**main**":
# Change n_days to 7, 14, or 30 depending on your backfill
backfill_days(n_days=7)
