import os
import requests
import csv
import io
import datetime
import time
from influxdb_client import InfluxDBClient, Point, WriteOptions

SENSOR_IDS = [
    89747, 94735, 94449, 94448, 94687, 94693, 94701,
    95492, 95490, 95484, 94695
]

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

def fetch_and_push(sensor_id, day):
    url = f"https://archive.sensor.community/{day}/{day}_laerm_sensor_{sensor_id}.csv"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404: return True
        if response.status_code != 200: return False

        content = response.text.strip()
        if not content: return True

        reader = csv.DictReader(io.StringIO(content), delimiter=";")
        points = []
        for row in reader:
            try:
                timestamp = datetime.datetime.fromisoformat(row["timestamp"])
                point = Point("noise") \
                    .tag("sensor_id", str(sensor_id)) \
                    .time(timestamp) \
                    .field("LAeq", float(row.get("noise_LAeq", 0) or 0)) \
                    .field("LAmin", float(row.get("noise_LA_min", 0) or 0)) \
                    .field("LAmax", float(row.get("noise_LA_max", 0) or 0))
                points.append(point)
            except Exception: continue

        if points:
            with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
                with client.write_api(write_options=WriteOptions(batch_size=500)) as write_api:
                    write_api.write(bucket=INFLUX_BUCKET, record=points)
            print(f"✅ Loaded {len(points)} pts for {sensor_id} ({day})")
        return True
    except Exception as e:
        print(f"❌ Error {sensor_id} on {day}: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting 30-day historical backfill...")
    today = datetime.date.today()
    # Process the last 30 days
    for i in range(30):
        day = today - datetime.timedelta(days=i+1)
        day_str = day.strftime("%Y-%m-%d")
        print(f"🕓 Processing {day_str}...")
        for sensor in SENSOR_IDS:
            fetch_and_push(sensor, day_str)
            time.sleep(0.2) # Small delay to be server-friendly
    print("🎉 Full 30-day backfill completed!")
