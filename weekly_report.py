#!/usr/bin/env python3
import os
import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from matplotlib.backends.backend_pdf import PdfPages

# ===== SETTINGS =====
SENSOR_ID = "89747"    # change to another sensor if needed
REPORTS_DIR = "reports"  # folder to save PDFs
ARCHIVE_URL = "https://archive.sensor.community"
# ====================

# Make sure reports folder exists
os.makedirs(REPORTS_DIR, exist_ok=True)

REPORT_FILE = os.path.join(REPORTS_DIR, f"weekly_report_{SENSOR_ID}.pdf")

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

def normalize_dataframe(df, url):
    rename_map = {
        "noise_LAeq": "LAeq",
        "noise_LA_max": "LAmax",
        "noise_LA_min": "LAmin",
        "timestamp": "timestamp"
    }
    df = df.rename(columns=rename_map)

    needed = ["timestamp", "LAeq", "LAmax", "LAmin"]
    if not all(col in df.columns for col in needed):
        print(f"⚠️ Skipping {url}: missing expected columns")
        return None

    df = df[needed].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna()
    return df

def build_pdf_report(df, start_date, end_date):
    plt.figure(figsize=(12,6))
    plt.plot(df["timestamp"], df["LAeq"], label="LAeq", color="blue")
    plt.plot(df["timestamp"], df["LAmax"], label="LAmax", color="red", alpha=0.6)
    plt.plot(df["timestamp"], df["LAmin"], label="LAmin", color="green", alpha=0.6)
    plt.xlabel("Time")
    plt.ylabel("dB(A)")
    plt.title(f"Noise Report – Sensor {SENSOR_ID}\n{start_date} → {end_date}")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    with PdfPages(REPORT_FILE) as pdf:
        pdf.savefig()
        plt.close()

    print(f"✅ PDF report saved as {REPORT_FILE}")

if __name__ == "__main__":
    start_date, end_date = get_last_full_week()
    print(f"📅 Generating report for {start_date} → {end_date}")

    all_data = []
    current = start_date
    while current <= end_date:
        df = fetch_csv(current, SENSOR_ID)
        if df is not None:
            df = normalize_dataframe(df, current.strftime("%Y-%m-%d"))
            if df is not None:
                all_data.append(df)
        current += timedelta(days=1)

    if not all_data:
        raise RuntimeError("No valid data found for the selected week!")

    full_df = pd.concat(all_data).sort_values("timestamp")
    build_pdf_report(full_df, start_date, end_date)
