import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import numpy as np

# Example: load your dataframe here
# df = pd.read_csv("noise_data.csv", parse_dates=["timestamp"])

# --- CONFIG ---
DAY_START = 7   # 07:00 daytime start
NIGHT_START = 23  # 23:00 night start
DAY_THRESHOLD = 55
NIGHT_THRESHOLD = 45

# --- ANALYSIS FUNCTION ---
def analyze(df, metric):
    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["is_day"] = (df["hour"] >= DAY_START) & (df["hour"] < NIGHT_START)

    # Day & Night averages
    day_avg = df.loc[df["is_day"], metric].mean()
    night_avg = df.loc[~df["is_day"], metric].mean()

    # Minutes above thresholds
    minutes_day_thr = (df.loc[df["is_day"], metric] > DAY_THRESHOLD).sum()
    minutes_night_thr = (df.loc[~df["is_day"], metric] > NIGHT_THRESHOLD).sum()

    # Noise events (consecutive > threshold)
    thr = DAY_THRESHOLD if metric != "noise_LAmin" else NIGHT_THRESHOLD  # just for consistency
    df["above"] = df[metric] > thr
    df["block"] = (df["above"] != df["above"].shift()).cumsum()
    events = df[df["above"]].groupby("block").size()

    n_events = len(events)
    avg_event_dur = events.mean() if n_events > 0 else 0
    max_event_dur = events.max() if n_events > 0 else 0

    return {
        "Metric": metric,
        "Daytime Average": round(day_avg, 1),
        "Nighttime Average": round(night_avg, 1),
        "Minutes Above Daytime Threshold": int(minutes_day_thr),
        "Minutes Above Nighttime Threshold": int(minutes_night_thr),
        "Number of Noise Events": int(n_events),
        "Average Event Duration (minutes)": round(avg_event_dur, 1),
        "Maximum Event Duration (minutes)": int(max_event_dur),
    }

# --- PLOTTING FUNCTIONS ---
def plot_heatmap(df, metric="noise_LAmin"):
    df = df.copy()
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    pivot = df.pivot_table(values=metric, index="hour", columns="date", aggfunc="mean")

    cmap = mcolors.LinearSegmentedColormap.from_list("noise", ["green", "yellow", "red", "darkred"])
    norm = mcolors.BoundaryNorm([40, 50, 60, 70, 100], cmap.N)

    fig, ax = plt.subplots(figsize=(10, 6))
    c = ax.imshow(pivot.values, aspect="auto", cmap=cmap, norm=norm, origin="lower")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([pd.to_datetime(str(d)).strftime("%a %d") for d in pivot.columns], rotation=45)
    ax.set_yticks(range(0, 24, 2))
    ax.set_yticklabels(range(0, 24, 2))
    ax.set_ylabel("Hour of Day")
    ax.set_title(f"Weekly Heatmap of {metric}")
    fig.colorbar(c, ax=ax, label="dB")
    plt.tight_layout()
    plt.show()


def plot_weekly_line(df, metric="noise_LAmin"):
    daily = df.groupby(df["timestamp"].dt.date)[metric].mean()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(daily.index, daily.values, marker="o", color="darkgreen")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d"))
    plt.xticks(rotation=45)
    ax.set_ylabel("dB")
    ax.set_title(f"Daily Average {metric}")
    plt.tight_layout()
    plt.show()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Example dummy data for demonstration
    rng = pd.date_range("2025-08-18", periods=7*24*12, freq="5min")
    df = pd.DataFrame({
        "timestamp": rng,
        "noise_LAmin": np.random.normal(50, 5, len(rng)),
        "noise_LAeq": np.random.normal(55, 5, len(rng)),
        "noise_LAmax": np.random.normal(65, 5, len(rng)),
    })

    # --- Summary Table ---
    summary = pd.DataFrame([
        analyze(df, "noise_LAmin"),
        analyze(df, "noise_LAeq"),
        analyze(df, "noise_LAmax"),
    ])

    print("\nSummary Table:\n", summary)

    # --- Plots for LAmin only ---
    plot_heatmap(df, "noise_LAmin")
    plot_weekly_line(df, "noise_LAmin")
