import asyncio
import os
import logging

from db import open_ssh_tunnel
from config import (
    load_data_configs,
    load_window_configs,
    load_analysis_config
)
from src.logging_config import setup_logging
from src.data_loader import (
    load_market_data,
    convert_db_records_to_parquet
)
from src.metrics import btc_return_distribution_analysis
from src.plots import (
    generate_all_parameter_clouds,
    generate_interactive_clouds,
    generate_all_heatmaps
)
from src.drift_analysis import (
    plot_centroid_drift,
    plot_centroid_norm_drift,
    plot_top_n_overlap,
    plot_convex_hull_volume_drift
)


setup_logging(log_dir="logs", service_name="analysis_service", log_level="INFO")
logger = logging.getLogger(__name__)


# ===== Directories =====
FIG_DIR = "figures"
DATA_DIR = "data"


# ===== Configs =====
DATA_CONFIG = load_data_configs("config/data_config.yaml")[0] # BTC-USD config
WINDOW_CONFIG = load_window_configs("config/window_configs.yaml")[0]  # 730 days config
ANALYSIS_CONFIG = load_analysis_config("config/analysis_config.yaml")


# ===== Main Analysis =====
async def main():
    parquet_path = os.path.join(DATA_DIR, "macd_strategy_results.parquet")
    async with open_ssh_tunnel() as async_session_maker, async_session_maker() as session:
        market_data = await load_market_data(session, DATA_CONFIG)
        await convert_db_records_to_parquet(
            session,
            WINDOW_CONFIG.window_size,
            parquet_path,
            DATA_CONFIG
        )

    # BTC return distribution analysis
    btc_return_distribution_analysis(
        market_data,
        os.path.join(FIG_DIR, "btc_return_distribution.svg")
    )

    for metric in ANALYSIS_CONFIG.metrics:
        generate_all_parameter_clouds(
            parquet_path=parquet_path,
            metric=metric,
            fig_dir=FIG_DIR
        )

        generate_interactive_clouds(
            parquet_path=parquet_path,
            metric=metric,
            fig_dir=FIG_DIR
        )

        generate_all_heatmaps(
            parquet_path=parquet_path,
            metric=metric,
            agg="mean",
            fig_dir=FIG_DIR
        )

        for top_pct in ANALYSIS_CONFIG.top_n:
            plot_centroid_drift(
                parquet_path=parquet_path,
                metric=metric,
                top_pct=top_pct,
                fig_dir=FIG_DIR
            )

            plot_centroid_norm_drift(
                parquet_path=parquet_path,
                metric=metric,
                top_pct=top_pct,
                fig_dir=FIG_DIR
            )

            plot_top_n_overlap(
                parquet_path=parquet_path,
                metric=metric,
                top_pct=top_pct,
                fig_dir=FIG_DIR
            )

            plot_convex_hull_volume_drift(
                parquet_path=parquet_path,
                metric=metric,
                top_pct=top_pct,
                fig_dir=FIG_DIR
            )


if __name__ == "__main__":
    asyncio.run(main())
    