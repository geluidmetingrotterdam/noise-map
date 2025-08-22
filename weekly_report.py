import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# ---- Settings ----
SENSOR_ID = 89747
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

# Define last Monday–Sunday
today = datetime.utcnow().date()
last_monday = today - timedelta(days=today.weekday() + 7)
last_sunday = last_monday + timedelta(days=6)

print(f"Generating report for {last_monday} → {last_sunday}")

# ---- Download daily CSVs and combine ----
dfs = []
for i in range(7):
    day = last_monday + timedelta(days=i)
    url = f"https://archive.sensor.community/{day.strftime('%Y-%m-%d')}/{SENSOR_ID}_noise.csv"
    print(f"Fetching {url}")
    resp = requests.get(url)
    if resp.status_code == 200:
        tmp_path = os.path.join(REPORTS_DIR, f"{SENSOR_ID}_{day}.csv")
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        try:
            df_day = pd.read_csv(tmp_path, sep=";")
            df_day["timestamp"] = pd.to_datetime(df_day["timestamp"])
            dfs.append(df_day)
        except Exception as e:
            print(f"⚠️ Could not parse {url}: {e}")
    else:
        print(f"❌ No data for {day}")

if not dfs:
    raise RuntimeError("No data downloaded for the selected week!")

df = pd.concat(dfs)
df = df.set_index("timestamp").sort_index()

# ---- Make plot ----
plt.figure(figsize=(10, 4))
df["dBA"].plot(title=f"Noise levels for sensor {SENSOR_ID}\n{last_monday} – {last_sunday}")
plt.ylabel("dBA")
plot_path = os.path.join(REPORTS_DIR, "plot.png")
plt.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close()

# ---- Create PDF ----
pdf_path = os.path.join(REPORTS_DIR, f"weekly_report_{SENSOR_ID}.pdf")
doc = SimpleDocTemplate(pdf_path)
styles = getSampleStyleSheet()
story = [
    Paragraph(f"Weekly Report for Sensor {SENSOR_ID}", styles["Title"]),
    Paragraph(f"Period: {last_monday} – {last_sunday}", styles["Normal"]),
    Spacer(1, 20),
    Image(plot_path, width=500, height=200)
]
doc.build(story)

print(f"✅ Report saved to {pdf_path}")
