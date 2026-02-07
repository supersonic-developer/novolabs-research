from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import polars as pl

from schemas import (
    MarketData,
    MACDHistogramSignFlipStrategy,
    DataConfig
)
from strategies import reconstruct_metrics


async def load_market_data(
    session: AsyncSession, 
    data_config: DataConfig
) -> list[MarketData]:
    """
    Loads market data from DB for given DATA_CONFIG.
    """
    result = await session.execute(
        select(MarketData).where(
            MarketData.asset == data_config.asset,
            MarketData.source == data_config.source,
            MarketData.timeframe == data_config.timeframe,
            MarketData.timestamp >= data_config.start_date,
            MarketData.timestamp < data_config.end_date,
        )
    )

    return sorted(list(result.scalars().all()))


async def convert_db_records_to_parquet(
    session: AsyncSession,
    window_size_days: int,
    out_path: str,
    data_config: DataConfig
) -> None:
    """
    Converts MACD strategy results from DB to Parquet format. Keeps only fast, slow, signal periods, start_date, end_date and reconstructed metrics.
    """
    stmt = (
        select(
            MACDHistogramSignFlipStrategy.fast_period,
            MACDHistogramSignFlipStrategy.slow_period,
            MACDHistogramSignFlipStrategy.signal_period,
            MACDHistogramSignFlipStrategy.start_date,
            MACDHistogramSignFlipStrategy.end_date,
            MACDHistogramSignFlipStrategy.metrics,
        )
        .where(
            func.date_part(
                "day",
                MACDHistogramSignFlipStrategy.end_date
                - MACDHistogramSignFlipStrategy.start_date
            ) == window_size_days,
            MACDHistogramSignFlipStrategy.asset == data_config.asset,
            MACDHistogramSignFlipStrategy.timeframe == data_config.timeframe
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    records: list[dict[str, Any]] = []
    for r in rows:
        reconstructed_metrics = reconstruct_metrics(r.metrics)

        rec: dict[str, Any] = {
            "fast_period": r.fast_period,
            "slow_period": r.slow_period,
            "signal_period": r.signal_period,

            "start_date": r.start_date,
            "end_date": r.end_date,
        }

        for key, value in reconstructed_metrics.items():
            rec[key] = value

        records.append(rec)

    df = pl.DataFrame(records).with_columns([
        pl.col("fast_period").cast(pl.UInt8),
        pl.col("slow_period").cast(pl.UInt8),
        pl.col("signal_period").cast(pl.UInt8),
    ])
    df.write_parquet(out_path)


def load_macd_results_by_window(
    parquet_path: str
) -> dict[tuple[datetime, datetime], pl.DataFrame]:
    """
    Loads MACD strategy results from parquet and groups them by (start_date, end_date) window.
    """
    df = pl.read_parquet(parquet_path)

    windows: dict[tuple[datetime, datetime], pl.DataFrame] = {}

    for (start, end), subdf in df.group_by(["start_date", "end_date"]):
        windows[(start, end)] = subdf

    return windows
