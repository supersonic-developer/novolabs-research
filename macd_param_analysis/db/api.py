from datetime import datetime, timezone
from dataclasses import asdict
import logging
from typing import Iterable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
import pandas as pd
import yfinance as yf   # type: ignore

from schemas import (
    MarketData, 
    MarketAction, 
    MACDHistogramSignFlipStrategy,
    DataConfig,
    MACDParamsGrid
)
from strategies.macd import calculate_max_warmup_period


logger = logging.getLogger(__name__)


# ===== Public API =====
async def collect_data(
    session: AsyncSession,
    data_config: DataConfig,
    macd_params_grid: MACDParamsGrid
) -> list[MarketData]:
    """
    Checks the required range of market data for each asset, and downloads the missing parts.
    Note: it adds the padding required by MACD warm-up periods.

    :param session: Database session for querying and saving data
    :type session: AsyncSession
    :param data_config: Data configuration specifying source, asset, timeframe, and date range
    :type data_config: DataConfig
    :return: Sorted list of MarketData covering the required range
    :rtype: list[MarketData]
    """
    date_range = await _get_available_range(session, data_config)
    required_start_date = data_config.start_date - data_config.timeframe_td * calculate_max_warmup_period(macd_params_grid)

    # There is data available --> check if it covers the required range --> If not, download missing parts, else skip
    if date_range and all(date_range):
        available_start_date, available_end_date = date_range

        result = await session.execute(
            select(MarketData).where(
                MarketData.asset == data_config.asset,
                MarketData.source == data_config.source,
                MarketData.timeframe == data_config.timeframe,
                MarketData.timestamp >= required_start_date,
                MarketData.timestamp < data_config.end_date,
            )
        )
        market_data = list(result.scalars().all())

        # Download missing data before the available start date
        if available_start_date > required_start_date:
            data_before = await _download_data_and_save(
                session,
                required_start_date,
                available_start_date,
                data_config
            )
            market_data.extend(data_before[0])

        # Download missing data after the available end date
        if available_end_date < data_config.end_date - data_config.timeframe_td:
            data_after = await _download_data_and_save(
                session,
                available_end_date,
                data_config.end_date,
                data_config
            )
            market_data.extend(data_after[0])

    # No data available at all --> download full range
    else:
        logger.warning(f"No data available for {data_config.asset} ({data_config.timeframe}). Downloading full range.")
        data_full = await _download_data_and_save(
            session,
            required_start_date,
            data_config.end_date,
            data_config
        )
        market_data = data_full[0]
    
    return sorted(market_data)


async def get_macd_histogram_sign_flip_simulations(
    session: AsyncSession,
    data_config: DataConfig,
) -> set[MACDHistogramSignFlipStrategy]:
    """
    Runs a MACD histogram sign-flip strategy simulation for the given configuration and market data.

    :param session: Database session for storing/retrieving simulation results
    :type session: AsyncSession
    :param data_config: The data configuration
    :type data_config: DataConfig
    :return: Set of MACDHistogramSignFlipStrategy results for the given asset/timeframe
    :rtype: set[MACDHistogramSignFlipStrategy]
    """
    result = await session.execute(
        select(MACDHistogramSignFlipStrategy).where(
            MACDHistogramSignFlipStrategy.asset == data_config.asset,
            MACDHistogramSignFlipStrategy.timeframe == data_config.timeframe,
        )
    )
    results = set(result.scalars().all())
    return results


# ===== Internal Helpers =====
async def _get_available_range(
    session: AsyncSession,
    data_config: DataConfig
) -> tuple[datetime, datetime] | None:
    """
    Returns (min_timestamp, max_timestamp) for given asset/source/timeframe.
    If no data exists, returns None.

    :param session: Database session for querying data
    :type session: AsyncSession
    :param data_config: Data configuration specifying source, asset, timeframe
    :type data_config: DataConfig
    :return: Tuple of (min_timestamp, max_timestamp) or None if no data exists
    :rtype: tuple[datetime, datetime] | None
    """
    stmt = (
        select(
            func.min(MarketData.timestamp),
            func.max(MarketData.timestamp),
        )
        .where(
            MarketData.asset == data_config.asset,
            MarketData.source == data_config.source,
            MarketData.timeframe == data_config.timeframe,
        )
    )

    result = await session.execute(stmt)
    interval = result.tuples().first()

    return interval    


