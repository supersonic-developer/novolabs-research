# MACD Parameter Analysis Project

## Overview

This project provides a comprehensive framework for analyzing MACD (Moving Average Convergence Divergence) trading strategy parameters across different time windows. It uses backtesting to evaluate various parameter combinations and generate performance metrics and visualizations.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Main Tools & Technologies](#main-tools--technologies)
- [Environment Setup](#environment-setup)
- [Configuration Guide](#configuration-guide)
- [Project Structure](#project-structure)
- [Output & Results](#output--results)

---

## Prerequisites

- **Docker** and **Docker Compose** installed on your system
- Basic understanding of Docker containerization
- SSH access (optional, for remote database connectivity)
- Python 3.x knowledge for configuration and customization

---

## Quick Start

1. **Copy and configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

2. **Run the analysis:**
   ```bash
   ./compose_up.sh
   ```

3. **View results:**
   - Check `figures/` directory for visualizations
   - Check `data/` directory for exported data

---

## Main Tools & Technologies

### Docker Compose

The project uses **Docker Compose** to orchestrate multiple services:
- **Data Collector** (`data_collector`): Fetches market data and runs backtesting simulations
- **Analysis Service** (`analysis_service`): Generates metrics, visualizations, and reports
- **PostgreSQL Database** (`pg`): Stores market data and simulation results
  - It's an **optional** service to start depending on if you want to use remote PostgreSQL DB with SSH tunneling

### Wrapper Shell Script (`compose_up.sh`)

The `compose_up.sh` script is the **primary entry point** for running the analysis. It provides intelligent service orchestration based on your choice in an interactive shell prompt and infrastructure configuration. You can pass Docker Compose arguments to this script, such as `-d` for detached mode or `--build` to rebuild images.

#### Dynamic Service Configuration

The script supports two database deployment modes:

1. **Local PostgreSQL Docker Service**
   - Starts the `pg` container
   - Suitable for standalone/local development
   - No need to provide SSH tunneling related configs, check more details in the comments of `config/infra_config.yaml`

2. **Remote PostgreSQL with SSH Tunneling**
   - Doesn't start the `pg` container instead it opens an SSH tunnel to your configured remote server
   - Binds the remote port where your database is to your configured local port
   - Checks if the remote port is available, if it's not available it will start the local `pg` service!
   - Useful for:
     - Shared database environments
     - Production/staging database access
     - Team collaboration with centralized data storage

#### How It Works

When you run `./compose_up.sh`, the script will:

1. **Prompt for SSH tunnel preference:**
   ```
   Do you want to use SSH tunnel? [y/N]
   ```

2. **Check remote database availability** (if SSH is enabled):
   - Reads configuration from `config/infra_config.yaml`
   - Tests SSH connection and database reachability (only checks for port availablity but not for actual DB connection!)
   - Determines whether to start local PostgreSQL or skip it

3. **Start appropriate services:**
   - If remote DB is available: starts only `data_collector` and `analysis_service`
   - If using local DB: starts all services including `pg`

#### Usage Examples

```bash
# Start with local PostgreSQL
./compose_up.sh

# Start with remote PostgreSQL (prompted)
./compose_up.sh
# Answer 'y' when prompted

# Pass additional docker-compose flags
./compose_up.sh --build
./compose_up.sh -d  # Detached mode
```

---

## Environment Setup

### Step 1: Configure Environment Variables

The project requires several environment variables for database connectivity. These should be defined in a `.env` file which you have to setup:

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your values:**
   ```dotenv
   POSTGRES_USER=your_username
   POSTGRES_PASSWORD=your_password
   POSTGRES_PORT=5432
   ```

   **Note:** These values must match the configuration in `config/infra_config.yaml`

### Step 2: SSH Configuration (Optional)

If using remote PostgreSQL with SSH tunneling:

1. Ensure you have SSH keys set up (`~/.ssh/id_ed25519` or `~/.ssh/id_rsa`) and at least one of them is accepted on your remote
2. Configure SSH details in `config/infra_config.yaml` (see below)
3. Test SSH connection manually before running the analysis

---

## Configuration Guide

All project behavior is controlled through YAML configuration files located in the `config/` directory. This allows you to customize the analysis without modifying code.

### Configuration Files

#### 1. `infra_config.yaml` - Infrastructure & Database

Controls database connectivity and SSH tunneling:

```yaml
# SSH Configuration (optional)
ssh_host: "your.server.ip"       # SSH server address
ssh_port: 22                      # SSH port (default: 22)
ssh_username: "your_username"     # SSH username
ssh_pkey_path: "~/.ssh/id_ed25519" # Path to SSH private key
db_local_port: 65433             # Local port for SSH tunnel

# Database Configuration (required)
db_user: "your_username"         # Must match POSTGRES_USER in .env
db_name: "financial_data"        # Database name
db_host: "localhost"             # DB host (localhost for SSH tunnel)
db_port: 5432                    # DB port (must match POSTGRES_PORT in .env)
```

**Key Points:**
- Leave SSH fields empty/commented for local PostgreSQL
- `db_user` must match `POSTGRES_USER` from `.env`
- `db_port` must match `POSTGRES_PORT` from `.env` when not using SSH

#### 2. `data_config.yaml` - Market Data Sources

Defines which assets and timeframes to analyze:

```yaml
- source: yahoo             # Data source (e.g., yahoo)
  asset: BTC-USD            # Asset symbol
  timeframe: 1d             # Timeframe (1d, 1h, etc.)
  start_date: 2021-01-02T00:00:00Z  # Analysis start date (ISO 8601)
  end_date: 2026-01-01T00:00:00Z    # Analysis end date (ISO 8601)
```

**Configuration Options:**
- Add multiple entries for different assets
- Use timezone-aware datetime strings (ISO 8601 format)
- Check data source documentation for valid timeframes

#### 3. `macd_params.yaml` - MACD Parameter Grid

Defines the parameter space for backtesting:

```yaml
# Format: [start, end, step]
fast_periods: [2, 52, 2]      # Fast EMA: 2, 4, 6, ..., 50
slow_periods: [20, 202, 2]    # Slow EMA: 20, 22, 24, ..., 200
signal_periods: [10, 102, 2]  # Signal line: 10, 12, 14, ..., 100
```

**Format Explanation:**
- First value: Range start (inclusive)
- Second value: Range end (exclusive)
- Third value: Step size

#### 4. `window_configs.yaml` - Rolling Window Analysis

Configure rolling window parameters for temporal analysis:

```yaml
# Configure rolling time windows for drift analysis
windows:
  - duration: 730  # days (e.g., 2 years)
    step: 73       # step size in days
```

**Configuration Options:**
- Add multiple window configurations with different duration or step size

**Explanation:**
- Creates a 730-day rolling window that last day fit to your configured end date and moves backward through time in 73-day increments
- Automatically drops any incomplete windows that would extend before your configured start date

#### 5. `simulation_config.yaml` - Backtesting Parameters

Trading simulation settings:

```yaml
initial_capital: 1000  # USD
fee: 0.001              # 0.1%
slippage: 0.001         # %
```

#### 6. `trade_execution_config.yaml` - Trade Execution Rules

```yaml
# Trade entry/exit logic configuration
position_sizing: "fixed"
direction: "long_only"
```

**Configure Options:**
- Valid strings are defined in `schemas/config_model.py` with enum classes:

```python
class PositionSizing(Enum):
    FIXED = "fixed"
    PERCENT_EQUITY = "percent_equity"
    VOL_TARGET = "vol_target"
    KELLY = "kelly"


class TradeDirection(Enum):
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    LONG_SHORT = "long_short"
```

#### 7. `analysis_config.yaml` - Analysis & Visualization Settings

This configuration file used only for analysis:

```yaml
metrics:
  - expectancy
top_n:
  - 0.1  # Top 10%
```

**Configuration Options:**
- Add multiple metrics or top_n configurations if needed
- valid metrics string are define in `strategies/extract.py`:
```python
CORE_METRICS = {
    # Performance
    "Total Return [%]": "total_return_pct",
    "Benchmark Return [%]": "benchmark_return_pct",

    # Risk-adjusted
    "Sharpe Ratio": "sharpe",
    "Calmar Ratio": "calmar",
    "Sortino Ratio": "sortino",
    "Omega Ratio": "omega",

    # Drawdown
    "Max Drawdown [%]": "max_dd_pct",
    "Max Drawdown Duration": "max_dd_duration",

    # Trading quality
    "Win Rate [%]": "win_rate_pct",
    "Profit Factor": "profit_factor",
    "Expectancy": "expectancy",
    "Total Trades": "total_trades",
    "Total Fees Paid": "total_fees_paid",
}
```
- top_n will set your top N% best parameter combinations

#### 8. `code_execution_control.yaml` - Execution Flow Control

```yaml
simulation_batch_size: 200
db_bulk_insert_size: 5000
threads_to_use: 16
consumer_queue_size: 50000
```

**Configure options:**
- Simulation batch size defines how much simulation should be ran in a single task, based on my measurements 200 is a good choice to utilize the potential of python's pool executor
- DB bulk insert defines the number of simulation results that should be commited to the DB in a single transaction, 5,000 is a good choice because it doesn't slow too much the CPU bounded task, and modern RAMs can easily handle
- Number of threads to use with safeguarding in config loader
- Consumer queue size is the maximum number of simulation results that can be stored in the memory at once

---

## Project Structure

### Core Modules

#### `main.py` - Data Collection & Backtesting
**Purpose:** Orchestrates data collection and runs backtesting simulations

**What it does:**
- Fetches market data from configured sources (Yahoo Finance, etc.)
- Stores data in PostgreSQL database
- Generates MACD parameter combinations
- Runs backtesting simulations for each missing parameter set, so it skips parameter combinations which already exists in DB
- Stores simulation results in the database

**When to modify:**
- Change data collection logic
- Modify backtesting workflow
- Add new strategies and signal generations for your own strategies
- Customize parallel processing behavior

#### `analysis.py` - Post-Processing & Visualization
**Purpose:** Analyzes backtesting results and generates reports

**What it does:**
- Loads simulation results from database
- Generates visualizations (parameter clouds, heatmaps)
- Exports data to CSV/Parquet format, very efficient way to store data locally
- Creates drift analysis plots for temporal patterns

**When to modify:**
- Customize visualization styles
- Change export formats
- Modify analysis workflows

### Module Directories

#### `config/` - Configuration Management
**Files:**
- `config_loader.py`: Functions to load YAML configurations
- `*.yaml`: Configuration files (see Configuration Guide above)

**Purpose:** Centralized configuration loading and validation

#### `db/` - Database Layer
**Files:**
- `api.py`: Database CRUD operations
- `lifecycle.py`: Connection management, SSH tunneling

**Purpose:** Handles all database interactions and connection lifecycle

**Key Functions:**
- `open_ssh_tunnel()`: Establishes SSH tunnel to remote database
- `collect_data()`: Fetches and stores market data
- `get_macd_histogram_sign_flip_simulations()`: Retrieves simulation results

#### `schemas/` - Data Models
**Files:**
- `config_models.py`: Pydantic models for configurations
- `macd_models.py`: MACD strategy models
- `orm_models.py`: SQLAlchemy ORM models for database tables

**Purpose:** Type-safe data structures and database schema definitions

#### `src/` - Core Analysis Logic
**Files:**
- `data_loader.py`: Load and transform market data
- `metrics.py`: Calculate performance metrics
- `plots.py`: Generate visualizations
- `runner.py`: Parallel execution utilities
- `drift_analysis.py`: Temporal drift analysis
- `logging_config.py`: Logging configuration

**Purpose:** Core analytical functions and utilities

#### `strategies/` - Trading Strategies
**Structure:**
```
strategies/
├── __init__.py
├── extract.py           # Strategy result extraction
└── macd/
    ├── __init__.py
    ├── combinations.py  # Parameter combination generation
    ├── common.py        # Shared MACD utilities
    └── signals.py       # Signal generation logic
└── your_strategy/
    ├── __init__.py
    ├── ...
```

**Purpose:** Trading strategy implementations and signal generation

**When to modify:**
- Implement new trading strategies
- Customize MACD signal logic
- Add strategy variants

#### `figures/` - Output Visualizations
**Structure:**
```
figures/
├── interactive/         # HTML interactive plots (Plotly)
│   ├── calmar/
│   ├── sharpe/
│   ├── sortino/
│   └── ...
├── static/             # PNG/static images
└── static_2d_projection/  # 2D projections of parameter space
```

**Purpose:** Stores generated visualizations

#### `data/` - Exported Data
**Purpose:** CSV/Parquet exports of analysis results

---

## Output & Results

### Generated Files

After running the analysis, you'll find:

1. **Interactive Visualizations** (`figures/interactive/<metric>`)
   - 3D parameter clouds for various metrics
   - Color-coded by performance
   - Organized by metric type (Sharpe, Sortino, Calmar, etc.)
   - Files named: `macd_param_cloud_<start_date>_<end_date>.html`

2. **Static Images** (`figures/static/<metric>`)
   - PNG exports for reports and presentations
   - Same organization as interactive plots

3. **2D Projections** (`figures/static_2d_projection/<metric>`)
   - Heatmaps showing parameter relationships projected into 2D
   - Can you different methods to eliminate the 3rd variable

4. **Exported Data** (`data/`)
   - CSV/Parquet files with raw metrics
   - Can be loaded for custom analysis

### Interpreting Results

- **Parameter Clouds:** Each point represents a parameter combination colored by performance metric
- **Drift Analysis:** Shows how optimal parameters change over time
- **Heatmaps:** Identify regions of parameter space with consistently good performance

---

## License

See `LICENSE` file in the root directory.
