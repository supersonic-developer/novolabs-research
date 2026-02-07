import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib.pyplot as plt
import polars as pl

from src.data_loader import load_macd_results_by_window
from src.metrics import (
    compute_top_n_centroid,
    get_top_n_set,
    compute_convex_hull_volume
)


logger = logging.getLogger(__name__)


# ----- Centroid Shift Analysis -----
def plot_centroid_drift(
    parquet_path: str,
    metric: str,
    top_pct: float,
    fig_dir: str
):
    windows = load_macd_results_by_window(parquet_path)

    records: list[dict[str, Any]] = []

    for (_, end), df in windows.items():
        centroid, disp = compute_top_n_centroid(df, metric, top_pct)

        records.append({
            "end_date": end,
            **centroid,
            **disp,
        })

    df = pl.DataFrame(records).sort("end_date")

    plt.figure(figsize=(9, 5))
    plt.plot(df["end_date"], df["fast"], label="Fast centroid")
    plt.plot(df["end_date"], df["signal"], label="Signal centroid")
    plt.plot(df["end_date"], df["slow"], label="Slow centroid")

    plt.title(f"Centroid drift (top {int(top_pct*100)}%) – {metric}")
    plt.ylabel("Parameter value")
    plt.legend()
    plt.tight_layout()

    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(Path(fig_dir) / f"centroid_drift_{metric}.svg", dpi=150)
    plt.close()

    logger.info(f"Centroid drift plot for metric '{metric}' saved to {fig_dir}")


def plot_centroid_norm_drift(
    parquet_path: str,
    metric: str,
    top_pct: float,
    fig_dir: str
):
    windows = load_macd_results_by_window(parquet_path)
    window_keys = sorted(windows.keys(), key=lambda x: x[0])

    prev_centroid = None
    drifts: list[float] = []
    times: list[datetime] = []

    for (_, end), df in [(k, windows[k]) for k in window_keys]:
        centroid, _ = compute_top_n_centroid(df, metric, top_pct)

        curr = np.array([
            centroid["fast"],
            centroid["slow"],
            centroid["signal"],
        ])

        if prev_centroid is not None:
            drift = np.linalg.norm(curr - prev_centroid)
            drifts.append(drift)
            times.append(end)

        prev_centroid = curr

    plt.figure(figsize=(9, 4))
    plt.plot(times, drifts, marker="o")

    plt.ylabel("Centroid drift norm (L2)")
    plt.xlabel("Window end date")

    plt.title(
        f"3D centroid drift magnitude (top {int(top_pct*100)}%)\n"
        f"Metric: {metric}"
    )

    plt.tight_layout()
    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(
        Path(fig_dir) / f"centroid_norm_drift_{metric}.svg",
        dpi=150
    )
    plt.close()

    logger.info(f"Centroid norm drift plot for metric '{metric}' saved to {fig_dir}")


def plot_top_n_overlap(
    parquet_path: str,
    metric: str,
    top_pct: float,
    fig_dir: str
):
    windows = load_macd_results_by_window(parquet_path)

    window_keys = sorted(windows.keys(), key=lambda x: x[0])

    overlaps: list[float] = []
    times: list[datetime] = []

    prev_set = None

    for (start, end) in window_keys:
        df = windows[(start, end)]
        curr_set = get_top_n_set(df, metric, top_pct)

        if prev_set is not None:
            overlap_ratio = len(prev_set & curr_set) / len(prev_set)
            overlaps.append(overlap_ratio)
            times.append(end)

        prev_set = curr_set

    plt.figure(figsize=(9, 4))
    plt.plot(times, overlaps, marker="o")

    plt.ylim(0, 1)
    plt.ylabel("Top N% overlap")
    plt.xlabel("Window end date")

    plt.title(
        f"Temporal stability of top {int(top_pct*100)}% MACD parameters\n"
        f"Metric: {metric}"
    )

    plt.tight_layout()
    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(
        Path(fig_dir) / f"top_{int(top_pct*100)}pct_overlap_{metric}.svg",
        dpi=150
    )
    plt.close()

    logger.info(f"Top {int(top_pct*100)}% overlap plot for metric '{metric}' saved to {fig_dir}")


# ----- Convex Hull Shape Analysis -----
def plot_convex_hull_volume_drift(
    parquet_path: str,
    metric: str,
    top_pct: float,
    fig_dir: str
):
    windows = load_macd_results_by_window(parquet_path)
    window_keys = sorted(windows.keys(), key=lambda x: x[0])

    volumes: list[float] = []
    times: list[datetime] = []

    for (start, end) in window_keys:
        df = windows[(start, end)]
        volume = compute_convex_hull_volume(df, metric, top_pct)

        volumes.append(volume)
        times.append(end)

    plt.figure(figsize=(9, 4))
    plt.plot(times, volumes, marker="o")

    plt.ylabel("Convex hull volume")
    plt.xlabel("Window end date")

    plt.title(
        f"Top {int(top_pct*100)}% convex hull volume over time\n"
        f"Metric: {metric}"
    )

    plt.tight_layout()
    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(
        Path(fig_dir) / f"convex_hull_volume_{metric}.svg",
        dpi=150
    )
    plt.close()

    logger.info(f"Convex hull volume plot for metric '{metric}' saved to {fig_dir}")
