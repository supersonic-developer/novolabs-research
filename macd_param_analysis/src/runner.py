import logging
import asyncio
from dataclasses import asdict

import vectorbt as vbt  # type: ignore
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

import strategies.macd as macd
from strategies import extract_metrics
from schemas import (
    MACDHistogramSignFlipStrategy,
    MarketData,
    SimulationConfig,
    YF2PANDAS_FREQ_MAP,
    MACDParams
)


logger = logging.getLogger(__name__)


# ==== Public API =====
def batch_runner(batch: list[MACDHistogramSignFlipStrategy], full_data: list[MarketData], timeframe: str) -> list[MACDHistogramSignFlipStrategy]:
    result_batch: list[MACDHistogramSignFlipStrategy] = []
    for sim in batch:
        result = _run_single_simulation_for_MACD(sim, full_data, timeframe)
        result_batch.append(result)

    return result_batch


async def db_worker(
    queue: asyncio.Queue[MACDHistogramSignFlipStrategy | None], 
    async_session_maker: async_sessionmaker[AsyncSession], 
    max_bulk_insert: int
):
    """
    Asynchronous worker that processes simulation results from the queue and saves them to the database.

    :param queue: An asyncio Queue containing simulation results
    :type queue: asyncio.Queue[MACDHistogramSignFlipStrategy | None]
    :param async_session_maker: An asynchronous database session maker
    :type async_session_maker: async_sessionmaker[AsyncSession]
    :param max_bulk_insert: Maximum number of records to insert in a single bulk operation
    :type max_bulk_insert: int
    """
    try:
        logger.info("DB worker started.")
        buffer: list[MACDHistogramSignFlipStrategy] = []

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=3)
            except asyncio.TimeoutError:
                continue
            
            # Sentinel value to indicate completion
            if item is None:
                queue.task_done()
                break

            buffer.append(item)

            if len(buffer) >= max_bulk_insert:
                async with async_session_maker() as session, session.begin():
                    await session.execute(
                        insert(MACDHistogramSignFlipStrategy),
                        [asdict(sim) for sim in buffer]
                    )
                buffer.clear()
                logger.info(f"Inserted {max_bulk_insert} simulation results into the database.")

        logger.info("DB worker received shutdown signal. Inserting remaining records...")

        # Remainings
        if buffer:
            async with async_session_maker() as session, session.begin():
                await session.execute(
                    insert(MACDHistogramSignFlipStrategy),
                    [asdict(sim) for sim in buffer]
                )
            logger.info(f"Inserted remaining {len(buffer)} simulation results into the database.")

    except Exception as e:
        logger.error(f"Error in DB worker: {e}")


# ==== Internal Methods =====
def _run_single_simulation_for_MACD(
    macd_histogram_sign_flip_strategy: MACDHistogramSignFlipStrategy,
    full_data: list[MarketData],
    timeframe: str,
) -> MACDHistogramSignFlipStrategy:
    """
    Runs a single simulation for the MACD Histogram Sign Flip Strategy with the given parameters.
    NOTE: Execution time is around 0.04-0.05 seconds per simulation on average.

    :param macd_histogram_sign_flip_strategy: The MACD histogram sign-flip strategy configuration
    :type macd_histogram_sign_flip_strategy: MACDHistogramSignFlipStrategy
    :param full_data: The full market data for the asset and timeframe
    :type full_data: list[MarketData]
    :param timeframe: The timeframe string (e.g., '1d', '1h')
    :type timeframe: str
    :return: The MACDHistogramSignFlipStrategy object with populated metrics
    :rtype: MACDHistogramSignFlipStrategy
    """
    extended_period = full_data[
        macd_histogram_sign_flip_strategy.start_idx : macd_histogram_sign_flip_strategy.end_idx
    ]
    macd_params = MACDParams(
        fast=macd_histogram_sign_flip_strategy.fast_period,
        slow=macd_histogram_sign_flip_strategy.slow_period,
        signal=macd_histogram_sign_flip_strategy.signal_period,
    )

    entries, exits, simulation_period = macd.generate_MACD_histogram_sign_flip_signals(extended_period, macd_params)
    logger.info(f"Running simulation {macd_histogram_sign_flip_strategy}...")

    vbt_portfolio = vbt.Portfolio.from_signals(     # type: ignore
        close=simulation_period,
        entries=entries,
        exits=exits,
        init_cash=SimulationConfig.initial_cash,
        fees=SimulationConfig.fee,
        slippage=SimulationConfig.slippage,
        freq=YF2PANDAS_FREQ_MAP[timeframe],
    )

    macd_histogram_sign_flip_strategy.metrics = extract_metrics(vbt_portfolio.stats().to_dict())  # type: ignore
    return macd_histogram_sign_flip_strategy