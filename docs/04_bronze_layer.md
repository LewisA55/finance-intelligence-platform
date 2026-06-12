# Bronze Layer

The Bronze layer is the faithful raw ingestion boundary for Project Atlas.

Raw CSV source files are loaded into DuckDB tables with minimal transformation. Bronze is responsible for repeatable ingestion, source preservation, and technical lineage.

## Purpose

Bronze provides:

- one table per source file;
- consistent ingestion metadata;
- row-count and source inventory validation;
- a stable source boundary for dbt Silver models.

Bronze does not apply finance logic, semantic conformance, deduplication, or KPI calculations. Those responsibilities begin in Silver and Gold.

## Table Naming

Each raw file maps to a Bronze table using:

```text
<domain>__<file_name_without_extension>
```

Examples:

| Raw file | Bronze source |
| --- | --- |
| `data/raw/billing/billing_invoices.csv` | `bronze.billing__billing_invoices` |
| `data/raw/procurement/vendor_payments.csv` | `bronze.procurement__vendor_payments` |
| `data/raw/planning/forecast_lines.csv` | `bronze.planning__forecast_lines` |

## Metadata Contract

Every Bronze table includes:

| Column | Purpose |
| --- | --- |
| `_atlas_row_hash` | Deterministic fingerprint of the original source row values. |
| `_atlas_ingested_at` | Timestamp of the Bronze load run. |
| `_atlas_source_file` | Source filename loaded into Bronze. |

## Operating Commands

Load Bronze:

```bash
python scripts/warehouse/load_raw_to_duckdb.py
```

Validate Bronze:

```bash
python scripts/warehouse/bronze_validation_check.py
```

## Validation Scope

The Bronze validation checkpoint verifies:

- audited source files were loaded;
- expected Bronze tables exist;
- required metadata columns exist;
- row counts reconcile to the latest source inventory where applicable;
- load audit records are available.

## Version Control Policy

The DuckDB database and Bronze validation output files are generated artifacts and are not normally tracked:

```text
data/warehouse/atlas.duckdb
data/warehouse/bronze_validation_results.csv
```
