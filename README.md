# Finance Intelligence Platform

## Project Atlas

A portfolio-grade finance analytics platform built to simulate a modern multinational SaaS organization.

The project demonstrates end-to-end analytics engineering, finance data modelling, forecasting, governance, and AI-assisted reporting using realistic synthetic enterprise data.

## Business Scenario

Nexus Technologies is a multinational SaaS company operating across:

* United Kingdom
* United States
* Germany
* Singapore

Following rapid growth and the acquisition of DataPulse Analytics, finance leadership faces challenges around:

* Data fragmentation
* SaaS KPI consistency
* Multi-currency reporting
* Forecast accuracy
* Governance and auditability

Project Atlas provides a governed analytics platform designed to address these challenges.

---

## Technology Stack

### Data Generation

* Python

### Data Storage

* DuckDB
* Parquet

### Transformation & Governance

* dbt

### Analytics & Reporting

* Power BI

### Forecasting & AI

* Python Analytics Suite
* OpenAI API

---

## Architecture

```text
Raw Source Systems
        ↓
DuckDB Bronze
        ↓
dbt Silver
        ↓
dbt Gold
        ↓
Analytical Marts
        ↓
Forecasting Layer
        ↓
AI Commentary Layer
        ↓
Power BI Executive Reporting
```

---

## Project Objectives

* Simulate realistic SaaS source systems
* Build a modern finance warehouse
* Calculate SaaS performance metrics
* Implement governance and audit controls
* Generate financial forecasts
* Produce AI-assisted commentary
* Deliver executive reporting

---

## Current Status

### Design Phase

* [x] Project Charter
* [x] Architecture Design
* [x] Data Model Design
* [x] Synthetic Data Design
* [x] Source System Generation Design

### Engineering Phase

* [ ] Source System Generation
* [ ] DuckDB Warehouse
* [ ] dbt Transformations
* [ ] Forecasting Layer
* [ ] AI Commentary Layer
* [ ] Power BI Reporting

---

## Repository Structure

```text
docs/
data/
scripts/
tests/
logs/
```

---

## Author

Lewis Andrews

Finance | Data | Analytics Engineering | Audit Technology