import os
import pytz
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient

# ---- Settings ----
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
BUCKET = os.getenv("INFLUX_BUCKET", "sensor_data")  # matches backfill
REPORTS_DIR = "reports"  # inside noise-map
TZ = pytz.timezone("Europe/Amsterdam")

DAY_THRESHOLD = 55
NIGHT_THRESHOLD = 45

print(f"Reports will be saved inside: {os.path.abspath(REPORTS_DIR)}")

# ---- Fetch last 7 full days of data ----
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

today = datetime.now(TZ).date()
start = today - timedelta(days=7)
stop = today

query = f'''
from(bucket: "{BUCKET}")
  |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
  |> filter(fn: (r) => r._measurement == "noise")
  |> filter(fn: (r) => r._field == "noise_LAeq")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
  |> yield(name: "mean")
'''

tables = client.query_api().query(query)

records = []
for table in tables:
    for record in table.records:
        records.append({
            "time": record.get_time(),
            "value": record.get_value(),
            "sensor": record.values.get("sensor_id")  # matches backfill tag
        })

if not records:
    raise ValueError("⚠️ No records returned. Check your bucket, measurement, or date range.")

df = pd.DataFrame(records)
df["time"] = pd.to_datetime(df["time"]).dt.tz_convert(TZ)
df = df.set_index("time").sort_index()

# ---- Ensure reports directory exists ----
os.makedirs(REPORTS_DIR, exist_ok=True)

# ---- Process per sensor ----
for sensor_id, g in df.groupby("sensor"):
    sensor_dir = os.path.join(REPORTS_DIR, str(sensor_id))
    os.makedirs(sensor_dir, exist_ok=True)

    g["hour"] = g.index.hour
    g["is_day"] = g["hour"].between(7, 22)
    g["threshold"] = g.apply(lambda r: DAY_THRESHOLD if r["is_day"] else NIGHT_THRESHOLD, axis=1)
    g["exceeded"] = g["value"] > g["threshold"]

    total_day_minutes = g[g["is_day"] & g["exceeded"]].shape[0] * 5
    total_night_minutes = g[~g["is_day"] & g["exceeded"]].shape[0] * 5

    # Detect events
    g["event"] = (g["exceeded"] != g["exceeded"].shift()).cumsum()
    events = g[g["exceeded"]].groupby("event").size() * 5
    num_events = len(events)
    avg_duration = events.mean() if num_events > 0 else 0
    max_duration = events.max() if num_events > 0 else 0

    # Summary table
    summary = pd.DataFrame([{
        "Sensor": sensor_id,
        "LAeq Day Avg": round(g[g["is_day"]]["value"].mean(), 1),
        "LAeq Night Avg": round(g[~g["is_day"]]["value"].mean(), 1),
        "Minutes > Day Thr": total_day_minutes,
        "Minutes > Night Thr": total_night_minutes,
        "Noise Events": num_events,
        "Avg Event Duration (min)": round(avg_duration, 1),
        "Max Event Duration (min)": max_duration
    }])

    # ---- Charts ----
    plt.figure(figsize=(12, 6))
    g["value"].plot(alpha=0.7)
    plt.axhline(DAY_THRESHOLD, color="orange", linestyle="--", label="Day threshold")
    plt.axhline(NIGHT_THRESHOLD, color="purple", linestyle="--", label="Night threshold")
    plt.title(f"Weekly Noise Levels – Sensor {sensor_id}")
    plt.ylabel("dB")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(sensor_dir, "weekly_noise.png"))
    plt.close()

    pivot = g.groupby([g.index.date, g.index.hour])["exceeded"].mean().unstack(fill_value=0)
    plt.figure(figsize=(10, 5))
    plt.imshow(pivot.T, aspect="auto", cmap="Reds", origin="lower")
    plt.yticks(range(24), range(24))
    plt.xticks(range(len(pivot.index)), [str(d)[5:] for d in pivot.index], rotation=45)
    plt.colorbar(label="Fraction above threshold")
    plt.title("Exceedance Heatmap (hour vs day)")
    plt.tight_layout()
    plt.savefig(os.path.join(sensor_dir, "exceedance_heatmap.png"))
    plt.close()

    # ---- HTML with PDF button ----
    html = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <title>Weekly Noise Report – Sensor {sensor_id}</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
        th {{ background-color: #f4f4f4; }}
        img {{ max-width: 100%; margin-top: 20px; border: 1px solid #ddd; }}
        .btn {{ display:inline-block;padding:10px 15px;margin:10px 0;background:#2c3e50;color:#fff;text-decoration:none;border-radius:5px; }}
      </style>
    </head>
    <body>
      <h1>Weekly Noise Report</h1>
      <h2>Sensor {sensor_id}</h2>
      <p>Generated on {datetime.now(TZ).strftime("%Y-%m-%d %H:%M")}</p>
      <a class="btn" href="#" onclick="window.print()">Download PDF</a>
      <h2>Summary</h2>
      {summary.to_html(index=False)}
      <h2>Weekly Noise Graph</h2>
      <img src="weekly_noise.png"/>
      <h2>Exceedance Heatmap</h2>
      <img src="exceedance_heatmap.png"/>
    </body>
    </html>
    """

    with open(os.path.join(sensor_dir, "weekly_report.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Report generated for sensor {sensor_id}")
