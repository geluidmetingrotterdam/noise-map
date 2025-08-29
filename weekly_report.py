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
SENSOR_IDS = ["89747"]  # add more IDs if needed
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

    # ---- Chart 2: Heatmap with LAmin ----
    pivot = df.groupby([df["timestamp"].dt.date, df["timestamp"].dt.hour])["LAmin"].mean().unstack(fill_value=0)
    cmap = LinearSegmentedColormap.from_list(
        "noise_levels", ["green", "yellow", "red", "darkred", "black"]
    )
    norm = PowerNorm(gamma=1.0, vmin=40, vmax=80)
    plt.figure(figsize=(12, 6))
    ax = sns.heatmap(
        pivot.T,
        annot=True,
        fmt=".1f",
        cmap=cmap,
        norm=norm,
        cbar_kws={'label': 'Avg LAmin dB(A)'},
        linewidths=.5
    )
    ax.set_yticklabels(range(24))
    ax.set_xticklabels([f"{d.strftime('%a %d')}" for d in pivot.index], rotation=45)
    plt.ylabel("Hour of day")
    plt.title("Average LAmin Heatmap (hour vs day)")
    plt.tight_layout()
    plt.savefig(os.path.join(sensor_dir, "la_min_heatmap.png"))
    plt.close()

    # ---- PDF ----
    pdf_file = os.path.join(sensor_dir, f"weekly_report_{sensor_id}.pdf")
    with PdfPages(pdf_file) as pdf:
        for img in ["weekly_noise.png", "la_min_heatmap.png"]:
            fig = plt.figure()
            plt.imshow(plt.imread(os.path.join(sensor_dir, img)))
            plt.axis("off")
            pdf.savefig(fig)
            plt.close(fig)
    print(f"✅ PDF saved: {pdf_file}")

    # ---- HTML ----
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Weekly Noise Report {sensor_id}</title></head>
    <body>
        <h1>Weekly Noise Report – Sensor {sensor_id}</h1>
        <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        <h2>Summary</h2>
        {summary.to_html(index=False)}
        <h2>Weekly Noise Graph</h2>
        <img src="weekly_noise.png"/>
        <h2>Heatmap (Hourly Average LAmin)</h2>
        <img src="la_min_heatmap.png"/>
    </body>
    </html>
    """
    with open(os.path.join(sensor_dir, "weekly_report.html"), "w", encoding="utf-8") as f:
        f.write(html)


def build_index(sensor_ids):
    index_path = os.path.join(REPORTS_DIR, "index.html")
    links = [f'<li><a href="{sid}/weekly_report.html">Sensor {sid}</a></li>' for sid in sensor_ids]
    index_html = f"<html><body><h1>Weekly Noise Reports</h1><ul>{''.join(links)}</ul></body></html>"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)


if __name__ == "__main__":
    start_date, end_date = get_last_full_week()
    for sensor_id in SENSOR_IDS:
        print(f"📅 Generating report for sensor {sensor_id}: {start_date} → {end_date}")
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

    build_index(SENSOR_IDS)
    print(f"✅ Index created at {os.path.join(REPORTS_DIR,'index.html')}")
