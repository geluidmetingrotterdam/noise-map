#!/usr/bin/env python3
import os
import io
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from matplotlib.backends.backend_pdf import PdfPages

# -------- Settings --------
SENSOR_ID = "89747"     # change sensor ID if needed
START_DATE = datetime(2025, 8, 4)  # Monday
END_DATE   = datetime(2025, 8, 10) # Sunday
REPORT_NAME = f"weekly_report_{SENSOR_ID}_{START_DATE.date()}_{END_DATE.date()}.pdf"

# -------- Download + Parse --------
all_data = []

current = START_DATE
while current <= END_DATE:
    date_str = current.strftime("%Y-%m-%d")
    url = f"https://archive.sensor.community/{date_str}/{date_str}_laerm_sensor_{SENSOR_ID}.csv"
    print(f"Fetching {url}")
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"❌ No file for {date_str}")
            current += timedelta(days=1)
            continue

        df = pd.read_csv(io.StringIO(r.text), sep=";")

        # Standardize column names
        df = df.rename(columns={
            "timestamp": "timestamp",
            "laeq": "LAeq",
            "lamax": "LAmax",
            "lamin": "LAmin"
        })

        # Only keep what we need
        df = df[["timestamp", "LAeq", "LAmax", "LAmin"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        all_data.append(df)

    except Exception as e:
        print(f"⚠️ Could not parse {url}: {e}")

    current += timedelta(days=1)

if not all_data:
    raise RuntimeError("No data found for the selected week!")

# Merge all
data = pd.concat(all_data).sort_values("timestamp")
data.set_index("timestamp", inplace=True)

# -------- Plotting --------
with PdfPages(REPORT_NAME) as pdf:
    plt.figure(figsize=(12, 6))
    plt.plot(data.index, data["LAeq"], label="LAeq", color="blue")
    plt.plot(data.index, data["LAmax"], label="LAmax", color="red", alpha=0.6)
    plt.plot(data.index, data["LAmin"], label="LAmin", color="green", alpha=0.6)

    plt.title(f"Noise Report for Sensor {SENSOR_ID}\n{START_DATE.date()} to {END_DATE.date()}")
    plt.xlabel("Date/Time")
    plt.ylabel("dB(A)")
    plt.legend()
    plt.grid(True)

    pdf.savefig()
    plt.close()

print(f"✅ Weekly PDF report created: {REPORT_NAME}")
