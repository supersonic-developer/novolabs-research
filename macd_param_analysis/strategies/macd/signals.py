
import pandas as pd

from .common import calculate_warmup_period
from schemas import (
    MarketData,
    MACDParams
)


def generate_MACD_histogram_sign_flip_signals(
    market_data: list[MarketData],
    macd_params: MACDParams,
    cut_warmup_period: bool = True
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Go long when MACD histogram flips from negative to positive, exit when it flips from positive to negative.

    Note: this method assumes market_data is sorted by timestamp.
    
    :param market_data: Market data to generate signals from
    :type market_data: list[MarketData]
    :param macd_params: MACD parameters
    :type macd_params: MACDParams
    :param cut_warmup_period: Whether to cut the initial warm-up period from the signals
    :type cut_warmup_period: bool
    :return: Tuple of (entry_signals, exit_signals, simulation period)
    :rtype: tuple[pd.Series[bool], pd.Series[bool], pd.Series[float]]
    """
    close = pd.Series(
        [md.close for md in market_data],
        index=[md.timestamp for md in market_data]
    )

    ema_fast = close.ewm(span=macd_params.fast, adjust=False).mean()
    ema_slow = close.ewm(span=macd_params.slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=macd_params.signal, adjust=False).mean()
    macd_histogram = macd_line - signal_line

    # Entry & Exit Signals
    entry_signals = (macd_histogram.shift(1) < 0) & (macd_histogram >= 0)
    exit_signals = (macd_histogram.shift(1) > 0) & (macd_histogram <= 0)

    warmup_period = calculate_warmup_period(macd_params)

    if cut_warmup_period:
        return entry_signals[warmup_period:], exit_signals[warmup_period:], close[warmup_period:]
    else:
        return entry_signals, exit_signals, close
