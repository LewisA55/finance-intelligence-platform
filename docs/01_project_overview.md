# Project Overview

Project Atlas is a governed SaaS finance intelligence platform built for a fictional company, Nexus Technologies.

It is designed as a portfolio project that demonstrates finance analytics engineering across synthetic source generation, local warehouse ingestion, dbt modelling, automated testing, and executive semantic marts.

## Business Context

Nexus Technologies is a multinational SaaS company operating across:

- United Kingdom;
- United States;
- Germany;
- Singapore.

The company has grown quickly, acquired DataPulse Analytics, and now needs a governed finance data platform that can support CFO reporting across actuals, budget, forecast, revenue, billing, collections, vendors, workforce, and SaaS metrics.

## Core Finance Problems

The project is built around realistic enterprise finance challenges:

- fragmented source systems;
- inconsistent ARR, MRR, NRR, and GRR definitions;
- multi-currency actuals and planning data;
- revenue recognition and deferred revenue control;
- AP, O2C, and workforce cost governance;
- budget and rolling forecast comparison;
- executive reporting fan-out risk;
- auditability from source file to final mart.

## Completed Build Scope

| Area | Status |
| --- | --- |
| Synthetic finance source generation | Complete |
| DuckDB Bronze warehouse ingestion | Complete |
| dbt Silver staging and control layer | Complete |
| dbt Gold conformed dimensions and facts | Complete |
| Domain Gold marts | Complete |
| Executive CFO Command Center mart | Complete |
| CFO dashboard (React + DuckDB-WASM) | Live |
| Atlas Intelligence Portal / AI commentary | Planned |

## Final Warehouse Milestone

The locked full dbt warehouse build completed with:

| Metric | Result |
| --- | ---: |
| Table models | 37 |
| View models | 30 |
| Data tests | 2,946 |
| PASS | 3,013 |
| WARN | 0 |
| ERROR | 0 |
| SKIP | 0 |
| Runtime | 323.70 seconds |

## Finance Semantics

Project Atlas keeps core finance concepts separated:

- ARR is a commercial SaaS run-rate measure, not GAAP revenue.
- Revenue recognition models earned revenue over service periods.
- Deferred revenue models balance-sheet liability movement.
- Billing and cash collection are separate from revenue recognition.
- Executive reporting uses controlled scopes to prevent double-counting across incompatible grains.

## Portfolio Positioning

This project is intended to show:

- practical analytics engineering with dbt;
- finance domain modelling;
- control-first data design;
- realistic synthetic data generation;
- clear semantic-layer ownership;
- portfolio-ready governance and validation evidence.
