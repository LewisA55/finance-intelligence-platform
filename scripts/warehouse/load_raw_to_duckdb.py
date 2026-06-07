"""
Project Atlas / Finance Intelligence Platform
Phase 4 - DuckDB Bronze Warehouse Loader (Fast DuckDB Hash Edition)

Purpose
-------
Loads every CSV under data/raw into data/warehouse/atlas.duckdb as faithful
Bronze tables, preserving source structure and adding Atlas audit metadata.

Bronze metadata contract
------------------------
Every loaded Bronze table receives:
- _atlas_row_hash: deterministic MD5 fingerprint of original source-row values only
- _atlas_ingested_at: UTC timestamp of this warehouse load run
- _atlas_source_file: origin CSV filename

Hash encoding standard
----------------------
_atlas_row_hash is computed by DuckDB using MD5 over JSON-array serialisation of
ordered, normalised source values. This avoids delimiter-collision risk while
preserving native CSV column order and source-only fingerprinting.

Physical execution method:
    duckdb_json_array_v1

Critical design invariant
-------------------------
The raw payload boundary must be captured before operational enrichment:
    source_columns = list(df.columns)

The row hash must never include _atlas_ingested_at, _atlas_source_file,
_atlas_row_hash, row indexes, runtime state, or future metadata columns.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import duckdb
    import pandas as pd
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "Missing dependency. Install required packages with: pip install pandas duckdb"
    ) from exc


LOGGER = logging.getLogger("AtlasBronzeLoader")

ATLAS_METADATA_COLUMNS = [
    "_atlas_row_hash",
    "_atlas_ingested_at",
    "_atlas_source_file",
]

NULL_TOKEN = "<NULL>"
HASH_ENCODING_METHOD = "duckdb_json_array_v1"
BRONZE_SCHEMA = "bronze"
AUDIT_TABLE = "_atlas_load_audit"


@dataclass(frozen=True)
class BronzeLoadResult:
    source_file_path: str
    source_file_name: str
    target_schema: str
    target_table: str
    rows_loaded: int
    source_column_count: int
    final_column_count: int
    source_file_size_bytes: int
    ingested_at_utc: str
    hash_encoding_method: str
    load_status: str
    error_message: str = ""


# -----------------------------------------------------------------------------
# Path / identifier helpers
# -----------------------------------------------------------------------------


def resolve_project_root() -> Path:
    """
    Resolve the repository root from scripts/warehouse/load_raw_to_duckdb.py.

    Expected project layout:
        project_root/
            data/raw/
            data/warehouse/
            scripts/warehouse/load_raw_to_duckdb.py
    """
    return Path(__file__).resolve().parents[2]



def quote_identifier(identifier: str) -> str:
    """Safely quote a DuckDB identifier."""
    return '"' + identifier.replace('"', '""') + '"'



def sql_string_literal(value: str) -> str:
    """Safely quote a string literal for generated DuckDB SQL."""
    return "'" + value.replace("'", "''") + "'"



def sanitise_identifier_component(value: str) -> str:
    """
    Sanitise one DuckDB identifier component.

    This normalises noisy characters and repeated single underscores within the
    component. It deliberately does not know about the Atlas namespace boundary.
    """
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", value.strip()).lower()
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    if not cleaned:
        cleaned = "unnamed"

    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"

    return cleaned



def sanitise_identifier(value: str) -> str:
    """
    Convert a path-derived value into a stable DuckDB-safe table identifier.

    The explicit Atlas double-underscore namespace boundary is preserved.

    Examples:
        accounting__chart_of_accounts -> accounting__chart_of_accounts
        billing__billing invoices     -> billing__billing_invoices
    """
    namespace_parts = value.strip().split("__")
    cleaned_parts = [
        sanitise_identifier_component(part)
        for part in namespace_parts
    ]
    return "__".join(cleaned_parts)



def table_name_from_csv_path(csv_path: Path, raw_dir: Path) -> str:
    """
    Create one stable Bronze table name per raw CSV.

    Examples:
        data/raw/billing/billing_invoices.csv
            -> bronze.billing__billing_invoices

        data/raw/accounting/trial_balance.csv
            -> bronze.accounting__trial_balance

        data/raw/governance/source_output_inventory.csv
            -> bronze.governance__source_output_inventory
    """
    relative_path = csv_path.relative_to(raw_dir)
    path_parts = list(relative_path.with_suffix("").parts)
    table_base = "__".join(path_parts)
    return sanitise_identifier(table_base)


# -----------------------------------------------------------------------------
# Source discovery / reading
# -----------------------------------------------------------------------------


def discover_raw_csv_files(raw_dir: Path) -> list[Path]:
    """Return all raw CSV files under data/raw in deterministic path order."""
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    csv_files = sorted(path for path in raw_dir.rglob("*.csv") if path.is_file())

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found under raw data directory: {raw_dir}")

    return csv_files



def read_source_csv(csv_path: Path) -> pd.DataFrame:
    """
    Read a raw CSV with Bronze-friendly source preservation.

    dtype=str intentionally avoids premature typing. Dates, account codes,
    IDs, currency codes, periods, booleans and amounts are interpreted later in
    dbt Silver models.

    keep_default_na=False avoids converting business strings such as 'NA' into
    nulls. Missing parser values are handled by the DuckDB hash expression.
    """
    return pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
        na_values=[],
        encoding="utf-8-sig",
        low_memory=False,
    )



def capture_source_columns(df: pd.DataFrame) -> list[str]:
    """
    Capture the raw payload boundary immediately after CSV read.

    This list is the only allowed input set for _atlas_row_hash.
    """
    source_columns = list(df.columns)

    if not source_columns:
        raise ValueError("Cannot load source file because it contains no columns.")

    metadata_collisions = sorted(set(source_columns).intersection(ATLAS_METADATA_COLUMNS))
    if metadata_collisions:
        raise ValueError(
            "Source file already contains reserved Atlas metadata columns: "
            f"{metadata_collisions}. Rename upstream columns before Bronze ingestion."
        )

    return source_columns


# -----------------------------------------------------------------------------
# DuckDB SQL builders
# -----------------------------------------------------------------------------


def build_normalised_value_expression(column_name: str) -> str:
    """
    Build the source-value normalisation expression used for row hashing.

    Rules implemented in DuckDB:
    - cast to VARCHAR
    - trim leading/trailing whitespace
    - convert SQL NULL to <NULL>

    Source values loaded from CSV are preserved in the output table; this
    expression is used only for the hash payload.
    """
    col = quote_identifier(column_name)
    return f"COALESCE(TRIM(CAST({col} AS VARCHAR)), {sql_string_literal(NULL_TOKEN)})"



def build_duckdb_row_hash_expression(source_columns: list[str]) -> str:
    """
    Build the DuckDB-native json-array MD5 hash expression.

    Python owns the contract and source column order; DuckDB executes the
    expensive vectorised hashing work.
    """
    normalised_values = ",\n                ".join(
        build_normalised_value_expression(column)
        for column in source_columns
    )

    return (
        "md5("
        "to_json("
        "list_value(\n                "
        f"{normalised_values}"
        "\n            )"
        ")"
        ")"
    )



def build_source_select_list(source_columns: list[str]) -> str:
    """Build an explicit SELECT list for original source columns."""
    return ",\n            ".join(quote_identifier(column) for column in source_columns)


# -----------------------------------------------------------------------------
# DuckDB operations
# -----------------------------------------------------------------------------


def initialise_duckdb(connection: duckdb.DuckDBPyConnection) -> None:
    """Create required schemas and load-audit table."""
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(BRONZE_SCHEMA)}")

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(BRONZE_SCHEMA)}.{quote_identifier(AUDIT_TABLE)} (
            source_file_path VARCHAR,
            source_file_name VARCHAR,
            target_schema VARCHAR,
            target_table VARCHAR,
            rows_loaded BIGINT,
            source_column_count BIGINT,
            final_column_count BIGINT,
            source_file_size_bytes BIGINT,
            ingested_at_utc VARCHAR,
            hash_encoding_method VARCHAR,
            load_status VARCHAR,
            error_message VARCHAR
        )
        """
    )

    # Backward-compatible migration for earlier 11-column audit table versions.
    connection.execute(
        f"""
        ALTER TABLE {quote_identifier(BRONZE_SCHEMA)}.{quote_identifier(AUDIT_TABLE)}
        ADD COLUMN IF NOT EXISTS hash_encoding_method VARCHAR
        """
    )



