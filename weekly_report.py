    # ---- HTML with PDF button ----
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Weekly Noise Report – Sensor {sensor_id}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; }}
    h1 {{ color: #2c3e50; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
    th {{ background-color: #f4f4f4; }}
    img {{ max-width: 100%; margin-top: 20px; border: 1px solid #ddd; }}
    .btn {{ display:inline-block; padding:10px 15px; margin:10px 0;
           background:#2c3e50; color:#fff; text-decoration:none;
           border-radius:5px; }}
  </style>
</head>
<body>
  <h1>Weekly Noise Report</h1>
  <h2>Sensor {sensor_id}</h2>
  <p>Generated on {datetime.now(TZ).strftime("%Y-%m-%d %H:%M")}</p>
  <a class="btn" href="#" onclick="window.print()">Download PDF</a>
  <h2>Summary</h2>
  {summary.to_html(index=False)}
  <h2>Weekly Noise Graph</h2>
  <img src="weekly_noise.png"/>
  <h2>Exceedance Heatmap</h2>
  <img src="exceedance_heatmap.png"/>
</body>
</html>
"""

    html_file = os.path.join(sensor_dir, "weekly_report.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Report generated for sensor {sensor_id} → {html_file}")
