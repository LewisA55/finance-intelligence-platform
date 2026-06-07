# 06 — Bronze Warehouse

## Project Atlas / Finance Intelligence Platform

### Phase 4.1 — DuckDB Bronze Raw Ingestion Layer

This document defines the Bronze ingestion boundary for Project Atlas. It explains how raw CSV source files are loaded into the DuckDB warehouse, what guarantees the Bronze layer provides, and how the layer is validated before downstream dbt Silver modelling begins.

---

## 1. Purpose

The Bronze layer is the faithful raw ingestion layer for Project Atlas.

Its purpose is to:

- ingest all generated raw CSV source files into DuckDB;
- preserve source-system structure without applying business interpretation;
- add consistent Atlas metadata for auditability and lineage;
- create a repeatable validation checkpoint before dbt transformations;
- provide a stable source foundation for Silver and Gold modelling.

The Bronze layer is not responsible for accounting logic, KPI calculation, type casting, dimensional modelling, or business-rule interpretation. Those responsibilities begin in dbt Silver.

---

## 2. Source-to-Bronze Mapping

Raw CSV files are loaded from:

```text
data/raw/<domain>/<file_name>.csv
```

into the DuckDB database:

```text
data/warehouse/atlas.duckdb
```

under the `bronze` schema.

The target table naming convention is:

```text
bronze.<domain>__<file_name>
```

Examples:

```text
data/raw/accounting/chart_of_accounts.csv
→ bronze.accounting__chart_of_accounts

data/raw/billing/billing_invoices.csv
→ bronze.billing__billing_invoices

data/raw/planning/variance_source_extract.csv
→ bronze.planning__variance_source_extract
```

The double underscore is an intentional namespace boundary between the raw source domain and the file-derived table name.

---

## 3. Bronze Design Principles

### 3.1 Faithful ingestion

Bronze preserves source-system payloads as closely as possible.

All source columns are loaded as `VARCHAR`. This prevents premature interpretation of:

- dates;
- posting periods;
- account codes;
- IDs;
- booleans;
- currencies;
- financial values;
- defect flags.

Type casting and semantic modelling are deferred to dbt Silver.

### 3.2 One raw file maps to one Bronze table

Each raw CSV maps to one Bronze table. The loader does not combine, aggregate, deduplicate, join, or reshape raw source files.

### 3.3 Metadata is appended after source boundary capture

The loader captures the raw payload boundary before adding Atlas metadata:

```python
source_columns = list(df.columns)
```

This is a primary Phase 4 invariant.

The captured source column list is the only allowed input into the row fingerprinting process. Operational metadata must never be included in the row hash.

---

## 4. Atlas Bronze Metadata Contract

Every Bronze source table receives three Atlas metadata columns:

| Column | Purpose | Audit justification |
|---|---|---|
| `_atlas_row_hash` | Detects upstream row mutation or pipeline drift | Proves whether the original source row changed |
| `_atlas_ingested_at` | Records the UTC timestamp of the warehouse load run | Proves when Atlas loaded the row |
| `_atlas_source_file` | Records the origin CSV filename | Proves where Atlas loaded the row from |

These fields are appended to the end of each Bronze table.

---

## 5. Row Hashing Standard

### 5.1 Hash method

The locked Phase 4.1 row hash method is:

```text
duckdb_json_array_v1
```

The conceptual standard is:

```text
_atlas_row_hash = MD5(JSON_ARRAY(ordered_normalised_source_values))
```

The implementation is executed inside DuckDB for performance, while Python still owns the ingestion contract and source-column boundary.

### 5.2 Source-only fingerprinting

The hash uses only original source CSV columns, in their exact native CSV order.

It excludes:

- `_atlas_row_hash`;
- `_atlas_ingested_at`;
- `_atlas_source_file`;
- row indexes;
- runtime state;
- future operational metadata fields.

### 5.3 Value normalisation

Before hashing, each source value is normalised as follows:

- cast to string;
- trim leading and trailing whitespace;
- convert null or missing values to the static token `<NULL>`;
- preserve source column order;
- structurally encode values as a JSON array before applying MD5.

This avoids delimiter-collision risk from simple string concatenation.

---

## 6. Load Audit Table

The loader maintains a central operational audit table:

```text
bronze._atlas_load_audit
```

This table records one audit row per source CSV per load run.

Key fields include:

| Column | Description |
|---|---|
| `source_file_path` | Full local path of the loaded CSV |
| `source_file_name` | Origin CSV filename |
| `target_schema` | Target DuckDB schema, normally `bronze` |
| `target_table` | Loaded Bronze table name |
| `rows_loaded` | Number of rows loaded into the target table |
| `source_column_count` | Number of original CSV source columns |
| `final_column_count` | Number of columns after Atlas metadata enrichment |
| `source_file_size_bytes` | Source CSV size in bytes |
| `ingested_at_utc` | UTC timestamp for the load run |
| `hash_encoding_method` | Hash standard used, currently `duckdb_json_array_v1` |
| `load_status` | `SUCCESS` or `FAILED` |
| `error_message` | Error detail for failed loads |

