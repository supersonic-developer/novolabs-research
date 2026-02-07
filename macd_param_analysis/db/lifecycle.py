from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio
import logging

from sshtunnel import SSHTunnelForwarder    # type: ignore
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from schemas import Base
from config import load_infra_config


logger = logging.getLogger(__name__)

INFRA_CONFIG = load_infra_config("config/infra_config.yaml")


@asynccontextmanager
async def open_ssh_tunnel() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """
    Async context manager that:
    - opens an SSH tunnel to remote DB
    - creates async SQLAlchemy engine
    - cleans up tunnel and engine automatically
    - yields an async session maker
    Usage:
        async with get_db_session() as session:
            await session.execute(...)
    """
    server: SSHTunnelForwarder | None = None
    if INFRA_CONFIG.ssh_host is not None:
        server = SSHTunnelForwarder(
            (INFRA_CONFIG.ssh_host, INFRA_CONFIG.ssh_port),
            ssh_username=INFRA_CONFIG.ssh_username,
            ssh_pkey=INFRA_CONFIG.ssh_pkey_path,
            remote_bind_address=(INFRA_CONFIG.db_host, INFRA_CONFIG.db_port),
            local_bind_address=(INFRA_CONFIG.db_host, INFRA_CONFIG.db_local_port),
        )
        server.start()
        logger.info(f"SSH tunnel opened: {INFRA_CONFIG.ssh_host}:{INFRA_CONFIG.ssh_port} → {INFRA_CONFIG.db_host}:{INFRA_CONFIG.db_local_port}")
    await asyncio.to_thread(ensure_db_exists)

    try:
        # --- Create async engine ---
        DATABASE_URL = f"postgresql+asyncpg://{INFRA_CONFIG.db_user}:{INFRA_CONFIG.db_password}@{INFRA_CONFIG.db_host}:{INFRA_CONFIG.target_port}/{INFRA_CONFIG.db_name}"
        engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

        await db_init(engine)

        yield async_sessionmaker(engine, expire_on_commit=False)

        await engine.dispose()
    finally:
        if server:
            server.stop()
        logger.info("SSH tunnel closed.")


def ensure_db_exists():
    """Connect to default 'postgres' DB and create target DB if missing."""
    bootstrap_url = f"postgresql://{INFRA_CONFIG.db_user}:{INFRA_CONFIG.db_password}@{INFRA_CONFIG.db_host}:{INFRA_CONFIG.target_port}/postgres"
    engine = create_engine(bootstrap_url, isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        try:
            conn.execute(text(f"CREATE DATABASE {INFRA_CONFIG.db_name}"))
            logger.info(f"Database {INFRA_CONFIG.db_name} created.")
        except ProgrammingError as e:
            if "already exists" in str(e):
                logger.info(f"Database {INFRA_CONFIG.db_name} already exists.")
            else:
                raise

    engine.dispose()
    logger.info("Postgres engine disposed.")


async def db_init(engine: AsyncEngine):
    """
    Initialize the database schema.
    Creates all tables defined in models.Base.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized.")
