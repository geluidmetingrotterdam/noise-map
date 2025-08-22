import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# ========== SETTINGS ==========
SENSOR_ID = "89747"   # Rotterdam sensor ID
REPORT_FILE = "weekly_report.pdf"
ARCHIVE_URL = "https://archive.sensor.community"
# ===============================

def get_last_full_week():
    today = datetime.utcnow().date()
    # find last Sunday
    last_sunday = today - timedelta(days=today.weekday() + 1)
    # Monday before that
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday

def fetch_csv(date, sensor_id):
    date_str = date.strftime("%Y-%m-%d")
    url = f"{ARCHIVE_URL}/{date_str}/{date_str}_laerm_sensor_{sensor_id}.csv"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return pd.read_csv(pd.compat.StringIO(r.text), sep=";")
        else:
            print(f"❌ No file for {date_str}")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return None

def normalize_dataframe(df, url):
    rename_map = {
        "noise_LAeq": "LAeq",
        "noise_LAmax": "LAmax",
        "noise_LAmin": "LAmin",
        "laeq": "LAeq",
        "lamax": "LAmax",
        "lamin": "LAmin",
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

def build_report(df, start_date, end_date):
    # ---- Plot with matplotlib ----
    plt.figure(figsize=(10, 6))
    plt.plot(df["timestamp"], df["LAeq"], label="LAeq", linewidth=1)
    plt.plot(df["timestamp"], df["LAmax"], label="LAmax", linewidth=1)
    plt.plot(df["timestamp"], df["LAmin"], label="LAmin", linewidth=1)
    plt.legend()
    plt.xlabel("Time")
    plt.ylabel("dB(A)")
    plt.title(f"Noise Report Sensor {SENSOR_ID}\n{start_date} → {end_date}")
    plt.tight_layout()
    img_file = "weekly_plot.png"
    plt.savefig(img_file)
    plt.close()

    # ---- Create PDF ----
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(REPORT_FILE, pagesize=A4)
    story = []
    story.append(Paragraph(f"<b>Weekly Noise Report – Sensor {SENSOR_ID}</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Period: {start_date} → {end_date}", styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Image(img_file, width=500, height=300))
    doc.build(story)

    print(f"✅ Report saved as {REPORT_FILE}")

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
    build_report(full_df, start_date, end_date)