The audit table supports repeatable ingestion assurance and provides a bridge into future data observability checks.

---

## 7. Operating Instructions

### 7.1 Run the Bronze loader

From the project root:

```bash
python scripts/warehouse/load_raw_to_duckdb.py
```

Expected output:

```text
Atlas Bronze load complete
Successful files: 39
Failed files: 0
Total rows loaded: 2,520,661
```

### 7.2 Run the Bronze validation check

From the project root:

```bash
python scripts/warehouse/bronze_validation_check.py
```

The validator writes results to:

```text
data/warehouse/bronze_validation_results.csv
```

This CSV is an optional commit artefact. The DuckDB warehouse binary itself should not normally be committed.

---

## 8. Validation Framework

The Bronze validator checks the latest load run only.

Validation checks include:

1. `bronze._atlas_load_audit` exists.
2. Latest ingestion timestamp exists.
3. Latest audit contains rows.
4. Latest load has zero failed files.
5. Latest load has the expected successful file count.
6. Latest load uses `duckdb_json_array_v1`.
7. `final_column_count = source_column_count + 3`.
8. Every audited Bronze table physically exists.
9. Every loaded Bronze table has all three Atlas metadata columns.
10. Audit row counts match physical table row counts.
11. Atlas metadata values are not null.
12. Duplicate `_atlas_row_hash` values are scanned.
13. Source inventory row counts are compared against the latest Bronze audit where applicable.

Duplicate row hashes are treated as warnings, not automatic failures, because exact duplicate raw rows may be valid at Bronze. Silver models decide whether duplicates are invalid at business grain.

---

## 9. Latest Locked Validation Result

The Phase 4.1 Bronze ingestion layer passed validation with:

```text
PASS: 14
WARN: 0
FAIL: 0
```

Latest confirmed load:

```text
Ingestion timestamp UTC: 2026-06-07T22:07:31+00:00
Files loaded: 39
Failed files: 0
Rows loaded: 2,520,661
Hash encoding method: duckdb_json_array_v1
```

Confirmed outcomes:

- all audited Bronze tables exist;
- all loaded Bronze tables include `_atlas_row_hash`, `_atlas_ingested_at`, and `_atlas_source_file`;
- all audit row counts match physical DuckDB table counts;
- no null Atlas metadata values were detected;
- no duplicate row hashes were detected;
- source inventory row counts matched the latest Bronze audit for 37 files.

The two unmatched files are expected because governance outputs are themselves loaded into Bronze but are not part of the original source-output inventory manifest.

---

## 10. Git and Version Control Guidance

Commit the Bronze loader and validation scripts:

```bash
git add scripts/warehouse/load_raw_to_duckdb.py
git add scripts/warehouse/bronze_validation_check.py
git commit -m "Build DuckDB Bronze ingestion and validation layer"
```

Do not normally commit:

```text
data/warehouse/atlas.duckdb
```

The database is a generated binary artefact and should be recreated by running the loader.

Recommended `.gitignore` coverage:

```gitignore
data/warehouse/*
*.duckdb
*.db
```

Optionally commit:

```text
data/warehouse/bronze_validation_results.csv
```

if a point-in-time validation evidence file is desired.

---

## 11. Downstream dbt Implications

The Bronze layer provides the dbt source boundary.

dbt Silver models should:

- cast fields into correct business types;
- apply source-specific cleaning;
- validate business keys;
- classify defects;
- model conformed dimensions and facts;
- implement accounting and FP&A logic;
- perform source-to-source reconciliations.

dbt Silver should not need to rediscover raw file lineage because Bronze already provides:

- physical table lineage through `bronze.<domain>__<file_name>`;
- row-level lineage through `_atlas_source_file`;
- load-run lineage through `_atlas_ingested_at`;
- row-drift detection through `_atlas_row_hash`.

---

## 12. Phase 4.1 Lock Status

Phase 4.1 is locked.

```text
Phase 4.1 — DuckDB Bronze Raw Ingestion Layer ✅ Locked
```

Locked assets:

```text
scripts/warehouse/load_raw_to_duckdb.py
scripts/warehouse/bronze_validation_check.py
```

Generated but normally uncommitted artefact:

```text
data/warehouse/atlas.duckdb
```

Optional generated evidence:

```text
data/warehouse/bronze_validation_results.csv
```

The project is now ready for Phase 4.2: dbt source readiness and Bronze source documentation expansion.
