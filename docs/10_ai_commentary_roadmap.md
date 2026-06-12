# AI Commentary Roadmap

The Atlas Intelligence Portal and AI commentary layer are planned future work.

The current completed scope is the governed warehouse and executive mart layer. AI commentary should be built only on top of validated Gold outputs.

## Intended Purpose

The AI layer should:

- summarise validated CFO metrics;
- explain variance drivers from structured mart outputs;
- highlight control exceptions already identified by dbt models/tests;
- support executive review without inventing new calculations.

## Guardrails

The AI commentary layer must not:

- calculate finance metrics independently;
- infer unsupported causes;
- override dbt-defined business logic;
- blend incompatible grains;
- present ARR as GAAP revenue;
- treat deferred revenue as recognised revenue.

## Likely Inputs

- `mart_executive_cfo_command_center`
- `mart_financial_performance`
- `mart_saas_arr_movement`
- `mart_saas_retention`
- `mart_revenue_waterfall`
- `mart_deferred_revenue_control`
- `mart_ap_working_capital_control`
- `mart_workforce_cost_control`

## Planned Interface

The likely front end is an Atlas Intelligence Portal, potentially implemented in Streamlit, with curated executive commentary generated from warehouse outputs.
