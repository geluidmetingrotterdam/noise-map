#!/usr/bin/env python3

import os
import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

# ===== SETTINGS =====
SENSOR_IDS = [
    89747, 94284, 94735, 94449, 94687, 94448, 94693, 94701,
    95492, 95490, 95484, 94695
]

REPORTS_DIR = "reports"
ARCHIVE_URL = "https://archive.sensor.community"
os.makedirs(REPORTS_DIR, exist_ok=True)
# ====================


def get_last_full_week():
    today = datetime.utcnow().date()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def fetch_csv(date, sensor_id):
    date_str = date.strftime("%Y-%m-%d")
    url = f"{ARCHIVE_URL}/{date_str}/{date_str}_laerm_sensor_{sensor_id}.csv"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"❌ No file for {date_str} / sensor {sensor_id}")
            return None
        df = pd.read_csv(io.StringIO(r.text), sep=";")
        return df
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return None


def normalize_dataframe(df):
    rename_map = {
        "timestamp": "timestamp",
        "noise_LA_max": "LAmax"
    }
    df = df.rename(columns=rename_map)
    if "timestamp" not in df.columns or "LAmax" not in df.columns:
        return None
    df = df[["timestamp", "LAmax"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna()
    return df


def build_heatmap(sensor_id, df, start_date, end_date):
    # Create pivot: rows = date, columns = hour, values = avg LAmax
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    pivot = df.groupby(["date", "hour"])["LAmax"].mean().unstack(fill_value=0)

    # Ensure all 24 hours exist
    pivot = pivot.reindex(columns=range(24), fill_value=0)

    plt.figure(figsize=(12, 6))
    sns.heatmap(
        pivot,
        cmap="YlOrRd",
        linewidths=0.5,
        cbar_kws={"label": "Average LAmax dB(A)"}
    )
    plt.title(f"Hourly Average Max Noise Heatmap – Sensor {sensor_id}\n{start_date} → {end_date}")
    plt.ylabel("Date")
    plt.xlabel("Hour of day")
    plt.tight_layout()

    sensor_dir = os.path.join(REPORTS_DIR, str(sensor_id))
    os.makedirs(sensor_dir, exist_ok=True)
    file_path = os.path.join(sensor_dir, "hourly_avg_max_noise_heatmap.png")
    plt.savefig(file_path)
    plt.close()
    print(f"✅ Heatmap saved: {file_path}")


if __name__ == "__main__":
    start_date, end_date = get_last_full_week()
    print(f"📅 Generating hourly average max noise heatmaps for {start_date} → {end_date}")

    for sensor_id in SENSOR_IDS:
        all_data = []
        current = start_date
        while current <= end_date:
            df = fetch_csv(current, sensor_id)
            if df is not None:
                df = normalize_dataframe(df)
                if df is not None:
                    all_data.append(df)
            current += timedelta(days=1)

        if not all_data:
            print(f"⚠️ No valid data for sensor {sensor_id}")
            continue

        full_df = pd.concat(all_data).sort_values("timestamp")
        build_heatmap(sensor_id, full_df, start_date, end_date)

print("✅ All heatmaps generated.")
