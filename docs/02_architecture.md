# Current Architecture

Project Atlas follows a local-first modern finance warehouse architecture.

```text
Python synthetic source generation
        |
        v
Raw CSV files under data/raw
        |
        v
DuckDB Bronze warehouse
        |
        v
dbt Silver staging and controls
        |
        v
dbt Gold semantic layer
        |
        v
Domain marts and executive marts
        |
        v
React + DuckDB-WASM dashboard (live) / Atlas Intelligence Portal (planned)
```

## Layer Responsibilities

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Source generation | Python | Create realistic synthetic source extracts and intentional data defects. |
| Raw files | CSV | Store generated source-system extracts locally. |
| Bronze | DuckDB | Preserve source payloads and append ingestion metadata. |
| Silver | dbt views | Cast, clean, standardise, and expose source-aligned staging models. |
| Gold | dbt tables | Build conformed dimensions, atomic facts, domain marts, and executive marts. |
| Reporting | React + DuckDB-WASM (live) | Consume governed Gold marts in-browser without redefining business logic. |
| Intelligence | Streamlit / AI, planned | Summarise validated outputs without calculating finance metrics independently. |

## Current dbt Structure

```text
models/
  bronze/
    sources.yml
  silver/
    accounting/
    billing/
    hris/
    planning/
    procurement/
    revenue/
    workforce/
  gold/
    core_dimensions/
    core_facts/
    marts/
      procurement/
      revenue/
      saas/
      workforce/
    executive_marts/
```

## Materialisation Strategy

| Layer | Materialisation | Rationale |
| --- | --- | --- |
| Bronze | DuckDB tables outside dbt model SQL | Preserve raw-loaded source boundary. |
| Silver | Views | Keep source-aligned cleaning transparent and lightweight. |
| Gold dimensions/facts/marts | Tables | Provide stable reporting-ready semantic assets. |

## Source-to-Mart Flow

```text
Raw source CSV
  -> Bronze source table
  -> Silver stg_<source>__<entity>
  -> Gold dim_ / fct_
  -> Gold mart_
  -> Executive CFO Command Center
```

## Reporting Scope Design

The final executive mart does not force all metrics into one universal dimensional grain. Instead, it uses controlled reporting scopes:

- Company Total;
- Region Total;
- Business Unit Total.

This protects executive reporting from fan-out and double-counting when combining customer, region, department, finance, SaaS, AP, and workforce metrics.

## Local Artifacts

Generated data and warehouse files are intentionally not tracked by Git:

- `data/raw/`
- `data/processed/`
- `data/warehouse/`
- `data/exports/`
- dbt `target/`
- dbt `logs/`

The repository tracks code, dbt models, tests, documentation, and placeholder `.gitkeep` files only.
