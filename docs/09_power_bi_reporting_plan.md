# Power BI Reporting Plan

> **Superseded.** The realised BI/reporting layer is the live **React + DuckDB-WASM CFO
> dashboard** ([dashboard/README.md](../dashboard/README.md) ·
> [live site](https://lewisa55.github.io/finance-intelligence-platform/)), which consumes
> these same Gold marts in-browser and enforces scope-safe Company-Total reads. This Power BI
> plan is retained as an alternative reference; the page map below still maps cleanly onto the
> delivered dashboard pages.

The warehouse provides the Gold marts needed for the reporting layer. Any reporting tool
(the delivered React/DuckDB-WASM dashboard, or Power BI) should consume these marts directly
without redefining core finance logic.

## Planned Report Pages

| Page | Primary sources |
| --- | --- |
| Executive Overview | `mart_executive_cfo_command_center` |
| Financial Performance | `mart_financial_performance` |
| SaaS ARR Movement | `mart_saas_arr_movement` |
| SaaS Retention | `mart_saas_retention` |
| O2C Collections | `mart_o2c_customer_collections` |
| Revenue Waterfall | `mart_revenue_waterfall` |
| Deferred Revenue Control | `mart_deferred_revenue_control` |
| AP Working Capital | `mart_ap_working_capital_control` |
| Workforce Cost Control | `mart_workforce_cost_control` |

## Design Rules

- Do not calculate core finance metrics in Power BI.
- Do not join incompatible grains without controlled scope.
- Use the CFO command center for cross-domain executive reporting.
- Use domain marts for detailed drill paths.
- Clearly label commercial ARR separately from recognised revenue.

## Screenshot Status

Screenshots are not included yet because the reporting pack is planned future work.
