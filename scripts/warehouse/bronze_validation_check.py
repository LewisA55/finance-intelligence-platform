"""
Project Atlas / Finance Intelligence Platform
Phase 4 - DuckDB Bronze Warehouse Validation Check

Purpose
-------
Validates the Phase 4 Bronze ingestion layer after running:

    scripts/warehouse/load_raw_to_duckdb.py

This script is intentionally separate from the loader. The loader performs
ingestion; this validator performs post-load assurance before dbt Silver models
consume Bronze tables.

Validation scope
----------------
1. Latest Bronze load run exists.
2. Latest load has zero failed files.
3. Latest load has the expected number of successful source files.
4. Latest load uses the locked hash encoding method.
5. Every loaded Bronze source table exists.
6. Every loaded Bronze source table has the three Atlas metadata columns.
7. final_column_count = source_column_count + 3 in the audit table.
8. No loaded Bronze source table contains NULL metadata values.
9. Row counts in audit table match physical DuckDB table counts.
10. Duplicate _atlas_row_hash values are flagged as warnings, not hard failures.
11. source_output_inventory.csv alignment is checked where the governance table is available.

Design stance
-------------
This is a Bronze QA gate, not a Silver transformation model. It should not apply
business typing, accounting calculations, or source-system interpretation.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import duckdb
    import pandas as pd
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "Missing dependency. Install required packages with: pip install pandas duckdb"
    ) from exc


LOGGER = logging.getLogger("AtlasBronzeValidator")

BRONZE_SCHEMA = "bronze"
AUDIT_TABLE = "_atlas_load_audit"

EXPECTED_METADATA_COLUMNS = [
    "_atlas_row_hash",
    "_atlas_ingested_at",
    "_atlas_source_file",
]

EXPECTED_HASH_ENCODING_METHOD = "duckdb_json_array_v1"
DEFAULT_EXPECTED_FILE_COUNT = 39


@dataclass(frozen=True)
class ValidationResult:
    check_name: str
    check_status: str  # PASS, WARN, FAIL
    severity: str      # INFO, LOW, MEDIUM, HIGH
    details: str


# -----------------------------------------------------------------------------
# Path / identifier helpers
# -----------------------------------------------------------------------------


def resolve_project_root() -> Path:
    """
    Resolve the repository root from scripts/warehouse/bronze_validation_check.py.

    Expected project layout:
        project_root/
            data/warehouse/atlas.duckdb
            scripts/warehouse/bronze_validation_check.py
    """
    return Path(__file__).resolve().parents[2]


def quote_identifier(identifier: str) -> str:
    """Safely quote a DuckDB identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def qualified_table(schema_name: str, table_name: str) -> str:
    """Return a safely quoted schema-qualified table reference."""
    return f"{quote_identifier(schema_name)}.{quote_identifier(table_name)}"


# -----------------------------------------------------------------------------
# Validation helpers
# -----------------------------------------------------------------------------


def add_result(
    results: list[ValidationResult],
    *,
    check_name: str,
    check_status: str,
    severity: str,
    details: str,
) -> None:
    results.append(
        ValidationResult(
            check_name=check_name,
            check_status=check_status,
            severity=severity,
            details=details,
        )
    )


