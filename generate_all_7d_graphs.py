import os
import pandas as pd
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
import plotly.graph_objects as go

# ---------------
# CONFIGURATION
# ---------------
INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "-_P87rOiwYwhU5CrKstQ-Y9vCrwvRvGXSicCXYSJZUpvAY-t-HUDsDNNbbfU2VKB0a3x7o5j2caulJ4euo1M0w=="    # Replace with your token
INFLUX_ORG = "Overview"                    # Replace with your org
INFLUX_BUCKET = "sensor-data"                 # Replace with your bucket
MEASUREMENT = "noise"
FIELD = "LAeq"

# List of sensor chip_ids
chip_ids = [
    13492675, 4697349, 13485578, 6365646, 13486994, 13490756, 7974125,
    6564283, 7366586, 1165775, 4498201, 13491599, 15180296, 13491199,
    13485069, 8292136, 13487297, 13492648, 13485694, 976045, 7874199,
    6563185, 13487070, 13491187, 13492369, 13261816, 15188288, 7811716,
    13491144, 13491372, 94695, 94686, 94687, 94448, 94688, 94449, 94689,
    94693, 94284, 94696, 94735, 94701, 94447, 94692
]

# Create output folder if not exists
output_folder = "graphs"
os.makedirs(output_folder, exist_ok=True)

# Define time range: last 7 full days (exclude today)
end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
start = end - timedelta(days=7)
start_str = start.isoformat() + "Z"
end_str = end.isoformat() + "Z"

# Connect InfluxDB client once
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

def query_sensor_data(chip_id):
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start_str}, stop: {end_str})
      |> filter(fn: (r) => r["_measurement"] == "{MEASUREMENT}")
      |> filter(fn: (r) => r["chip_id"] == "{chip_id}")
      |> filter(fn: (r) => r["_field"] == "{FIELD}")
      |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
      |> yield(name: "mean")
    '''
    tables = query_api.query_data_frame(query)
    if isinstance(tables, list):
        df = pd.concat(tables)
    else:
        df = tables
    if df.empty:
        return None
    df = df[["_time", "_value"]].rename(columns={"_time": "time", "_value": "LAeq"})
    df["time"] = pd.to_datetime(df["time"])
    return df

def generate_graph(df, chip_id):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["time"],
        y=df["LAeq"],
        mode="lines+markers",
        name="LAeq (dB)",
        line=dict(color="blue", width=2)
    ))

    # Night shading (22:00 - 07:00) per day
    for i in range(7):
        night_start = start + timedelta(days=i, hours=22)
        night_end = start + timedelta(days=i+1, hours=7)
        fig.add_vrect(
            x0=night_start, x1=night_end,
            fillcolor="rgba(200, 200, 200, 0.3)",
            line_width=0,
            layer="below"
        )

    fig.update_layout(
        title=f"Weekly Noise Level (LAeq) – Sensor {chip_id}",
        xaxis_title="Time",
        yaxis_title="LAeq (dB)",
        template="plotly_white",
        height=600,
        width=1000,
        margin=dict(l=60, r=40, t=80, b=50)
    )

    filename_html = os.path.join(output_folder, f"sensor_{chip_id}_7d.html")
    fig.write_html(filename_html)
    print(f"Generated {filename_html}")

# --------------------
# Main loop: generate graphs for all sensors
# --------------------
for chip_id in chip_ids:
    print(f"Processing sensor {chip_id}...")
    df_sensor = query_sensor_data(str(chip_id))
    if df_sensor is None:
        print(f"⚠ No data for sensor {chip_id}, skipping.")
        continue
    generate_graph(df_sensor, chip_id)

client.close()
print("✅ All done!")
