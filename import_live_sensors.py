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
    url = f"https://archive.sensor.community/{day}/{day}_laerm_sensor_{sensor_id}.csv"
    
    try:
        response = requests.get(url, timeout=30)
        
        # 1. Handle 404 (Expected for inactive sensors)
        if response.status_code == 404:
            return True 
            
        # 2. Handle other errors
        if response.status_code != 200:
            print(f"⚠️ Error {response.status_code} for {sensor_id} on {day}", flush=True)
            return False

        # 3. Process CSV
        content = response.text.strip()
        if not content:
            return True

        reader = csv.DictReader(io.StringIO(content), delimiter=";")
        points = []
        for row in reader:
            try:
                timestamp = datetime.datetime.fromisoformat(row["timestamp"])
                point = Point("noise") \
                    .tag("sensor_id", str(sensor_id)) \
                    .time(timestamp) \
                    .field("LAeq", float(row["noise_LAeq"]) if row.get("noise_LAeq") else 0.0) \
                    .field("LAmin", float(row["noise_LA_min"]) if row.get("noise_LA_min") else 0.0) \
                    .field("LAmax", float(row["noise_LA_max"]) if row.get("noise_LA_max") else 0.0)
                points.append(point)
            except Exception:
                continue

        if points:
            with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
                write_api = client.write_api(write_options=WriteOptions(batch_size=500))
                write_api.write(bucket=INFLUX_BUCKET, record=points)
            print(f"✅ Wrote {len(points)} points for {sensor_id} ({day})", flush=True)
            
        return True

    except Exception as e:
        print(f"❌ Connection error for {sensor_id}: {e}", flush=True)
        return False

def backfill_days(n_days: int = 30):
    today = datetime.date.today()
    for i in range(n_days):
        day = today - datetime.timedelta(days=i+1)
        day_str = day.strftime("%Y-%m-%d")
        print(f"🕓 Processing {day_str}...", flush=True)
        for sensor in SENSOR_IDS:
            fetch_and_push(sensor, day_str)
            time.sleep(0.5) # Slight pause to be polite to the server

if __name__ == "__main__":
    backfill_days(n_days=30)
