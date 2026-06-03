from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
WAREHOUSE_DIR = DATA_DIR / "warehouse"

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONFIG_DIR = SCRIPTS_DIR / "config"
LOGS_DIR = PROJECT_ROOT / "logs"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_raw_data_path(domain: str) -> Path:
    return ensure_directory(RAW_DATA_DIR / domain)


def get_processed_data_path() -> Path:
    return ensure_directory(PROCESSED_DATA_DIR)


def get_warehouse_path() -> Path:
    return ensure_directory(WAREHOUSE_DIR)


def get_config_path(filename: str) -> Path:
    return CONFIG_DIR / filename


def get_log_path(filename: str) -> Path:
    ensure_directory(LOGS_DIR)
    return LOGS_DIR / filename