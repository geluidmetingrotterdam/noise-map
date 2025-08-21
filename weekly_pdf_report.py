import os
import pytz
import pandas as pd
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# -----------------------
# Config
# -----------------------
SENSOR_ID = "89747"
TZ = pytz.timezone("Europe/Amsterdam")

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

# -----------------------
# Time range: Monday → Friday
# -----------------------
today = datetime.now(TZ).date()
monday = today - timedelta(days=today.weekday())   # start of this week (Monday)
friday = monday + timedelta(days=5)                # Friday 00:00 (exclusive)

start_time = monday.strftime("%Y-%m-%dT00:00:00Z")
end_time = friday.strftime("%Y-%m-%dT00:00:00Z")

print(f"Generating report for {SENSOR_ID} from {start_time} to {end_time}")

# -----------------------
# Query InfluxDB
# -----------------------
query = f"""
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start_time}, stop: {end_time})
  |> filter(fn: (r) => r["_measurement"] == "noise")
  |> filter(fn: (r) => r["sensor_id"] == "{SENSOR_ID}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["_time", "LAeq", "LAmax", "LAmin"])
"""

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
tables = client.query_api().query_data_frame(query=query)

if tables.empty:
    print("No data found for this period.")
    exit(0)

df = tables.copy()
df["_time"] = pd.to_datetime(df["_time"]).dt.tz_convert(TZ)
df.set_index("_time", inplace=True)

# -----------------------
# PDF Report
# -----------------------
os.makedirs("reports", exist_ok=True)
pdf_path = f"reports/weekly_report_{SENSOR_ID}.pdf"

with PdfPages(pdf_path) as pdf:
    # --- Page 1: time series
    plt.figure(figsize=(11, 6))
    plt.plot(df.index, df["LAeq"], label="LAeq")
    plt.plot(df.index, df["LAmax"], label="LAmax", alpha=0.7)
    plt.plot(df.index, df["LAmin"], label="LAmin", alpha=0.7)
    plt.title(f"Noise levels for sensor {SENSOR_ID} (Mon–Fri)")
    plt.xlabel("Time")
    plt.ylabel("dB(A)")
    plt.legend()
    plt.grid(True)
    pdf.savefig()
    plt.close()

    # --- Page 2: summary stats
    stats = df.describe()[["LAeq", "LAmax", "LAmin"]]
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis("off")
    ax.table(cellText=stats.round(2).values,
             colLabels=stats.columns,
             rowLabels=stats.index,
             loc="center")
    ax.set_title(f"Summary statistics for {SENSOR_ID} (Mon–Fri)")
    pdf.savefig()
    plt.close()

print(f"✅ PDF report generated: {pdf_path}")
