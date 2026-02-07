import os
import logging
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl
import plotly.express as px
import seaborn as sns

from src.data_loader import load_macd_results_by_window


logger = logging.getLogger(__name__)


# ----- Static 3D Scatter Plots -----
def plot_macd_parameter_cloud(
    df: pl.DataFrame,
    window_key: tuple[datetime, datetime],
    metric: str,
    fig_dir: str,
) -> None:
    """
    Plots a 3D scatter of MACD parameters for a single window.

    Axes:
        X: fast_period
        Y: slow_period
        Z: signal_period

    Color:
        given performance metric
    """
    start_date, end_date = window_key

    x = df["fast_period"].to_numpy()
    y = df["slow_period"].to_numpy()
    z = df["signal_period"].to_numpy()
    c = df[metric].to_numpy()

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    sc = ax.scatter(
        x, y, z,
        c=c,
        s=12,
        alpha=0.8
    )

    ax.set_xlabel("Fast period")
    ax.set_ylabel("Slow period")
    ax.set_zlabel("Signal period")

    title = (
        f"MACD Parameter Cloud\n"
        f"{start_date.date()} → {end_date.date()}"
    )
    ax.set_title(title)

    cb = plt.colorbar(sc, ax=ax, pad=0.1)
    cb.set_label(metric)

    plt.tight_layout()

    fname = (
        f"macd_param_cloud_"
        f"{start_date.date()}_{end_date.date()}.svg"
    )
    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.savefig(os.path.join(fig_dir, fname), dpi=150)
    plt.close()


def generate_all_parameter_clouds(
    parquet_path: str,
    metric: str,
    fig_dir: str
) -> None:
    """
    Generates static 3D scatter plots of MACD parameters for all windows.
    """
    windows = load_macd_results_by_window(parquet_path)

    structural_dir = f"{fig_dir}/static/{metric}"

    for window_key, df in windows.items():
        plot_macd_parameter_cloud(
            df=df,
            window_key=window_key,
            metric=metric,
            fig_dir=structural_dir
        )

    logger.info(f"Static MACD parameter clouds for metric '{metric}' saved to {structural_dir}")


# ----- Interactive 3D Scatter Plots -----
def plot_macd_parameter_cloud_interactive(
    df: pl.DataFrame,
    window_key: tuple[datetime, datetime],
    metric: str,
    fig_dir: str,
) -> None:
    """
    Interactive 3D scatter plot of MACD parameters.
    Color = raw metric value (NO ranking, NO normalization).
    """
    start_date, end_date = window_key

    pdf = df.to_pandas()

    fig = px.scatter_3d(
        pdf,
        x="fast_period",
        y="slow_period",
        z="signal_period",
        color=metric,
        color_continuous_scale="Viridis",
        opacity=0.85,
        title=(
            f"MACD Parameter Cloud<br>"
            f"{start_date.date()} → {end_date.date()}"
        ),
    )

    fig.update_layout(
        scene=dict(
            xaxis_title="Fast period",
            yaxis_title="Slow period",
            zaxis_title="Signal period",
        ),
        margin=dict(l=0, r=0, b=0, t=40),
    )

    fname = (
        f"macd_param_cloud_"
        f"{start_date.date()}_{end_date.date()}.html"
    )

    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    fig.write_html(Path(fig_dir) / fname)


def generate_interactive_clouds(
    parquet_path: str,
    metric: str,
    fig_dir: str
) -> None:
    """
    Generates interactive 3D scatter plots of MACD parameters for all windows.
    """
    windows = load_macd_results_by_window(parquet_path)

    structural_dir = f"{fig_dir}/interactive/{metric}"

    for window_key, df in windows.items():
        plot_macd_parameter_cloud_interactive(
            df=df,
            window_key=window_key,
            metric=metric,
            fig_dir=structural_dir,
        )

    logger.info(f"Interactive MACD parameter clouds for metric '{metric}' saved to {structural_dir}")


# ----- Projection to 2D spaces -----
def plot_macd_2d_heatmap(
    df: pl.DataFrame,
    window_key: tuple[datetime, datetime],
    metric: str,
    x_param: str,
    y_param: str,
    agg: str,   # aggregation method: 'mean', 'median', etc.
    fig_dir: str,
) -> None:
    """
    2D heatmap of MACD parameter projections. The third parameter is marginalized via aggregation.
    """
    start_date, end_date = window_key

    pdf = df.to_pandas()
    pivot = pdf.groupby([x_param, y_param])[metric].agg(agg).reset_index()

    heatmap = pivot.pivot(
        index=y_param,
        columns=x_param,
        values=metric
    )

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        heatmap,
        cmap="viridis",
        cbar_kws={"label": metric}
    )

    plt.title(
        f"{metric} heatmap ({x_param} vs {y_param})\n"
        f"{start_date.date()} → {end_date.date()}"
    )
    plt.xlabel(x_param)
    plt.ylabel(y_param)

    fname = (
        f"macd_heatmap_{metric}_"
        f"{x_param}_{y_param}_"
        f"{start_date.date()}_{end_date.date()}.svg"
    )

    Path(fig_dir).mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(Path(fig_dir) / fname, dpi=150)
    plt.close()


def generate_all_heatmaps(
    parquet_path: str,
    metric: str,
    agg: str,
    fig_dir: str
) -> None:
    """
    Generates 2D heatmaps of MACD parameters for all windows.
    Creates 3 projections per window: fast-slow, fast-signal, slow-signal.
    """
    windows = load_macd_results_by_window(parquet_path)

    structural_dir = f"{fig_dir}/static_2d_projection/{metric}"

    param_pairs = [
        ("fast_period", "slow_period"),
        ("fast_period", "signal_period"),
        ("slow_period", "signal_period"),
    ]

    for window_key, df in windows.items():
        for x_param, y_param in param_pairs:
            plot_macd_2d_heatmap(
                df=df,
                window_key=window_key,
                metric=metric,
                x_param=x_param,
                y_param=y_param,
                agg=agg,
                fig_dir=structural_dir
            )

    logger.info(f"2D heatmaps for metric '{metric}' saved to {structural_dir}")
