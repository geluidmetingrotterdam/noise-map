import os
import requests
import csv
import io
import datetime
import time
from collections import defaultdict
from influxdb_client import InfluxDBClient, Point

# ===== SETTINGS =====
SENSOR_ID = 94695

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "noise_data")

# Third trimester 2025
START_DATE = datetime.date(2025, 7, 1)
END_DATE = datetime.date(2025, 9, 30)

# ===== FUNCTIONS =====
def fetch_and_push(sensor_id, day: datetime.date):
    day_str = day.strftime("%Y-%m-%d")
    url = f"https://archive.sensor.community/{day_str}/{day_str}_laerm_sensor_{sensor_id}.csv"
    print(f"Fetching {url} ...", flush=True)

    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200 or not response.text.strip():
            print(f"⚠️ No CSV found for {day_str} (status {response.status_code})", flush=True)
            return 0

        reader = csv.DictReader(io.StringIO(response.text), delimiter=";")
        rows = list(reader)
        if not rows:
            print(f"⚠️ CSV empty for {day_str}", flush=True)
            return 0

        points_count = 0
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api()  # synchronous
            points = []

            for row in rows:
                try:
                    timestamp = datetime.datetime.fromisoformat(row["timestamp"])
                    fields = {}
                    for key_csv, key_field in [
                        ("noise_LAeq","LAeq"),
                        ("noise_LA_min","LAmin"),
                        ("noise_LA_max","LAmax")
                    ]:
                        if row.get(key_csv):
                            fields[key_field] = float(row[key_csv])
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
                points_count = len(points)

        print(f"✅ Wrote {points_count} points for {sensor_id} on {day_str}", flush=True)
        return points_count

    except Exception as e:
        print(f"❌ Error processing {url}: {e}", flush=True)
        return 0

def backfill_range(start_date: datetime.date, end_date: datetime.date):
    current_day = start_date
    monthly_counts = defaultdict(int)

    while current_day <= end_date:
        count = fetch_and_push(SENSOR_ID, current_day)
        month_key = current_day.strftime("%Y-%m")
        monthly_counts[month_key] += count
        time.sleep(1)  # avoid overwhelming server
        current_day += datetime.timedelta(days=1)

    print("\n📊 Summary of points fetched per month:")
    for month, total in monthly_counts.items():
        print(f"  {month}: {total} points")

# ===== MAIN =====
if __name__ == "__main__":
    print(f"🚀 Starting backfill for sensor {SENSOR_ID} from {START_DATE} to {END_DATE}")
    backfill_range(START_DATE, END_DATE)
    print("🎉 Done!")
