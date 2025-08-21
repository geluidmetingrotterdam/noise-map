import os
from datetime import datetime, timedelta
import pytz
import matplotlib.pyplot as plt
from influxdb_client import InfluxDBClient
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# 🔧 InfluxDB setup
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

SENSOR_ID = "89747"
TIMEZONE = pytz.timezone("Europe/Amsterdam")

# calculate last full week (Mon–Sun)
today = datetime.now(TIMEZONE).date()
last_monday = today - timedelta(days=today.weekday() + 7)
last_sunday = last_monday + timedelta(days=6)

start_time = datetime.combine(last_monday, datetime.min.time()).astimezone(TIMEZONE)
end_time = datetime.combine(last_sunday, datetime.max.time()).astimezone(TIMEZONE)

print(f"Generating report for {SENSOR_ID} from {start_time} to {end_time}")

# query Influx
query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
  |> filter(fn: (r) => r["sensor_id"] == "{SENSOR_ID}")
  |> filter(fn: (r) => r["_measurement"] == "noise")
  |> filter(fn: (r) => r["_field"] =~ /LAeq|LAmax|LAmin/)
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> yield(name: "mean")
'''

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
tables = client.query_api().query(query)

# convert to Python dicts
data = {"_time": [], "LAeq": [], "LAmax": [], "LAmin": []}
for table in tables:
    for record in table.records:
        if record["_field"] in data:
            data["_time"].append(record["_time"])
            data[record["_field"]].append(record["_value"])

# --- Make chart ---
plt.figure(figsize=(10, 4))
if data["_time"]:
    plt.plot(data["_time"], data["LAeq"], label="LAeq")
    plt.plot(data["_time"], data["LAmax"], label="LAmax")
    plt.plot(data["_time"], data["LAmin"], label="LAmin")
    plt.legend()
    plt.title(f"Noise levels sensor {SENSOR_ID}")
    plt.xlabel("Time")
    plt.ylabel("dB(A)")
    chart_path = f"report_{SENSOR_ID}.png"
    plt.savefig(chart_path, bbox_inches="tight")
    plt.close()
else:
    chart_path = None

# --- Make PDF ---
pdf_path = f"weekly_report_{SENSOR_ID}.pdf"
doc = SimpleDocTemplate(pdf_path)
styles = getSampleStyleSheet()
elements = []

elements.append(Paragraph(f"Weekly Noise Report – Sensor {SENSOR_ID}", styles['Title']))
elements.append(Paragraph(f"Period: {last_monday} → {last_sunday}", styles['Normal']))
elements.append(Spacer(1, 12))

if chart_path:
    elements.append(Image(chart_path, width=500, height=200))

doc.build(elements)

print(f"✅ Report saved: {pdf_path}")
