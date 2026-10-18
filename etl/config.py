import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables from .env if present
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Database Connection Settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Schemas and Tables
SOURCE_DB = os.getenv("SOURCE_DB", "nyc_taxi_source")
WAREHOUSE_DB = os.getenv("WAREHOUSE_DB", "nyc_taxi_warehouse")
SOURCE_TABLE = os.getenv("SOURCE_TABLE", "yellow_taxi_trips")

# File Paths
RAW_CSV_PATH = Path(os.getenv("RAW_CSV_PATH", BASE_DIR / "yellow_taxi_2025.csv"))
LOOKUP_CSV_PATH = Path(os.getenv("LOOKUP_CSV_PATH", BASE_DIR / "taxi_zone_lookup.csv"))

# Performance & Streaming Settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "100000"))
EXTRACT_MODE = os.getenv("EXTRACT_MODE", "db").lower()  # 'db' or 'csv'

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_source_connection_url() -> str:
    """Returns SQLAlchemy connection URL for the source database."""
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{SOURCE_DB}?charset=utf8mb4"


def get_warehouse_connection_url() -> str:
    """Returns SQLAlchemy connection URL for the warehouse database."""
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{WAREHOUSE_DB}?charset=utf8mb4"


def validate_config() -> dict:
    """Validates configuration and returns summary of parameters."""
    return {
        "DB_HOST": DB_HOST,
        "DB_PORT": DB_PORT,
        "DB_USER": DB_USER,
        "SOURCE_DB": SOURCE_DB,
        "WAREHOUSE_DB": WAREHOUSE_DB,
        "SOURCE_TABLE": SOURCE_TABLE,
        "CHUNK_SIZE": CHUNK_SIZE,
        "EXTRACT_MODE": EXTRACT_MODE,
        "RAW_CSV_EXISTS": RAW_CSV_PATH.exists(),
        "LOOKUP_CSV_EXISTS": LOOKUP_CSV_PATH.exists(),
    }