def create_or_replace_bronze_table_fast(
    connection: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    df: pd.DataFrame,
    source_columns: list[str],
    csv_path: Path,
    ingested_at_utc: str,
) -> None:
    """
    Create/replace one Bronze table and compute metadata in DuckDB.

    This is the high-performance path. Python reads the source file and captures
    the source column boundary; DuckDB computes the JSON-array MD5 hash in a
    vectorised SQL operation.
    """
    temp_view_name = f"tmp_{table_name}"
    connection.register(temp_view_name, df)

    source_select_list = build_source_select_list(source_columns)
    row_hash_expression = build_duckdb_row_hash_expression(source_columns)

    try:
        connection.execute(
            f"""
            CREATE OR REPLACE TABLE
                {quote_identifier(BRONZE_SCHEMA)}.{quote_identifier(table_name)}
            AS
            SELECT
                {source_select_list},
                {row_hash_expression} AS {quote_identifier('_atlas_row_hash')},
                {sql_string_literal(ingested_at_utc)} AS {quote_identifier('_atlas_ingested_at')},
                {sql_string_literal(csv_path.name)} AS {quote_identifier('_atlas_source_file')}
            FROM {quote_identifier(temp_view_name)}
            """
        )
    finally:
        connection.unregister(temp_view_name)