def table_exists(
    connection: duckdb.DuckDBPyConnection,
    *,
    schema_name: str,
    table_name: str,
) -> bool:
    return bool(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = ?
              AND table_name = ?
            """,
            [schema_name, table_name],
        ).fetchone()[0]
    )


def get_table_columns(
    connection: duckdb.DuckDBPyConnection,
    *,
    schema_name: str,
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ?
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema_name, table_name],
    ).fetchall()
    return [row[0] for row in rows]


def get_latest_ingestion_timestamp(connection: duckdb.DuckDBPyConnection) -> str | None:
    row = connection.execute(
        f"""
        SELECT MAX(ingested_at_utc)
        FROM {qualified_table(BRONZE_SCHEMA, AUDIT_TABLE)}
        """
    ).fetchone()
    return row[0] if row else None


def load_latest_audit(
    connection: duckdb.DuckDBPyConnection,
    *,
    latest_ingested_at_utc: str,
) -> pd.DataFrame:
    return connection.execute(
        f"""
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
        FROM {qualified_table(BRONZE_SCHEMA, AUDIT_TABLE)}
        WHERE ingested_at_utc = ?
        ORDER BY target_table
        """,
        [latest_ingested_at_utc],
    ).fetchdf()


def get_physical_row_count(
    connection: duckdb.DuckDBPyConnection,
    *,
    schema_name: str,
    table_name: str,
) -> int:
    return int(
        connection.execute(
            f"SELECT COUNT(*) FROM {qualified_table(schema_name, table_name)}"
        ).fetchone()[0]
    )


def count_null_metadata_rows(
    connection: duckdb.DuckDBPyConnection,
    *,
    schema_name: str,
    table_name: str,
) -> int:
    null_conditions = " OR ".join(
        f"{quote_identifier(column)} IS NULL"
        for column in EXPECTED_METADATA_COLUMNS
    )

    return int(
        connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {qualified_table(schema_name, table_name)}
            WHERE {null_conditions}
            """
        ).fetchone()[0]
    )


def count_duplicate_hash_rows(
    connection: duckdb.DuckDBPyConnection,
    *,
    schema_name: str,
    table_name: str,
) -> int:
    """
    Return duplicate hash rows beyond the first occurrence.

    Duplicate hashes are warnings in Bronze, not hard failures, because exact
    duplicate raw rows can legitimately exist in some source extracts.
    """
    return int(
        connection.execute(
            f"""
            WITH hash_counts AS (
                SELECT
                    _atlas_row_hash,
                    COUNT(*) AS row_count
                FROM {qualified_table(schema_name, table_name)}
                GROUP BY _atlas_row_hash
                HAVING COUNT(*) > 1
            )
            SELECT COALESCE(SUM(row_count - 1), 0)
            FROM hash_counts
            """
        ).fetchone()[0]
    )


