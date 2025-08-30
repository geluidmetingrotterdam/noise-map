#!/usr/bin/env python3

import os
import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

# ===== SETTINGS =====
SENSOR_IDS = [
    89747, 94284, 94735, 94449, 94687, 94448, 94693, 94284, 94701,
    95492, 95490, 95484,
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

def analyze(df):
    df["hour"] = df["timestamp"].dt.hour
    df["is_day"] = df["hour"].between(7, 22)
    df["threshold"] = df["is_day"].map({True: DAY_THRESHOLD, False: NIGHT_THRESHOLD})
    df["exceeded"] = df["LAmin"] > df["threshold"]

    total_day_minutes = df[df["is_day"] & df["exceeded"]].shape[0] * 5
    total_night_minutes = df[~df["is_day"] & df["exceeded"]].shape[0] * 5

    df["event"] = (df["exceeded"] != df["exceeded"].shift()).cumsum()
    events = df[df["exceeded"]].groupby("event").size() * 5

    num_events = len(events)
    avg_duration = round(events.mean(), 1) if num_events else 0
    max_duration = int(events.max()) if num_events else 0

    summary = pd.DataFrame([{
        "LAmin Day Avg": round(df[df["is_day"]]["LAmin"].mean(), 1),
        "LAmin Night Avg": round(df[~df["is_day"]]["LAmin"].mean(), 1),
        "Minutes > Day Thr": total_day_minutes,
        "Minutes > Night Thr": total_night_minutes,
        "Noise Events": num_events,
        "Avg Event Duration (min)": avg_duration,
        "Max Event Duration (min)": max_duration
    }])
    return summary

def build_report(sensor_id, df, start_date, end_date):
    sensor_dir = os.path.join(REPORTS_DIR, str(sensor_id))
    os.makedirs(sensor_dir, exist_ok=True)

    summary = analyze(df)

    # ---- Chart 1: Weekly Noise ----
    plt.figure(figsize=(12, 6))
    plt.plot(df["timestamp"], df["LAeq"], label="LAeq", color="blue")
    plt.plot(df["timestamp"], df["LAmax"], label="LAmax", color="red", alpha=0.6)
    plt.plot(df["timestamp"], df["LAmin"], label="LAmin", color="green", alpha=0.6)
    plt.axhline(DAY_THRESHOLD, color="orange", linestyle="--", label="Day thr")
    plt.axhline(NIGHT_THRESHOLD, color="purple", linestyle="--", label="Night thr")
    plt.xlabel("Time")
    plt.ylabel("dB(A)")
    plt.title(f"Noise Report – Sensor {sensor_id}\n{start_date} → {end_date}")
    plt.legend()
    plt.grid(True)
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(sensor_dir, "weekly_noise.png"))
    plt.close()

    # ---- Chart 2: Heatmap with LAmin (adjusted for evening/night) ----
    pivot = df.groupby([df["timestamp"].dt.date, df["timestamp"].dt.hour])["LAmin"].mean().unstack(fill_value=0)
    adjusted_pivot = pivot.copy()

    # Ensure column type is int for correct comparisons
    adjusted_pivot.columns = adjusted_pivot.columns.astype(int)

    for hour in adjusted_pivot.columns:
        if 7 <= hour < 19:        # Day
            continue
        elif 19 <= hour < 23:     # Evening
            adjusted_pivot[hour] += 5
        else:                     # Night
            adjusted_pivot[hour] += 10

    cmap = LinearSegmentedColormap.from_list(
        "noise_levels", ["gray", "green", "yellow", "red", "darkred", "black"]
    )
    norm = PowerNorm(gamma=1.9, vmin=0, vmax=80)

    plt.figure(figsize=(12, 6))
    ax = sns.heatmap(
        adjusted_pivot.T,
        annot=True,
        fmt=".1f",
        cmap=cmap,
        norm=norm,
        cbar_kws={'label': 'Avg LAmin dB(A)'},
        linewidths=.5
    )
    ax.set_yticklabels(range(24))
    ax.set_xticklabels([f"{d.strfti]()_
