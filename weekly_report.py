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

# Download CSV from Sensor.Community archive
url = f"https://archive.sensor.community/{last_monday.strftime('%Y-%m-%d')}/{SENSOR_ID}_noise.csv"
resp = requests.get(url)
if resp.status_code != 200:
    raise RuntimeError(f"Could not download data: {url}")

# Save and load CSV
csv_path = os.path.join(REPORTS_DIR, f"{SENSOR_ID}_data.csv")
with open(csv_path, "wb") as f:
    f.write(resp.content)

df = pd.read_csv(csv_path, sep=";")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.set_index("timestamp")
df = df[(df.index.date >= last_monday) & (df.index.date <= last_sunday)]

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