def append_load_audit(
    connection: duckdb.DuckDBPyConnection,
    results: Iterable[BronzeLoadResult],
) -> None:
    """Append load results into bronze._atlas_load_audit."""
    rows = [result.__dict__ for result in results]
    if not rows:
        return

    audit_df = pd.DataFrame(rows)
    connection.register("tmp_atlas_load_audit", audit_df)

    try:
        connection.execute(
            f"""
            INSERT INTO {quote_identifier(BRONZE_SCHEMA)}.{quote_identifier(AUDIT_TABLE)} (
                source_file_path,
                source_file_name,
                target_schema,
                target_table,
                rows_loaded,
                source_column_count,
                final_column_count,
                source_file_size_bytes,
                ingested_at_utc,
                hash_encoding_method,
                load_status,
                error_message
            )
            SELECT
                source_file_path,
                source_file_name,
                target_schema,
                target_table,
                rows_loaded,
                source_column_count,
                final_column_count,
                source_file_size_bytes,
                ingested_at_utc,
                hash_encoding_method,
                load_status,
                error_message
            FROM tmp_atlas_load_audit
            """
        )
    finally:
        connection.unregister("tmp_atlas_load_audit")


# -----------------------------------------------------------------------------
# Main load orchestration
# -----------------------------------------------------------------------------


def load_one_csv(
    connection: duckdb.DuckDBPyConnection,
    *,
    csv_path: Path,
    raw_dir: Path,
    ingested_at_utc: str,
) -> BronzeLoadResult:
    """Load one CSV into a replaceable Bronze table."""
    table_name = table_name_from_csv_path(csv_path, raw_dir)

    LOGGER.info("Loading %s -> %s.%s", csv_path, BRONZE_SCHEMA, table_name)

    df = read_source_csv(csv_path)
    source_columns = capture_source_columns(df)

    create_or_replace_bronze_table_fast(
        connection,
        table_name=table_name,
        df=df,
        source_columns=source_columns,
        csv_path=csv_path,
        ingested_at_utc=ingested_at_utc,
    )

    return BronzeLoadResult(
        source_file_path=str(csv_path),
        source_file_name=csv_path.name,
        target_schema=BRONZE_SCHEMA,
        target_table=table_name,
        rows_loaded=len(df),
        source_column_count=len(source_columns),
        final_column_count=len(source_columns) + len(ATLAS_METADATA_COLUMNS),
        source_file_size_bytes=csv_path.stat().st_size,
        ingested_at_utc=ingested_at_utc,
        hash_encoding_method=HASH_ENCODING_METHOD,
        load_status="SUCCESS",
    )



