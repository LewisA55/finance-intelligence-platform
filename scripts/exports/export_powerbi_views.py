from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse" / "atlas.duckdb"
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "powerbi"

POWERBI_TABLES = [
    # Executive reporting surface
    "gold.mart_executive_cfo_command_center",

    # Supporting marts / drilldown surfaces
    "gold.mart_financial_performance",
    "gold.mart_saas_arr_movement",
    "gold.mart_saas_retention",
    "gold.mart_o2c_customer_collections",
    "gold.mart_revenue_waterfall",
    "gold.mart_deferred_revenue_control",
    "gold.mart_workforce_cost_control",
    "gold.mart_ap_working_capital_control",

    # Conformed dimensions
    "gold.dim_date",
    "gold.dim_region",
    "gold.dim_department",
    "gold.dim_gl_account",
    "gold.dim_customer",
    "gold.dim_vendor",
    "gold.dim_employee",
    "gold.dim_budget_version",
    "gold.dim_forecast_scenario",
]


def quote_qualified_name(table_name: str) -> str:
    schema_name, model_name = table_name.split(".", maxsplit=1)
    return f'"{schema_name}"."{model_name}"'


def export_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    export_root_dir: Path,
    export_format: str,
) -> tuple[Path, int]:
    _, model_name = table_name.split(".", maxsplit=1)

    format_dir = export_root_dir / export_format
    format_dir.mkdir(parents=True, exist_ok=True)

    output_path = format_dir / f"{model_name}.{export_format}"
    qualified_name = quote_qualified_name(table_name)
    output_sql_literal = str(output_path).replace("'", "''")

    row_count = connection.execute(
        f"select count(*) from {qualified_name}"
    ).fetchone()[0]

    if export_format == "csv":
        copy_options = "HEADER, DELIMITER ','"
    elif export_format == "parquet":
        copy_options = "FORMAT PARQUET, COMPRESSION ZSTD"
    else:
        raise ValueError(f"Unsupported export format: {export_format}")

    connection.execute(
        f"COPY (SELECT * FROM {qualified_name}) "
        f"TO '{output_sql_literal}' "
        f"WITH ({copy_options})"
    )

    return output_path, row_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export selected Gold marts and dimensions to CSV and/or Parquet for Power BI import."
    )
    parser.add_argument(
        "--warehouse",
        type=Path,
        default=DEFAULT_WAREHOUSE_PATH,
        help="Path to the local DuckDB warehouse.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Directory where Power BI export files will be written.",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv", "both"],
        default="both",
        help="Export format. Parquet is smaller and preserves types; CSV is useful as a fallback.",
    )

    args = parser.parse_args()

    if not args.warehouse.exists():
        raise FileNotFoundError(f"DuckDB warehouse not found: {args.warehouse}")

    export_formats = ["csv", "parquet"] if args.format == "both" else [args.format]

    with duckdb.connect(str(args.warehouse), read_only=True) as connection:
        for table_name in POWERBI_TABLES:
            for export_format in export_formats:
                output_path, row_count = export_table(
                    connection=connection,
                    table_name=table_name,
                    export_root_dir=args.output_dir,
                    export_format=export_format,
                )
                print(f"Exported {table_name} -> {output_path} rows={row_count:,}")


if __name__ == "__main__":
    main()