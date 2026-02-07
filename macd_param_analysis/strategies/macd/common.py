from typing import Iterator

from schemas import (
    MACDParams,
    InvalidMACDParams,
    MACDParamsGrid
)


def calculate_warmup_period(macd_params: MACDParams) -> int:
    """
    Calculate the padding (warm-up period) required for MACD calculation.

    :param macd_params: MACD parameters
    :type macd_params: MACDParams
    :return: Number of periods to pad for MACD calculation
    :rtype: int
    """
    return macd_params.slow + macd_params.signal - 1


def calculate_max_warmup_period(macd_param_grid: MACDParamsGrid) -> int:
    """
    Calculate the maximum warm-up period required across all MACD parameter combinations.

    :param macd_param_grid: Grid of MACD parameters to consider
    :type macd_param_grid: MACDParamsGrid
    :return: Maximum number of periods to pad for MACD calculation
    :rtype: int
    """
    return max(macd_param_grid.slow_periods) + max(macd_param_grid.signal_periods) - 1


def iter_valid_macd_params(macd_param_grid: MACDParamsGrid) -> Iterator[MACDParams]:
    """
    Iterate over all valid MACD parameter combinations.

    :param macd_param_grid: Grid of MACD parameters to consider
    :type macd_param_grid: MACDParams Grid
    :return: Iterator of valid MACDParams
    :rtype: Iterator[MACDParams]
    """
    for fast in macd_param_grid.fast_periods:
        for slow in macd_param_grid.slow_periods:
            for signal in macd_param_grid.signal_periods:
                try:
                    params = MACDParams(fast=fast, slow=slow, signal=signal)
                    yield params
                except InvalidMACDParams:
                    continue
