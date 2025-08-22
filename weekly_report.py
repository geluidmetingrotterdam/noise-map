import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# ---- Config ----
ROTTERDAM_SENSORS = [
    89747, 94284, 94448, 94449, 94687, 94693, 94701, 94735
]
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

today = datetime.utcnow().date()

def find_last_week_with_data(sensor_id, max_weeks_back=6):
    for week_shift in range(max_weeks_back):
        monday = today - timedelta(days=today.weekday() + 7*(week_shift+1))
        sunday = monday + timedelta(days=6)
        dfs = []
        for i in range(7):
            day = monday + timedelta(days=i)
            url = f"https://archive.sensor.community/{day}/{sensor_id}_noise.csv"
            resp = requests.get(url)
            if resp.status_code == 200:
                try:
                    df_day = pd.read_csv(pd.compat.StringIO(resp.text), sep=";")
                    df_day["timestamp"] = pd.to_datetime(df_day["timestamp"])
                    dfs.append(df_day)
                except Exception as e:
                    print(f"⚠️ Could not parse {url}: {e}")
        if dfs:
            return monday, sunday, pd.concat(dfs)
    return None, None, pd.DataFrame()

# ---- Pick first sensor with data ----
for sensor in ROTTERDAM_SENSORS:
    monday, sunday, df = find_last_week_with_data(sensor)
    if not df.empty:
        SENSOR_ID = sensor
        break

if df.empty:
    raise RuntimeError("No data found for any Rotterdam sensor in the past 6 weeks.")

df = df.set_index("timestamp").sort_index()

# ---- Make LAeq / LAmax / LAmin plot ----
plt.figure(figsize=(10,4))
if "LAeq" in df.columns:
    df["LAeq"].plot(label="LAeq", color="blue")
if "LAmax" in df.columns:
    df["LAmax"].plot(label="LAmax", color="red", alpha=0.6)
if "LAmin" in df.columns:
    df["LAmin"].plot(label="LAmin", color="green", alpha=0.6)
plt.title(f"Weekly Noise – Sensor {SENSOR_ID}\n{monday} to {sunday}")
plt.ylabel("dB(A)")
plt.xlabel("Time")
plt.grid(True)
plt.legend()
plt.tight_layout()
plot_file = os.path.join(REPORTS_DIR, "weekly_plot.png")
plt.savefig(plot_file, dpi=150)
plt.close()

# ---- Create PDF ----
pdf_file = os.path.join(REPORTS_DIR, f"weekly_report_{SENSOR_ID}.pdf")
doc = SimpleDocTemplate(pdf_file)
styles = getSampleStyleSheet()
story = [
    Paragraph(f"Weekly Noise Report – Sensor {SENSOR_ID}", styles["Title"]),
    Paragraph(f"Period: {monday} – {sunday}", styles["Normal"]),
    Spacer(1,20),
    Image(plot_file, width=500, height=200)
]
doc.build(story)

print(f"✅ PDF report created: {pdf_file}")
