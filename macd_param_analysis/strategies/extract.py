from typing import Any
import logging
import math
from datetime import timedelta

import pandas as pd

logger = logging.getLogger(__name__)


# ===== Constant mapper =====
CORE_METRICS = {
    # Performance
    "Total Return [%]": "total_return_pct",
    "Benchmark Return [%]": "benchmark_return_pct",

    # Risk-adjusted
    "Sharpe Ratio": "sharpe",
    "Calmar Ratio": "calmar",
    "Sortino Ratio": "sortino",
    "Omega Ratio": "omega",

    # Drawdown
    "Max Drawdown [%]": "max_dd_pct",
    "Max Drawdown Duration": "max_dd_duration",

    # Trading quality
    "Win Rate [%]": "win_rate_pct",
    "Profit Factor": "profit_factor",
    "Expectancy": "expectancy",
    "Total Trades": "total_trades",
    "Total Fees Paid": "total_fees_paid",
}


# ===== Metric extraction function =====
def extract_metrics(
    stats: dict[str, Any]
) -> dict[str, float | None | str]:
    """
    Extract core metrics from the given stats dictionary.

    Each core metric is normalized into a database-safe representation. If a metric is missing,
    invalid, NaN, or infinite, its numeric value is set to None and an additional companion key
    with the suffix '_kind' is added to describe the original semantic state of the value.

    Metric encoding lookup table:

    +------------+-------------------------------+---------------------------+
    | kind       | Meaning                       | Reconstructable to float  |
    +------------+-------------------------------+---------------------------+
    | value      | Finite numeric value          | Yes (stored value)        |
    | pos_inf    | Positive infinity (+∞)        | Yes (float('inf'))        |
    | neg_inf    | Negative infinity (-∞)        | Yes (float('-inf'))       |
    | nan        | Not-a-Number                  | Yes (float('nan'))        |
    | missing    | Metric not present in stats   | No                        |
    | invalid    | Value not castable to float   | No                        |
    +------------+-------------------------------+---------------------------+

    :param stats: A dictionary containing various statistics from the simulation.
    :type stats: dict[str, Any]
    :return: A dictionary containing normalized core metrics and their '_kind' descriptors.
    :rtype: dict[str, float | None | str]
    """
    out: dict[str, float | None | str] = {}

    for name, alias in CORE_METRICS.items():
        raw = stats.get(name, None)

        kind = "value"
        value_f: float | None = None

        if raw is None:
            kind = "missing"
        else:
            try:
                if alias == "max_dd_duration":
                    if isinstance(raw, pd.Timedelta):
                        value_f = raw.total_seconds()
                    elif isinstance(raw, timedelta):
                        value_f = raw.total_seconds()
                    else:
                        value_f = float(raw)
                else:
                    value_f = float(raw)
                if math.isnan(value_f):
                    kind = "nan"
                    value_f = None
                elif math.isinf(value_f):
                    kind = "pos_inf" if value_f > 0 else "neg_inf"
                    value_f = None
            except Exception:
                kind = "invalid"
                value_f = None

        out[alias] = value_f
        out[f"{alias}_kind"] = kind

    return out


def reconstruct_metrics(
    encoded: dict[str, float | None | str],
    *,
    drop_unrecoverable: bool = False,
) -> dict[str, float | timedelta | None]:
    """
    Reconstruct original float metrics from an encoded metrics dictionary.

    The function expects a pair-wise encoding:
        <alias>        -> float | None
        <alias>_kind   -> str

    Supported kinds:
        - "value"
        - "pos_inf"
        - "neg_inf"
        - "nan"
        - "missing"
        - "invalid"

    :param encoded: Dictionary produced by `extract_metrics`
    :param drop_unrecoverable: If True, metrics with kind 'missing' or 'invalid'
                               are omitted from the result. If False, they are
                               returned as None.
    :return: Dictionary mapping metric aliases to reconstructed float values
    """
    result: dict[str, float | timedelta | None] = {}

    for key, value in encoded.items():
        if key.endswith("_kind"):
            continue

        kind_key = f"{key}_kind"
        kind = encoded.get(kind_key, "value")

        if kind == "value":
            if value is not None:
                if key == "max_dd_duration":
                    result[key] = timedelta(seconds=float(value))
                else:
                    result[key] = float(value)

        elif kind == "pos_inf":
            result[key] = float("inf")

        elif kind == "neg_inf":
            result[key] = float("-inf")

        elif kind == "nan":
            result[key] = float("nan")

        elif kind in {"missing", "invalid"}:
            if not drop_unrecoverable:
                result[key] = None  # type: ignore[assignment]

        else:
            raise ValueError(f"Unknown metric kind '{kind}' for key '{key}'")

    return result
