from dataclasses import dataclass


class InvalidMACDParams(Exception):
    def __init__(self, params: "MACDParams"):
        super().__init__(f"Invalid MACD parameters: fast={params.fast}, slow={params.slow}, signal={params.signal}")


@dataclass(frozen=True)
class MACDParams:
    fast: int
    slow: int
    signal: int


    def __post_init__(self):
        if not (0 < self.fast < self.slow and self.signal < self.slow):
            raise InvalidMACDParams(self)
        
    def __repr__(self) -> str:
        return f"MACDParams(fast={self.fast}, slow={self.slow}, signal={self.signal})"
        

@dataclass(frozen=True)
class MACDParamsGrid:
    fast_periods: list[int]
    slow_periods: list[int]
    signal_periods: list[int]


@dataclass(frozen=True)
class MACDWindowConfig:
    window_size: int
    window_shift: int