def load_raw_to_duckdb(
    *,
    raw_dir: Path,
    database_path: Path,
    continue_on_error: bool = False,
) -> list[BronzeLoadResult]:
    """Load every raw CSV into the DuckDB Bronze schema."""
    raw_dir = raw_dir.resolve()
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    ingested_at_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    csv_files = discover_raw_csv_files(raw_dir)

    LOGGER.info("Starting Atlas Bronze load")
    LOGGER.info("Raw directory: %s", raw_dir)
    LOGGER.info("Database path: %s", database_path)
    LOGGER.info("CSV files discovered: %s", len(csv_files))
    LOGGER.info("Ingestion timestamp UTC: %s", ingested_at_utc)
    LOGGER.info("Hash encoding method: %s", HASH_ENCODING_METHOD)

    results: list[BronzeLoadResult] = []

    with duckdb.connect(str(database_path)) as connection:
        initialise_duckdb(connection)

        for csv_path in csv_files:
            try:
                result = load_one_csv(
                    connection,
                    csv_path=csv_path,
                    raw_dir=raw_dir,
                    ingested_at_utc=ingested_at_utc,
                )
                LOGGER.info(
                    "Loaded %s rows into %s.%s",
                    f"{result.rows_loaded:,}",
                    result.target_schema,
                    result.target_table,
                )
                results.append(result)

            except Exception as exc:
                LOGGER.exception("Failed loading CSV: %s", csv_path)

                failure = BronzeLoadResult(
                    source_file_path=str(csv_path),
                    source_file_name=csv_path.name,
                    target_schema=BRONZE_SCHEMA,
                    target_table=table_name_from_csv_path(csv_path, raw_dir),
                    rows_loaded=0,
                    source_column_count=0,
                    final_column_count=0,
                    source_file_size_bytes=csv_path.stat().st_size if csv_path.exists() else 0,
                    ingested_at_utc=ingested_at_utc,
                    hash_encoding_method=HASH_ENCODING_METHOD,
                    load_status="FAILED",
                    error_message=str(exc),
                )
                results.append(failure)

                if not continue_on_error:
                    append_load_audit(connection, results)
                    raise

        append_load_audit(connection, results)

    success_count = sum(result.load_status == "SUCCESS" for result in results)
    failure_count = sum(result.load_status == "FAILED" for result in results)
    total_rows = sum(result.rows_loaded for result in results)

    LOGGER.info("Atlas Bronze load complete")
    LOGGER.info("Successful files: %s", success_count)
    LOGGER.info("Failed files: %s", failure_count)
    LOGGER.info("Total rows loaded: %s", f"{total_rows:,}")

    return results


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    project_root = resolve_project_root()

    parser = argparse.ArgumentParser(
        description="Load Project Atlas raw CSV files into DuckDB Bronze tables."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=project_root / "data" / "raw",
        help="Path to raw CSV directory. Defaults to data/raw under project root.",
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        default=project_root / "data" / "warehouse" / "atlas.duckdb",
        help="DuckDB database path. Defaults to data/warehouse/atlas.duckdb.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue loading remaining files if one CSV fails.",
    )
    return parser



def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )



def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()

    try:
        results = load_raw_to_duckdb(
            raw_dir=args.raw_dir,
            database_path=args.database_path,
            continue_on_error=args.continue_on_error,
        )
    except Exception as exc:
        LOGGER.critical("Bronze load failed: %s", exc)
        return 1

    failures = [result for result in results if result.load_status == "FAILED"]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
