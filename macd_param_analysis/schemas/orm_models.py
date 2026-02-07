from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKeyConstraint, func, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column
    

# ===== ORM Models =====
class Base(DeclarativeBase, MappedAsDataclass):
    pass


class BaseStrategyRun(Base):
    __abstract__ = True
    __allowed_unmapped__ = True

    # --- Data slice ---
    asset: Mapped[str] = mapped_column(primary_key=True)
    timeframe: Mapped[str] = mapped_column(primary_key=True)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

    # --- Execution context ---
    initial_cash: Mapped[float] = mapped_column(primary_key=True)
    fee: Mapped[float] = mapped_column(primary_key=True)
    slippage: Mapped[float] = mapped_column(primary_key=True)

    # --- Position / trade semantics ---
    position_sizing: Mapped[str] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(primary_key=True)

    # --- Monte Carlo / stochastic ---
    random_seed: Mapped[int] = mapped_column(primary_key=True)

    # --- Lineage ---
    run_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), init=False, server_default=func.now())

    # --- Outputs ---
    metrics: Mapped[dict[str, float | None | str]] = mapped_column(JSONB, init=False)

    # --- Runtime-only fields ---
    # Not stored in DB, only used during simulation execution
    start_idx: int | None = None
    end_idx: int | None = None


    # --- Methods ---
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}("
            f"{self.asset}, {self.timeframe}, "
            f"{self.start_date.date()} → {self.end_date.date()}, "
            f"seed={self.random_seed})>"
        )
    

    def __hash__(self) -> int:
        return hash((
            self.asset,
            self.timeframe,
            self.start_date,
            self.end_date,
            self.initial_cash,
            self.fee,
            self.slippage,
            self.position_sizing,
            self.direction,
            self.random_seed
        ))
    

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BaseStrategyRun):
            return False
        return (
            self.asset == other.asset
            and self.timeframe == other.timeframe
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.initial_cash == other.initial_cash
            and self.fee == other.fee
            and self.slippage == other.slippage
            and self.position_sizing == other.position_sizing
            and self.direction == other.direction
            and self.random_seed == other.random_seed
        )


class MACDHistogramSignFlipStrategy(BaseStrategyRun):
    """
    MACD Histogram Sign Flip Strategy: go long when the MACD histogram flips from negative to positive,
    exit when it flips from positive to negative.

    Parameters
    ---
    - fast_period: int
    - slow_period: int
    - signal_period: int
    """
    __tablename__ = "macd_histogram_sign_flip_strategy"

    fast_period: Mapped[int] = mapped_column(primary_key=True, kw_only=True)
    slow_period: Mapped[int] = mapped_column(primary_key=True, kw_only=True)
    signal_period: Mapped[int] = mapped_column(primary_key=True, kw_only=True)


    def __repr__(self) -> str:
        return (
            f"<MACDHistogramSignFlipStrategy("
            f"{self.asset}, {self.timeframe}, "
            f"{self.start_date.date()} → {self.end_date.date()}, "
            f"fast={self.fast_period}, slow={self.slow_period}, signal={self.signal_period}>"
        )
    

    def __hash__(self) -> int:
        return hash((
            super().__hash__(),
            self.fast_period,
            self.slow_period,
            self.signal_period
        ))
    

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MACDHistogramSignFlipStrategy):
            return False
        return (
            super().__eq__(other)
            and self.fast_period == other.fast_period
            and self.slow_period == other.slow_period
            and self.signal_period == other.signal_period
        )


class MarketData(Base):
    """
    Raw OHLCV bars as provided by a data source.
    No adjustments, no corporate actions.
    """
    __tablename__ = "market_data"

    __table_args__ = (
        Index(
            "ix_market_data_asset_source_tf_ts",
            "asset", "source", "timeframe", "timestamp"
        ),
    )

    # --- Composite Primary Key ---
    asset: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(primary_key=True)
    timeframe: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

    # --- OHLCV ---
    open: Mapped[float]
    high: Mapped[float]
    low: Mapped[float]
    close: Mapped[float]
    volume: Mapped[float]

    # --- Relationships ---
    actions: Mapped["MarketAction"] = relationship(
        "MarketAction",
        back_populates="market_data",
        primaryjoin="and_("
                    "MarketData.asset==MarketAction.asset, "
                    "MarketData.source==MarketAction.source, "
                    "MarketData.timeframe==MarketAction.timeframe, "
                    "MarketData.timestamp==MarketAction.timestamp)",
        init=False
    )

    def __repr__(self):
        return (
            f"<MarketData({self.asset}, {self.source}, "
            f"{self.timeframe}, {self.timestamp})>"
        )
    
    def __lt__(self, other: 'MarketData') -> bool:
        return self.timestamp < other.timestamp
    

class MarketAction(Base):
    __tablename__ = "market_actions"

    __table_args__ = (
        ForeignKeyConstraint(
            ["asset", "source", "timeframe", "timestamp"],
            ["market_data.asset", "market_data.source", "market_data.timeframe", "market_data.timestamp"]
        ),
        # Add unique constraint for ON CONFLICT
        Index(
            "uq_market_action_asset_source_tf_ts",
            "asset", "source", "timeframe", "timestamp",
            unique=True
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)

    # --- Composite Foreign Key to MarketData ---
    asset: Mapped[str]
    source: Mapped[str]
    timeframe: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # --- Corporate Actions ---
    dividends: Mapped[float | None]
    stock_splits: Mapped[float | None]
    capital_gains: Mapped[float | None]

    market_data: Mapped["MarketData"] = relationship(
        "MarketData",
        back_populates="actions",
        primaryjoin="and_("
                    "MarketAction.asset==MarketData.asset, "
                    "MarketAction.source==MarketData.source, "
                    "MarketAction.timeframe==MarketData.timeframe, "
                    "MarketAction.timestamp==MarketData.timestamp)",
        init=False
    )

    # backref for convenience
    market_data: Mapped["MarketData"] = relationship("MarketData", back_populates="actions", init=False)
