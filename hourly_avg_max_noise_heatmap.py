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

# List of sensors to include
SENSOR_IDS = [
    89747, 94284, 94735, 94449, 94687, 94448, 94693, 94701,
    95492, 95490, 95484, 94695
]

# InfluxDB settings from GitHub secrets
INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "noise_data")

# Use LAmax for heatmap
FIELD = "LAmax"

# ===== FUNCTIONS =====
def get_last_full_week():
    today = datetime.utcnow().date()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday

def fetch_influxdb_data(start_date, end_date):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    
    sensor_filter = ", ".join([f'"{sid}"' for sid in SENSOR_IDS])
    
    query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start_date}T00:00:00Z, stop: {end_date + timedelta(days=1)}T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "noise" and r._field == "{FIELD}")
  |> filter(fn: (r) => contains(value: r.sensor_id, set: [{sensor_filter}]))
'''
    tables = query_api.query(query)
    rows = []
    for table in tables:
        for record in table.records:
            rows.append({
                "timestamp": record.get_time(),
                "sensor_id": record.values.get("sensor_id"),
                FIELD: record.get_value()
            })
    df = pd.DataFrame(rows)
    if df.empty:
        print("⚠️ No data returned from InfluxDB")
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def build_heatmap(df, start_date, end_date):
    # ===== Heatmap same as original script =====
    df["hour"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date
    pivot = df.pivot_table(index="date", columns="hour", values=FIELD, aggfunc="mean")

    # Reorder hours 07..23 + 00..06
    hour_order = list(range(7, 24)) + list(range(0, 7))
    pivot = pivot[hour_order]

    # Day/evening/night color adjustments
    adj_map = pd.Series(0, index=hour_order, dtype=float)
    adj_map.loc[7:18] = 0      # 07–18 day
    adj_map.loc[19:22] = 5     # 19–22 evening
    adj_map.loc[list(range(23, 24)) + list(range(0, 7))] = 10  # 23–06 night

    adjusted_pivot = pivot.add(adj_map, axis=1)

    # Color map
    cmap = LinearSegmentedColormap.from_list(
        "noise_levels", ["gray", "green", "yellow", "red", "darkred", "black"]
    )
    norm = PowerNorm(gamma=2.5, vmin=0, vmax=80)

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
    plt.title(f"Hourly Average Max Noise Heatmap ({FIELD})\n{start_date} → {end_date}")
    plt.tight_layout()
    out_file = os.path.join(REPORTS_DIR, f"hourly_avg_max_noise_heatmap.png")
    plt.savefig(out_file, dpi=150)
    plt.close()
    print(f"✅ Heatmap saved to {out_file}")

    # PDF version
    pdf_file = os.path.join(REPORTS_DIR, f"hourly_avg_max_noise_heatmap.pdf")
    with PdfPages(pdf_file) as pdf:
        fig = plt.figure()
        plt.imshow(plt.imread(out_file))
        plt.axis("off")
        pdf.savefig(fig)
        plt.close(fig)
    print(f"✅ PDF saved to {pdf_file}")

# ===== MAIN =====
if __name__ == "__main__":
    start_date, end_date = get_last_full_week()
    df = fetch_influxdb_data(start_date, end_date)
    if df is not None:
        build_heatmap(df, start_date, end_date)
    else:
        print("❌ No data to build heatmap")