def get_source_inventory_df(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame | None:
    inventory_table = "governance__source_output_inventory"

    if not table_exists(
        connection,
        schema_name=BRONZE_SCHEMA,
        table_name=inventory_table,
    ):
        return None

    return connection.execute(
        f"SELECT * FROM {qualified_table(BRONZE_SCHEMA, inventory_table)}"
    ).fetchdf()


# -----------------------------------------------------------------------------
# Validation checks
# -----------------------------------------------------------------------------


def validate_latest_load_summary(
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
    expected_file_count: int,
) -> None:
    failed_count = int((audit_df["load_status"] == "FAILED").sum())
    success_count = int((audit_df["load_status"] == "SUCCESS").sum())
    total_rows = int(pd.to_numeric(audit_df["rows_loaded"], errors="coerce").fillna(0).sum())

    if failed_count == 0:
        add_result(
            results,
            check_name="latest_load_has_zero_failures",
            check_status="PASS",
            severity="INFO",
            details=f"Latest load has {success_count:,} successful files and 0 failed files.",
        )
    else:
        add_result(
            results,
            check_name="latest_load_has_zero_failures",
            check_status="FAIL",
            severity="HIGH",
            details=f"Latest load has {failed_count:,} failed files.",
        )

    if success_count == expected_file_count:
        add_result(
            results,
            check_name="expected_successful_file_count",
            check_status="PASS",
            severity="INFO",
            details=f"Successful file count matches expected count: {expected_file_count:,}.",
        )
    else:
        add_result(
            results,
            check_name="expected_successful_file_count",
            check_status="FAIL",
            severity="HIGH",
            details=(
                f"Successful file count {success_count:,} does not match "
                f"expected count {expected_file_count:,}."
            ),
        )

    add_result(
        results,
        check_name="latest_load_total_rows",
        check_status="PASS",
        severity="INFO",
        details=f"Latest load row count: {total_rows:,}.",
    )


def validate_hash_encoding_method(
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
    expected_hash_encoding_method: str,
) -> None:
    observed_methods = sorted(
        {
            str(value)
            for value in audit_df["hash_encoding_method"].dropna().unique().tolist()
        }
    )

    if observed_methods == [expected_hash_encoding_method]:
        add_result(
            results,
            check_name="hash_encoding_method_locked",
            check_status="PASS",
            severity="INFO",
            details=f"All files use {expected_hash_encoding_method}.",
        )
    else:
        add_result(
            results,
            check_name="hash_encoding_method_locked",
            check_status="FAIL",
            severity="HIGH",
            details=(
                f"Observed hash encoding methods {observed_methods}; "
                f"expected only {expected_hash_encoding_method}."
            ),
        )


def validate_audit_column_counts(
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
) -> None:
    audit_df = audit_df.copy()
    audit_df["source_column_count"] = pd.to_numeric(
        audit_df["source_column_count"],
        errors="coerce",
    )
    audit_df["final_column_count"] = pd.to_numeric(
        audit_df["final_column_count"],
        errors="coerce",
    )

    bad_df = audit_df[
        audit_df["final_column_count"]
        != audit_df["source_column_count"] + len(EXPECTED_METADATA_COLUMNS)
    ]

    if bad_df.empty:
        add_result(
            results,
            check_name="final_column_count_equals_source_plus_metadata",
            check_status="PASS",
            severity="INFO",
            details=(
                "All latest-run audit rows satisfy "
                f"final_column_count = source_column_count + {len(EXPECTED_METADATA_COLUMNS)}."
            ),
        )
    else:
        examples = bad_df[
            ["target_table", "source_column_count", "final_column_count"]
        ].head(5).to_dict("records")
        add_result(
            results,
            check_name="final_column_count_equals_source_plus_metadata",
            check_status="FAIL",
            severity="HIGH",
            details=f"{len(bad_df):,} audit rows violate column count rule. Examples: {examples}",
        )


def validate_table_existence_and_metadata(
    connection: duckdb.DuckDBPyConnection,
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
) -> None:
    missing_tables: list[str] = []
    missing_metadata: list[dict[str, object]] = []

    for row in audit_df.itertuples(index=False):
        if str(row.load_status) != "SUCCESS":
            continue

        table_name = str(row.target_table)
        schema_name = str(row.target_schema)

        if not table_exists(connection, schema_name=schema_name, table_name=table_name):
            missing_tables.append(f"{schema_name}.{table_name}")
            continue

        columns = get_table_columns(connection, schema_name=schema_name, table_name=table_name)
        missing_columns = [
            column for column in EXPECTED_METADATA_COLUMNS
            if column not in columns
        ]

        if missing_columns:
            missing_metadata.append(
                {
                    "table": f"{schema_name}.{table_name}",
                    "missing_metadata_columns": missing_columns,
                }
            )

    if not missing_tables:
        add_result(
            results,
            check_name="all_audited_bronze_tables_exist",
            check_status="PASS",
            severity="INFO",
            details="Every SUCCESS audit row has a physical Bronze table.",
        )
    else:
        add_result(
            results,
            check_name="all_audited_bronze_tables_exist",
            check_status="FAIL",
            severity="HIGH",
            details=f"Missing Bronze tables: {missing_tables[:10]}",
        )

    if not missing_metadata:
        add_result(
            results,
            check_name="all_bronze_tables_have_atlas_metadata_columns",
            check_status="PASS",
            severity="INFO",
            details=f"All loaded Bronze tables include {EXPECTED_METADATA_COLUMNS}.",
        )
    else:
        add_result(
            results,
            check_name="all_bronze_tables_have_atlas_metadata_columns",
            check_status="FAIL",
            severity="HIGH",
            details=f"Tables missing metadata columns: {missing_metadata[:10]}",
        )


def validate_row_counts_and_metadata_values(
    connection: duckdb.DuckDBPyConnection,
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
) -> None:
    row_count_mismatches: list[dict[str, object]] = []
    null_metadata_tables: list[dict[str, object]] = []
    duplicate_hash_warnings: list[dict[str, object]] = []

    for row in audit_df.itertuples(index=False):
        if str(row.load_status) != "SUCCESS":
            continue

        table_name = str(row.target_table)
        schema_name = str(row.target_schema)
        audit_rows_loaded = int(row.rows_loaded)

        if not table_exists(connection, schema_name=schema_name, table_name=table_name):
            continue

        physical_rows = get_physical_row_count(
            connection,
            schema_name=schema_name,
            table_name=table_name,
        )

        if physical_rows != audit_rows_loaded:
            row_count_mismatches.append(
                {
                    "table": f"{schema_name}.{table_name}",
                    "audit_rows_loaded": audit_rows_loaded,
                    "physical_rows": physical_rows,
                }
            )

        null_metadata_count = count_null_metadata_rows(
            connection,
            schema_name=schema_name,
            table_name=table_name,
        )

        if null_metadata_count:
            null_metadata_tables.append(
                {
                    "table": f"{schema_name}.{table_name}",
                    "null_metadata_rows": null_metadata_count,
                }
            )

        duplicate_hash_count = count_duplicate_hash_rows(
            connection,
            schema_name=schema_name,
            table_name=table_name,
        )

        if duplicate_hash_count:
            duplicate_hash_warnings.append(
                {
                    "table": f"{schema_name}.{table_name}",
                    "duplicate_hash_rows": duplicate_hash_count,
                }
            )

    if not row_count_mismatches:
        add_result(
            results,
            check_name="audit_row_counts_match_physical_tables",
            check_status="PASS",
            severity="INFO",
            details="All audit row counts match physical Bronze table counts.",
        )
    else:
        add_result(
            results,
            check_name="audit_row_counts_match_physical_tables",
            check_status="FAIL",
            severity="HIGH",
            details=f"Row count mismatches: {row_count_mismatches[:10]}",
        )

    if not null_metadata_tables:
        add_result(
            results,
            check_name="metadata_values_not_null",
            check_status="PASS",
            severity="INFO",
            details="No loaded Bronze table contains NULL Atlas metadata values.",
        )
    else:
        add_result(
            results,
            check_name="metadata_values_not_null",
            check_status="FAIL",
            severity="HIGH",
            details=f"Tables with NULL metadata values: {null_metadata_tables[:10]}",
        )

    if not duplicate_hash_warnings:
        add_result(
            results,
            check_name="duplicate_row_hash_scan",
            check_status="PASS",
            severity="INFO",
            details="No duplicate _atlas_row_hash values detected in loaded Bronze tables.",
        )
    else:
        add_result(
            results,
            check_name="duplicate_row_hash_scan",
            check_status="WARN",
            severity="MEDIUM",
            details=(
                "Duplicate row hashes detected. This can be valid for exact duplicate "
                f"raw rows, but should be reviewed. Examples: {duplicate_hash_warnings[:10]}"
            ),
        )


def validate_source_inventory_alignment(
    connection: duckdb.DuckDBPyConnection,
    results: list[ValidationResult],
    *,
    audit_df: pd.DataFrame,
) -> None:
    inventory_df = get_source_inventory_df(connection)

    if inventory_df is None:
        add_result(
            results,
            check_name="source_output_inventory_alignment",
            check_status="WARN",
            severity="LOW",
            details="governance__source_output_inventory table not found; alignment check skipped.",
        )
        return

    lower_columns = {column.lower(): column for column in inventory_df.columns}

    file_col = next(
        (
            lower_columns[name]
            for name in [
                "source_file_name",
                "file_name",
                "filename",
                "source_filename",
            ]
            if name in lower_columns
        ),
        None,
    )

    row_count_col = next(
        (
            lower_columns[name]
            for name in [
                "row_count",
                "rows",
                "record_count",
                "source_row_count",
            ]
            if name in lower_columns
        ),
        None,
    )

    if file_col is None or row_count_col is None:
        add_result(
            results,
            check_name="source_output_inventory_alignment",
            check_status="WARN",
            severity="LOW",
            details=(
                "governance__source_output_inventory exists, but expected filename "
                f"and row-count columns were not detected. Columns: {list(inventory_df.columns)}"
            ),
        )
        return

    inventory_check_df = inventory_df[[file_col, row_count_col]].copy()
    inventory_check_df.columns = ["source_file_name", "inventory_row_count"]
    inventory_check_df["source_file_name"] = inventory_check_df["source_file_name"].astype(str)
    inventory_check_df["inventory_row_count"] = pd.to_numeric(
        inventory_check_df["inventory_row_count"],
        errors="coerce",
    )

    audit_check_df = audit_df[["source_file_name", "rows_loaded"]].copy()
    audit_check_df["source_file_name"] = audit_check_df["source_file_name"].astype(str)
    audit_check_df["rows_loaded"] = pd.to_numeric(
        audit_check_df["rows_loaded"],
        errors="coerce",
    )

    merged = inventory_check_df.merge(
        audit_check_df,
        on="source_file_name",
        how="inner",
    )

    if merged.empty:
        add_result(
            results,
            check_name="source_output_inventory_alignment",
            check_status="WARN",
            severity="LOW",
            details=(
                "No overlapping source_file_name values found between source inventory "
                "and latest Bronze audit."
            ),
        )
        return

    mismatch_df = merged[merged["inventory_row_count"] != merged["rows_loaded"]]

    if mismatch_df.empty:
        add_result(
            results,
            check_name="source_output_inventory_alignment",
            check_status="PASS",
            severity="INFO",
            details=f"Source inventory row counts match latest Bronze audit for {len(merged):,} files.",
        )
    else:
        examples = mismatch_df.head(10).to_dict("records")
        add_result(
            results,
            check_name="source_output_inventory_alignment",
            check_status="FAIL",
            severity="HIGH",
            details=f"Source inventory row-count mismatches detected. Examples: {examples}",
        )


# -----------------------------------------------------------------------------
# Orchestration / output
# -----------------------------------------------------------------------------


def run_validation(
    *,
    database_path: Path,
    expected_file_count: int,
    expected_hash_encoding_method: str,
    output_csv_path: Path | None = None,
) -> list[ValidationResult]:
    database_path = database_path.resolve()

    if not database_path.exists():
        raise FileNotFoundError(f"DuckDB database not found: {database_path}")

    results: list[ValidationResult] = []

    with duckdb.connect(str(database_path)) as connection:
        if not table_exists(
            connection,
            schema_name=BRONZE_SCHEMA,
            table_name=AUDIT_TABLE,
        ):
            add_result(
                results,
                check_name="audit_table_exists",
                check_status="FAIL",
                severity="HIGH",
                details=f"{BRONZE_SCHEMA}.{AUDIT_TABLE} does not exist.",
            )
            return results

        add_result(
            results,
            check_name="audit_table_exists",
            check_status="PASS",
            severity="INFO",
            details=f"{BRONZE_SCHEMA}.{AUDIT_TABLE} exists.",
        )

        latest_ingested_at_utc = get_latest_ingestion_timestamp(connection)

        if not latest_ingested_at_utc:
            add_result(
                results,
                check_name="latest_ingestion_timestamp_exists",
                check_status="FAIL",
                severity="HIGH",
                details="No ingested_at_utc value found in Bronze audit table.",
            )
            return results

        add_result(
            results,
            check_name="latest_ingestion_timestamp_exists",
            check_status="PASS",
            severity="INFO",
            details=f"Latest ingestion timestamp: {latest_ingested_at_utc}.",
        )

        audit_df = load_latest_audit(
            connection,
            latest_ingested_at_utc=latest_ingested_at_utc,
        )

        if audit_df.empty:
            add_result(
                results,
                check_name="latest_audit_rows_exist",
                check_status="FAIL",
                severity="HIGH",
                details=f"No audit rows found for latest timestamp {latest_ingested_at_utc}.",
            )
            return results

        add_result(
            results,
            check_name="latest_audit_rows_exist",
            check_status="PASS",
            severity="INFO",
            details=f"Latest audit contains {len(audit_df):,} rows.",
        )

        validate_latest_load_summary(
            results,
            audit_df=audit_df,
            expected_file_count=expected_file_count,
        )

        validate_hash_encoding_method(
            results,
            audit_df=audit_df,
            expected_hash_encoding_method=expected_hash_encoding_method,
        )

        validate_audit_column_counts(
            results,
            audit_df=audit_df,
        )

        validate_table_existence_and_metadata(
            connection,
            results,
            audit_df=audit_df,
        )

        validate_row_counts_and_metadata_values(
            connection,
            results,
            audit_df=audit_df,
        )

        validate_source_inventory_alignment(
            connection,
            results,
            audit_df=audit_df,
        )

    if output_csv_path is not None:
        output_csv_path = output_csv_path.resolve()
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([result.__dict__ for result in results]).to_csv(
            output_csv_path,
            index=False,
        )
        LOGGER.info("Validation results written to %s", output_csv_path)

    return results


def print_results(results: Iterable[ValidationResult]) -> None:
    results = list(results)

    if not results:
        print("No validation results produced.")
        return

    df = pd.DataFrame([result.__dict__ for result in results])

    print("\nAtlas Bronze Validation Results")
    print("=" * 80)

    for row in df.itertuples(index=False):
        print(f"[{row.check_status}] {row.check_name} ({row.severity})")
        print(f"    {row.details}")

    print("=" * 80)

    summary = (
        df.groupby(["check_status", "severity"], dropna=False)
        .size()
        .reset_index(name="check_count")
        .sort_values(["check_status", "severity"])
    )

    print("\nSummary")
    print(summary.to_string(index=False))


def has_failures(results: Iterable[ValidationResult]) -> bool:
    return any(result.check_status == "FAIL" for result in results)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    project_root = resolve_project_root()

    parser = argparse.ArgumentParser(
        description="Validate Project Atlas DuckDB Bronze ingestion outputs."
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        default=project_root / "data" / "warehouse" / "atlas.duckdb",
        help="DuckDB database path. Defaults to data/warehouse/atlas.duckdb.",
    )
    parser.add_argument(
        "--expected-file-count",
        type=int,
        default=DEFAULT_EXPECTED_FILE_COUNT,
        help=f"Expected successful raw CSV file count. Defaults to {DEFAULT_EXPECTED_FILE_COUNT}.",
    )
    parser.add_argument(
        "--expected-hash-encoding-method",
        type=str,
        default=EXPECTED_HASH_ENCODING_METHOD,
        help=f"Expected hash encoding method. Defaults to {EXPECTED_HASH_ENCODING_METHOD}.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=project_root / "data" / "warehouse" / "bronze_validation_results.csv",
        help="Optional CSV output path for validation results.",
    )
    parser.add_argument(
        "--no-output-csv",
        action="store_true",
        help="Do not write validation results to CSV.",
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

    output_csv_path = None if args.no_output_csv else args.output_csv

    try:
        results = run_validation(
            database_path=args.database_path,
            expected_file_count=args.expected_file_count,
            expected_hash_encoding_method=args.expected_hash_encoding_method,
            output_csv_path=output_csv_path,
        )
    except Exception as exc:
        LOGGER.critical("Bronze validation failed to execute: %s", exc)
        return 1

    print_results(results)

    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    sys.exit(main())
