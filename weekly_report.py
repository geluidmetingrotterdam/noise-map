#!/usr/bin/env python3

import os
import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime, timedelta
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

# ===== SETTINGS =====
SENSOR_IDS = [
    89747, 94284, 94735, 94449, 94687, 94448, 94693, 94284, 94701,
    95492, 95490, 95484, 94695
]

REPORTS_DIR = "reports"
ARCHIVE_URL = "https://archive.sensor.community"
DAY_THRESHOLD = 65
NIGHT_THRESHOLD = 50
# ====================

os.makedirs(REPORTS_DIR, exist_ok=True)


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
            print(f"❌ No file for {date_str}")
            return None
        df = pd.read_csv(io.StringIO(r.text), sep=";")
        return df
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return None


def normalize_dataframe(df):
    rename_map = {
        "noise_LAeq": "LAeq",
        "noise_LA_max": "LAmax",
        "noise_LA_min": "LAmin",
        "timestamp": "timestamp"
    }
    df = df.rename(columns=rename_map)
    needed = ["timestamp", "LAeq", "LAmax", "LAmin"]
    if not all(col in df.columns for col in needed):
        return None
    df = df[needed].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna()
    return df


def build_report(sensor_id, df, start_date, end_date):
    sensor_dir = os.path.join(REPORTS_DIR, str(sensor_id))
    os.makedirs(sensor_dir, exist_ok=True)

    # ---- Only Chart 2: Heatmap with LAmax (day 07:00 → 07:00 next) ----

    df["hour"] = df["timestamp"].dt.hour
    df["date"] = df["timestamp"].dt.date

    # Assign early hours (00:00–06:59) to previous day
    df["day_for_heatmap"] = df["date"]
    mask_early = df["hour"].between(0, 6)
    df.loc[mask_early, "day_for_heatmap"] = (
        pd.to_datetime(df.loc[mask_early, "day_for_heatmap"]) - pd.Timedelta(days=1)
    )
    df["day_for_heatmap"] = pd.to_datetime(df["day_for_heatmap"]).dt.date

    # Group and pivot
    pivot = df.groupby([df["day_for_heatmap"], df["hour"]])["LAmax"].mean().unstack()

    # Ensure all hours exist
    hours = list(range(24))
    pivot = pivot.reindex(columns=hours)

    # Reorder hours so rows start at 07:00 (07..23 + 00..06)
    hour_order = list(range(7, 24)) + list(range(0, 7))
    pivot = pivot[hour_order]

    # Hidden adjustment map (for color shifts)
    adj_map = pd.Series(0, index=hour_order, dtype=float)
    adj_map.loc[7:18] = 0      # 07–18
    adj_map.loc[19:22] = 5     # 19–22
    adj_map.loc[list(range(23, 24)) + list(range(0, 7))] = 10  # 23–06
    adjusted_pivot = pivot.add(adj_map, axis=1)

    # Plot heatmap
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
        cbar_kws={'label': 'Avg LAmax dB(A)'},
        linewidths=.5
    )
    ax.set_yticklabels(hour_order)
    ax.set_xticklabels([f"{d.strftime('%a %d')}" for d in pivot.index], rotation=45)
    plt.ylabel("Hour of day (07 → 07)")
    plt.title(f"Average LAmax Heatmap – Sensor {sensor_id} ({start_date} → {end_date})")
    plt.tight_layout()
    plt.savefig(os.path.join(sensor_dir, "la_max_heatmap.png"))
    plt.close()

    print(f"✅ Heatmap saved: {sensor_dir}/la_max_heatmap.png")


if __name__ == "__main__":
    start_date, end_date = get_last_full_week()
    for sensor_id in SENSOR_IDS:
        print(f"📅 Generating heatmap for sensor {sensor_id}: {start_date} → {end_date}")
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
        build_report(sensor_id, full_df, start_date, end_date)

    print(f"✅ All heatmaps generated in {REPORTS_DIR}/")
