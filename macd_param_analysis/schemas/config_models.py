from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import ClassVar


# ===== Constants =====
YF2PANDAS_FREQ_MAP = { # lookup table for yfinance to pandas frequency mapping
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "60m": "1h",
    "1d": "1D",
    "5d": "5D",
    "1wk": "1W",
    "1mo": "1M",
}


# ===== Enums =====
class YfTimeFrames(Enum):
    ONE_MIN = "1m"
    TWO_MIN = "2m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    THIRTY_MIN = "30m"
    SIXTY_MIN = "60m"
    NINETY_MIN = "90m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    FIVE_DAY = "5d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"
    THREE_MONTH = "3mo"


class PositionSizing(Enum):
    FIXED = "fixed"
    PERCENT_EQUITY = "percent_equity"
    VOL_TARGET = "vol_target"
    KELLY = "kelly"


class TradeDirection(Enum):
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    LONG_SHORT = "long_short"


# ===== Dataclasses =====
@dataclass(frozen=True)
class DataConfig:
    source: str
    asset: str
    timeframe: str
    timeframe_td: timedelta
    start_date: datetime
    end_date: datetime

    def __repr__(self) -> str:
        return (
            f"<DataConfig("
            f"{self.source}, {self.asset}, {self.timeframe}, "
            f"{self.start_date.date()} → {self.end_date.date()})>"
        )


@dataclass
class SimulationConfig:
    sim_start_date: datetime
    sim_end_date: datetime
    initial_cash: ClassVar[float]  # USD
    fee: ClassVar[float]           # %
    slippage: ClassVar[float]      # %
    random_seed: int = 0

    def __repr__(self) -> str:
        return (
            f"<SimulationConfig("
            f"initial_cash={self.initial_cash}, "
            f"fee={self.fee}, slippage={self.slippage}, random_seed={self.random_seed})>"
        )


@dataclass(frozen=True)
class ExecutionConfig:
    position_sizing: str
    direction: str

    def __repr__(self) -> str:
        return (
            f"<ExecutionConfig("
            f"{self.position_sizing}, {self.direction})>"
        )


@dataclass(frozen=True)
class CodeExecutionControlConfig:
    simulation_batch_size: int
    db_bulk_insert_size: int
    threads_to_use: int
    consumer_queue_size: int


@dataclass(frozen=True)
class InfrastructureConfig:
    db_user: str
    db_password: str
    db_name: str
    db_host: str
    db_port: int
    target_port: int

    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_username: str | None = None
    ssh_pkey_path: str | None = None
    db_local_port: int | None = None


@dataclass(frozen=True)
class AnalysisConfig:
    metrics: list[str]
    top_n: list[float]
