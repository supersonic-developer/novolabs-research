import logging

import numpy as np
from scipy.stats import (
    gaussian_kde,
    skew,
    kurtosis
)
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt
import polars as pl

from schemas import MarketData


logger = logging.getLogger(__name__)


def btc_return_distribution_analysis(
    market_data: list[MarketData],
    out_path: str
) -> None:
    """
    Analyse log returns by skewness, kurtosis, upside & downside volatility and plots BTC log-return distribution with upside / downside KDE and saves it as an SVG.
    """
    # --- 1. Close prices ---
    closes = np.array([md.close for md in market_data], dtype=float)

    # --- 2. Log returns ---
    log_returns = np.diff(np.log(closes))

    # Drop NaNs / inf just in case
    log_returns = log_returns[np.isfinite(log_returns)]

    sk = skew(log_returns)
    ex_kurt = kurtosis(log_returns, fisher=True)  # fisher=True → excess kurtosis

    logger.info(f"Skewness: {sk:.2f}")
    logger.info(f"Excess kurtosis: {ex_kurt:.2f}")

    upside = log_returns[log_returns > 0]
    downside = log_returns[log_returns < 0]

    # --- 2.1 Upside / Downside volatility ---
    sigma_up = np.std(upside, ddof=1)
    sigma_down = np.std(downside, ddof=1)

    ratio = sigma_up / sigma_down if sigma_down > 0 else np.nan

    logger.info(f"Upside volatility (σ+): {sigma_up:.6f}")
    logger.info(f"Downside volatility (σ-): {sigma_down:.6f}")
    logger.info(f"σ+ / σ- ratio: {ratio:.2f}")

    # --- 3. KDE ---
    x_min, x_max = np.percentile(log_returns, [0.5, 99.5])
    x = np.linspace(x_min, x_max, 1000)

    kde_all = gaussian_kde(log_returns)
    kde_up = gaussian_kde(upside)
    kde_down = gaussian_kde(downside)

    # --- 4. Plot ---
    plt.figure(figsize=(10, 5))

    plt.plot(x, kde_all(x), label="Total return distribution", linewidth=2)
    plt.plot(x, kde_up(x), label="Upside returns", linestyle="--")
    plt.plot(x, kde_down(x), label="Downside returns", linestyle="--")

    plt.axvline(0.0, linewidth=1, linestyle=":")

    mean_return = np.mean(log_returns)
    plt.axvline(mean_return, linestyle=":", linewidth=1, label="Mean return")

    plt.title("BTC-USD Log-Return Distribution\nUpside vs Downside Volatility")
    plt.xlabel("Log return")
    plt.ylabel("Density")

    plt.legend()
    plt.tight_layout()

    # --- 5. Save SVG ---
    plt.savefig(out_path, format="svg")
    plt.close()

    logger.info(f"BTC log-return distribution plot saved to {out_path}")


def compute_top_n_centroid(
    df: pl.DataFrame,
    metric: str,
    top_pct: float,
) -> tuple[dict[str, float], dict[str, float]]:
    threshold = df[metric].quantile(1 - top_pct)

    top = df.filter(pl.col(metric) >= threshold)

    centroid = {
        "fast": float(top["fast_period"].mean()),
        "slow": float(top["slow_period"].mean()),
        "signal": float(top["signal_period"].mean()),
    }

    dispersion = {
        "fast_std": float(top["fast_period"].std()),
        "slow_std": float(top["slow_period"].std()),
        "signal_std": float(top["signal_period"].std()),
    }

    return centroid, dispersion


def get_top_n_set(
    df: pl.DataFrame,
    metric: str,
    top_pct: float,
) -> set[tuple[int, int, int]]:
    threshold = df[metric].quantile(1 - top_pct)

    top = df.filter(pl.col(metric) >= threshold)

    return set(
        zip(
            top["fast_period"].to_list(),
            top["slow_period"].to_list(),
            top["signal_period"].to_list(),
        )
    )


def compute_convex_hull_volume(
    df: pl.DataFrame, 
    metric: str, 
    top_pct: float
) -> float:
    threshold = df[metric].quantile(1 - top_pct)
    top = df.filter(pl.col(metric) >= threshold)

    points = np.column_stack([
        top["fast_period"],
        top["slow_period"],
        top["signal_period"],
    ])

    if len(points) < 4:
        return np.nan

    hull = ConvexHull(points)
    return hull.volume
