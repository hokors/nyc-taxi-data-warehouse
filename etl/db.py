"""
Database connection factory and session management for STADVDB MCO1.
Provides resilient SQLAlchemy engines, connection pooling, and PyMySQL streaming cursors.
"""

import logging
from contextlib import contextmanager
from typing import Generator
import pymysql
import pymysql.cursors
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from etl import config

logger = logging.getLogger(__name__)


def create_db_engine(db_name: str) -> Engine:
    """
    Creates an optimized SQLAlchemy engine with connection pooling and health checks.
    """
    db_url = f"mysql+pymysql://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{db_name}?charset=utf8mb4"
    return create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False,
    )


# Singleton engine instances
source_engine = create_db_engine(config.SOURCE_DB)
warehouse_engine = create_db_engine(config.WAREHOUSE_DB)


def get_raw_connection(db_name: str, server_side_cursor: bool = False) -> pymysql.connections.Connection:
    """
    Creates a direct PyMySQL raw connection.
    When server_side_cursor=True, uses SSCursor to stream queries without buffering multi-GB data into memory.
    """
    cursor_class = pymysql.cursors.SSCursor if server_side_cursor else pymysql.cursors.Cursor
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=db_name,
        charset="utf8mb4",
        cursorclass=cursor_class,
        autocommit=False,
    )


@contextmanager
def transaction_scope(engine: Engine) -> Generator[Connection, None, None]:
    """
    Context manager providing transactional execution with automatic rollback on error.
    """
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
        trans.commit()
    except Exception as e:
        trans.rollback()
        logger.error(f"Transaction failed and was rolled back: {e}")
        raise
    finally:
        connection.close()


def check_db_connections() -> dict:
    """
    Verifies connectivity to both source and warehouse databases.
    """
    status = {"source": False, "warehouse": False, "errors": []}
    
    # Test Source DB
    try:
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["source"] = True
    except Exception as e:
        status["errors"].append(f"Source DB connection error: {e}")

    # Test Warehouse DB
    try:
        with warehouse_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            status["warehouse"] = True
    except Exception as e:
        status["errors"].append(f"Warehouse DB connection error: {e}")

    return status
