import yaml
from datetime import timedelta
from typing import List, Any
import multiprocessing
import os

from schemas import (
    DataConfig,
    ExecutionConfig,
    MACDParamsGrid,
    MACDWindowConfig,
    CodeExecutionControlConfig,
    InfrastructureConfig,
    PositionSizing,
    TradeDirection,
    SimulationConfig,
    AnalysisConfig
)


def load_data_configs(path: str) -> List[DataConfig]:
    with open(path, 'r') as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f)

    configs: list[DataConfig] = []
    for entry in raw:
        configs.append(DataConfig(
            source=entry['source'],
            asset=entry['asset'],
            timeframe=entry['timeframe'],
            timeframe_td=_parse_timedelta(entry['timeframe']),
            start_date=entry['start_date'], # Note: pyyaml parses ISO 8601 datetime strings into datetime objects automatically
            end_date=entry['end_date'],
        ))

    return configs


def load_trade_execution_config(path: str) -> ExecutionConfig:
    with open(path, 'r') as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    
    # Check validity
    PositionSizing(raw['position_sizing'])
    TradeDirection(raw['direction'])

    return ExecutionConfig(
        position_sizing=raw['position_sizing'],
        direction=raw['direction']
    )


def load_macd_params(path: str) -> MACDParamsGrid:
    with open(path, 'r') as f:
        params: dict[str, Any] = yaml.safe_load(f)

    return MACDParamsGrid(
        fast_periods=list(range(params['fast_periods'][0], params['fast_periods'][1], params['fast_periods'][2])),
        slow_periods=list(range(params['slow_periods'][0], params['slow_periods'][1], params['slow_periods'][2])),
        signal_periods=list(range(params['signal_periods'][0], params['signal_periods'][1], params['signal_periods'][2])),
    )


def load_window_configs(path: str) -> List[MACDWindowConfig]:
    with open(path, 'r') as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f)
    
    configs: list[MACDWindowConfig] = []
    for entry in raw:
        configs.append(
            MACDWindowConfig(
                window_size=entry['window_size'],
                window_shift=entry['window_shift'],
            )
        )

    return configs


def load_code_execution_control_config(path: str) -> CodeExecutionControlConfig:
    with open(path, 'r') as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    threads_to_use = raw.get('threads_to_use', None)

    if threads_to_use is None or threads_to_use > multiprocessing.cpu_count():
        threads_to_use = multiprocessing.cpu_count() - 2

    return CodeExecutionControlConfig(
        simulation_batch_size=raw['simulation_batch_size'],
        db_bulk_insert_size=raw['db_bulk_insert_size'],
        threads_to_use=threads_to_use,
        consumer_queue_size=raw['consumer_queue_size'],
    )


def load_infra_config(path: str) -> InfrastructureConfig:
    with open(path, 'r') as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    if raw['db_host'] not in ['localhost', '127.0.0.1']:
        raw['ssh_host'] = None
        raw['ssh_port'] = None
        raw['ssh_username'] = None
        raw['ssh_pkey_path'] = None
        raw['db_local_port'] = None
        raw['target_port'] = raw['db_port']
    else:
        if any(v is None for k, v in raw.items() if k.startswith('ssh_')) or raw.get('db_local_port') is None:
            raise ValueError("Incomplete SSH configuration in infra_config.yaml for local DB access.")
        
        raw['target_port'] = raw['db_local_port']

    return InfrastructureConfig(
        db_user=raw['db_user'],
        db_password=os.environ['POSTGRES_PASSWORD'], # Required and stored in env variable for security
        db_name=raw['db_name'],
        db_host=raw['db_host'],
        db_port=raw['db_port'],
        ssh_host=raw['ssh_host'],
        ssh_port=raw['ssh_port'],
        ssh_username=raw['ssh_username'],
        ssh_pkey_path=raw['ssh_pkey_path'],
        db_local_port=raw['db_local_port'],
        target_port=raw['target_port'],
    )


def load_simulation_config(path: str) -> None:
    with open(path, 'r') as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    SimulationConfig.initial_cash = raw['initial_cash']
    SimulationConfig.fee = raw['fee']
    SimulationConfig.slippage = raw['slippage']


def load_analysis_config(path: str) -> AnalysisConfig:
    with open(path, 'r') as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    return AnalysisConfig(
        metrics=raw['metrics'],
        top_n=raw['top_n']
    )
    

# ===== Internal helpers =====
def _parse_timedelta(timeframe: str) -> timedelta:
    """
    Parses a timeframe string like '1d', '4h', '15m' into a timedelta object.
    NOTE: if your timeframe definitions differ, adjust this function accordingly.
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    return {
        'w': timedelta(weeks=value),
        'd': timedelta(days=value),
        'h': timedelta(hours=value),
        'm': timedelta(minutes=value),
        's': timedelta(seconds=value),
    }[unit]