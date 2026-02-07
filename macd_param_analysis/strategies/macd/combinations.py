from .common import (
    calculate_warmup_period,
    iter_valid_macd_params,
    calculate_max_warmup_period
)
from schemas import (
    DataConfig,
    ExecutionConfig,
    MACDHistogramSignFlipStrategy,
    MACDParams,
    MACDParamsGrid,
    MACDWindowConfig,
    SimulationConfig,
    MarketData
)


def get_all_macd_setup(
    data_config: DataConfig,
    execution_config: ExecutionConfig,
    macd_params_grid: MACDParamsGrid,
    macd_window_configs: list[MACDWindowConfig],
    full_data: list[MarketData]
) -> set[MACDHistogramSignFlipStrategy]:
    """
    Retrieves all MACD histogram sign-flip strategy simulations for the given data configuration.
    """
    out_list: list[MACDHistogramSignFlipStrategy] = []
    max_warmup = calculate_max_warmup_period(macd_params_grid)
    
    for window_config in macd_window_configs:
        for macd_params in iter_valid_macd_params(macd_params_grid):
            out_list.extend(
                _get_macd__setup_for_params(
                    data_config,
                    execution_config,
                    macd_params,
                    window_config,
                    full_data,
                    max_warmup
                )
            )

    return set(out_list)


def _get_macd__setup_for_params(
    data_config: DataConfig, 
    execution_config: ExecutionConfig,
    macd_params: MACDParams,
    window_config: MACDWindowConfig,
    full_data: list[MarketData],
    max_warmup: int
) -> list[MACDHistogramSignFlipStrategy]:
    """
    A single execution unit for running simulations for given setup through sliding windows.
    
    :param data_config: Data configuration
    :type data_config: DataConfig
    :param execution_config: Execution configuration
    :type execution_config: ExecutionConfig
    :param macd_params: Concrete MACD parameters
    :type macd_params: macd.MACDParams
    :param window_config: Window configuration for the sliding window
    :type window_config: MACDWindowConfig
    :param full_data: Full market data for the asset and timeframe
    :type full_data: list[MarketData]
    :param max_warmup: Maximum warmup period for the MACD parameters
    :type max_warmup: int
    :return: List of MACDHistogramSignFlipStrategy instances for the given setup
    :rtype: list[MACDHistogramSignFlipStrategy]
    """
    out: list[MACDHistogramSignFlipStrategy] = []
    # Calculate simulation period
    warmup_period = calculate_warmup_period(macd_params)
    
    for idx in range(len(full_data), max_warmup + window_config.window_size - 1, -window_config.window_shift):
        # Calculate start and end indices
        end_idx = idx
        start_idx = end_idx - (window_config.window_size + warmup_period)

        # Shouldn't happen, just safeguard
        if start_idx < 0:
            raise ValueError("Not enough data to fill the window with the required warmup period.")
        
        # Create simulation config
        simulation_config = SimulationConfig(
            sim_start_date=full_data[start_idx + warmup_period].timestamp,
            sim_end_date=full_data[end_idx - 1].timestamp + data_config.timeframe_td,  # exclusive
        )

        out.append(
            MACDHistogramSignFlipStrategy(
                asset=data_config.asset,
                timeframe=data_config.timeframe,
                start_date=simulation_config.sim_start_date,
                end_date=simulation_config.sim_end_date,
                initial_cash=simulation_config.initial_cash,
                fee=simulation_config.fee,
                slippage=simulation_config.slippage,
                position_sizing=execution_config.position_sizing,
                direction=execution_config.direction,
                random_seed=simulation_config.random_seed,
                fast_period=macd_params.fast,
                slow_period=macd_params.slow,
                signal_period=macd_params.signal,
                start_idx=start_idx,
                end_idx=end_idx,
            )
        )

    return out