async def _download_data_and_save(
    session: AsyncSession,
    dw_start_date: datetime, 
    dw_end_date: datetime, 
    data_config: DataConfig
) -> tuple[list[MarketData], list[MarketAction]]:
    """
    Downloads market data from yfinance and saves it into the database through the provided session.
    
    :param session: Database session for saving data
    :type session: AsyncSession
    :param dw_start_date: Start date for downloading data
    :type dw_start_date: datetime
    :param dw_end_date: End date for downloading data
    :type dw_end_date: datetime
    :param data_config: Data configuration specifying source, asset, timeframe
    :type data_config: DataConfig
    :return: Tuple of lists containing MarketData and MarketAction objects saved
    :rtype: tuple[list[MarketData], list[MarketAction]]
    """
    logger.info(f"Downloading data for {data_config.asset} ({data_config.timeframe}) from {dw_start_date} to {dw_end_date}")
    data = yf.download(     # type: ignore
        data_config.asset,
        start=dw_start_date.strftime("%Y-%m-%d"),
        end=dw_end_date.strftime("%Y-%m-%d"),
        interval=data_config.timeframe,
        auto_adjust=False,  # Do not adjust for dividends/splits
        actions=True,       # Download dividends/splits
        progress=False,
        multi_level_index=False,
        timeout=30,
    )

    if data is None or data.empty:
        raise RuntimeError(f"Failed to download data for {data_config.asset} ({data_config.timeframe}) from {dw_start_date} to {dw_end_date}")
    
    market_data_objs: list[MarketData] = []
    market_action_objs: list[MarketAction] = []

    for ts, row in data.iterrows():   # type: ignore
        ts: pd.Timestamp

        ts_dt = ts.to_pydatetime()
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)

        market_data_objs.append(
            MarketData(
                asset=data_config.asset,
                source=data_config.source,
                timeframe=data_config.timeframe,
                timestamp=ts_dt,
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"],
            )
        )

        # MarketAction: only if there are any non-zero actions
        action_cols = ["Dividends", "Stock Splits", "Capital Gains"]
        existing_cols = [col for col in action_cols if col in row.index]

        if existing_cols and any(row[col] != 0 for col in existing_cols):
            market_action_objs.append(
                MarketAction(
                    asset=data_config.asset,
                    source=data_config.source,
                    timeframe=data_config.timeframe,
                    timestamp=ts_dt,
                    dividends=row["Dividends"] if "Dividends" in row.index else None,
                    stock_splits=row["Stock Splits"] if "Stock Splits" in row.index else None,
                    capital_gains=row["Capital Gains"] if "Capital Gains" in row.index else None,
                )
            )
            
    # Bulk insert with conflict handling
    if market_data_objs:
        # Only include actual table columns in insert
        market_data_columns = set(c.name for c in MarketData.__table__.columns)
        for chunk in chunked(market_data_objs, 1000):
            values = [
                {k: v for k, v in asdict(obj).items() if k in market_data_columns}
                for obj in chunk
            ]
            stmt = insert(MarketData).values(values).on_conflict_do_nothing(
                index_elements=["asset", "source", "timeframe", "timestamp"]
            )
            await session.execute(stmt)

    if market_action_objs:
        market_action_columns = set(c.name for c in MarketAction.__table__.columns)
        market_action_columns.discard("id")  # Exclude id so it autoincrements
        for chunk in chunked(market_action_objs, 2000):
            values = [
                {k: v for k, v in asdict(obj).items() if k in market_action_columns}
                for obj in chunk
            ]
            stmt = insert(MarketAction).values(values).on_conflict_do_nothing(
                index_elements=["asset", "source", "timeframe", "timestamp"]
            )
            await session.execute(stmt)

    return market_data_objs, market_action_objs
    

T = TypeVar("T")

def chunked(iterable: list[T], size: int) -> Iterable[list[T]]:
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]
