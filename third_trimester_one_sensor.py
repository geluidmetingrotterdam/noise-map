#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.backends.backend_pdf import PdfPages

# ===== SETTINGS =====
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

SENSOR_ID = 94695
INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "noise_data")
FIELD = "LAmax"

# Third trimester 2025
START_DATE = datetime(2025, 7, 1)
END_DATE = datetime(2025, 9, 30)

# ===== FUNCTIONS =====
def fetch_sensor_data(sensor_id, start_date, end_date):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    start_iso = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_iso = (end_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start_iso}, stop: {end_iso})
  |> filter(fn: (r) => r._measurement == "noise" and r._field == "{FIELD}")
  |> filter(fn: (r) => r.sensor_id == {sensor_id})
'''
    tables = query_api.query(query)
    rows = []
    for table in tables:
        for record in table.records:
            rows.append({
                "timestamp": record.get_time(),
                FIELD: record.get_value()
            })
    df = pd.DataFrame(rows)
    if df.empty:
        print(f"⚠️ No data for sensor {sensor_id}")
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def build_heatmap(df, sensor_id, start_date, end_date):
    df["hour"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date

    # Pivot: rows = date, columns = hour
    pivot = df.groupby([df["date"], df["hour"]])[FIELD].mean().unstack()

    # Reorder hours 07..23 + 00..06
    hour_order = list(range(7, 24)) + list(range(0, 7))
    for h in hour_order:
        if h not in pivot.columns:
            pivot[h] = float('nan')
    pivot = pivot[hour_order]

    # Day/evening/night penalty for heatmap shading
    adj_map = pd.Series(0, index=hour_order, dtype=float)
    adj_map.loc[7:19] = 0        # 07-19 daytime
    adj_map.loc[19:23] = 5       # 19-23 evening
    adj_map.loc[list(range(23, 24)) + list(range(0, 7))] = 10  # 23-07 night

    adjusted_pivot = pivot.add(adj_map, axis=1)

    # Color map and normalization
    cmap = LinearSegmentedColormap.from_list(
        "noise_levels", ["gray", "green", "yellow", "red", "darkred", "black"]
    )
    norm = PowerNorm(gamma=2.5, vmin=0, vmax=80)

    # Plot heatmap
    plt.figure(figsize=(12, 6))
    ax = sns.heatmap(
        adjusted_pivot.T,
        annot=pivot.T,
        fmt=".0f",
        cmap=cmap,
        norm=norm,
        cbar_kws={'label': f'Avg {FIELD} dB(A)'},
        linewidths=.5
    )
    ax.set_yticklabels(hour_order)
    ax.set_xticklabels([d.strftime("%a %d") for d in pivot.index], rotation=45)
    plt.ylabel("Hour of day (07 → 07)")
    plt.xlabel("Date")
    plt.title(f"Hourly Average Max Noise Heatmap ({FIELD})\nSensor {sensor_id} {start_date.date()} → {end_date.date()}")
    plt.tight_layout()

    # Save final PDF
    pdf_file = os.path.join(REPORTS_DIR, f"{sensor_id}_final_report_2nd_trimester.pdf")
    with PdfPages(pdf_file) as pdf:
        pdf.savefig(plt.gcf())
    plt.close()
    print(f"✅ Final PDF saved: {pdf_file}")

# ===== MAIN =====
if __name__ == "__main__":
    df = fetch_sensor_data(SENSOR_ID, START_DATE, END_DATE)
    if df is not None:
        build_heatmap(df, SENSOR_ID, START_DATE, END_DATE)
