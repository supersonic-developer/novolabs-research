import asyncio
from typing import TypeVar, Iterable
import logging
from concurrent.futures import ProcessPoolExecutor

from src.logging_config import setup_logging
import strategies.macd as macd
from config import (
    load_data_configs,
    load_trade_execution_config,
    load_macd_params, 
    load_window_configs,
    load_code_execution_control_config,
    load_simulation_config
)
from db import (
    open_ssh_tunnel,
    collect_data,
    get_macd_histogram_sign_flip_simulations
)
from src.runner import (
    batch_runner,
    db_worker
)
from schemas import (
    DataConfig,
    ExecutionConfig,
    CodeExecutionControlConfig,
    MACDHistogramSignFlipStrategy,
    MACDParamsGrid,
    MACDWindowConfig
)


setup_logging(log_dir="logs", service_name="simulation_service", log_level="INFO")
logger = logging.getLogger(__name__)

# ===== Configurations =====
DATA_CONFIGS = load_data_configs("config/data_config.yaml")
EXECUTION_CONFIG = load_trade_execution_config("config/trade_execution_config.yaml")
MACD_PARAM_GRID = load_macd_params("config/macd_params.yaml")
MACD_WINDOW_CONFIGS = load_window_configs("config/window_configs.yaml")
CODE_EXECUTION_CONTROL = load_code_execution_control_config("config/code_execution_control.yaml")

# Entities are dynamically instantiated, so we just need to call this to set class variables
load_simulation_config("config/simulation_config.yaml")


# ===== Helpers =====
def sanitize_simulation_period_start_date() -> None:
    """
    Ensures that the simulation period start falls on the last valid whole window start.
    Note: This function modifies DATA_CONFIGS in place if necessary.
    """
    for i, data_config in enumerate(DATA_CONFIGS):
        base_start = data_config.start_date
        base_end = data_config.end_date
        max_aligned_start = base_start

        for macd_window_config in MACD_WINDOW_CONFIGS:
            total_samples = (base_end - base_start) // data_config.timeframe_td

            if total_samples < macd_window_config.window_size:
                aligned_start = base_end
            else:
                last_window_start = base_end - (data_config.timeframe_td * macd_window_config.window_size)
                shift_td = data_config.timeframe_td * macd_window_config.window_shift
                max_back_shifts = (last_window_start - base_start) // shift_td
                aligned_start = last_window_start - (max_back_shifts * shift_td)

            if aligned_start > max_aligned_start:
                max_aligned_start = aligned_start

        if max_aligned_start != base_start:
            logger.warning(
                f"Adjusting start_date for {data_config.asset} ({data_config.timeframe}) from {base_start} to {max_aligned_start} to align with window configuration(s)."
            )
            DATA_CONFIGS[i] = DataConfig(
                source=data_config.source,
                asset=data_config.asset,
                timeframe=data_config.timeframe,
                timeframe_td=data_config.timeframe_td,
                start_date=max_aligned_start,
                end_date=base_end
            )


T = TypeVar('T')

def chunked(iterable: Iterable[T], n: int) -> Iterable[list[T]]:
    """Yield successive n-sized chunks from iterable."""
    iterable = list(iterable)
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]


# ===== Main Execution =====
async def main(
    data_configs: list[DataConfig] = DATA_CONFIGS,
    execution_config: ExecutionConfig = EXECUTION_CONFIG,
    macd_params_grid: MACDParamsGrid = MACD_PARAM_GRID,
    macd_window_configs: list[MACDWindowConfig] = MACD_WINDOW_CONFIGS,
    code_execution_control: CodeExecutionControlConfig = CODE_EXECUTION_CONTROL
):
    sanitize_simulation_period_start_date()

    async with open_ssh_tunnel() as async_session_maker:
        db_worker_queue: asyncio.Queue[MACDHistogramSignFlipStrategy | None] = asyncio.Queue(code_execution_control.consumer_queue_size)
        db_worker_task = asyncio.create_task(
            db_worker(
                db_worker_queue,
                async_session_maker,
                max_bulk_insert=code_execution_control.db_bulk_insert_size
            )
        )

        try:
            for data_config in data_configs:
                try:
                    async with async_session_maker() as session, session.begin():
                        full_data = await collect_data(session, data_config, macd_params_grid)
                        existing_simulations = await get_macd_histogram_sign_flip_simulations(session, data_config)
                except Exception as e:
                    logger.error(f"Error processing data for {data_config.asset} ({data_config.timeframe}): {e}")
                    continue

                required_simulations = macd.get_all_macd_setup(
                    data_config,
                    execution_config,
                    macd_params_grid,
                    macd_window_configs,
                    full_data
                )

                missing_simulations = required_simulations - existing_simulations
                logger.info(f"For {data_config.asset} ({data_config.timeframe}), found {len(existing_simulations)} existing simulations, {len(missing_simulations)} missing simulations out of {len(required_simulations)} required simulations.")

                if not missing_simulations:
                    continue

                # ----- Process pool -----
                loop = asyncio.get_running_loop()

                with ProcessPoolExecutor(max_workers=code_execution_control.threads_to_use) as executor:
                    tasks = [
                        loop.run_in_executor(
                            executor,
                            batch_runner,
                            batch,
                            full_data,
                            data_config.timeframe
                        )
                        for batch in chunked(
                                        missing_simulations, 
                                        code_execution_control.simulation_batch_size
                                    )
                    ]

                    for coro in asyncio.as_completed(tasks):
                        batch_results = await coro
                        for result in batch_results:
                            await db_worker_queue.put(result)

        except Exception as e:
            logger.error(f"Unexpected error during simulations: {e}")

        finally:
            # Signal the db_worker to finish
            await db_worker_queue.put(None)
            await db_worker_task
                    

if __name__ == "__main__":
    asyncio.run(main())
