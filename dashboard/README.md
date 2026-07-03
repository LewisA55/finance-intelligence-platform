# Atlas Dashboard

Static CFO intelligence dashboard for the fictional Nexus Technologies portfolio case.

**Live:** https://lewisa55.github.io/finance-intelligence-platform/

The app runs entirely in the browser. React renders the interface while DuckDB-WASM
queries small, governed Parquet slices exported from the dbt Gold layer. There is no
application backend and no runtime CDN dependency.

> All data is synthetic. The dashboard is a portfolio demonstration, not production
> financial reporting or financial advice.

## Pages

Grouped as Overview / Performance / Operations / Modelling / Governance:

- **CFO Command Center**: executive summary, KPI spine, ranked "Focus next" routing,
  P&L summary, plan variance, domain health tiles including model readiness.
- **SaaS Performance**: the ARR growth-engine bridge, full-history run-rate,
  product/segment mix and trend, retention by segment.
- **Financial Performance**: actual vs budget vs forecast, operating-result variance
  waterfall by department, and the bridge into the model-serving feed (FC_BASE_CASE).
- **Revenue Quality**: recognition history and forward schedule, deferred backlog
  burn-down and rollforward, governance exceptions by readiness treatment.
- **Working Capital**: cash conversion history, AR collections and concentration,
  AP ageing snapshot and trend, working-capital model assumption hooks.
- **Workforce Capacity & Hiring Pressure**: payroll/FTE actuals vs plan, forward
  hiring pressure with salary exposure, department controls by readiness treatment.
- **Forecast & Valuation**: the modelling anchor — governed actuals feed and coverage,
  historical model drivers, opening balance sheet, readiness policy, Excel workspace.
- **Control Tower**: readiness cockpit (blocking / review / accepted / monitor),
  exception trends by domain, and locked dbt validation evidence.
- **Data & Validation**: per-table row counts and coverage windows, manifest status,
  and the model-serving readiness summary.

## Stack

- React 18, TypeScript and Vite
- DuckDB-WASM for in-browser SQL over Parquet
- Recharts for visualisation
- GitHub Actions and GitHub Pages

The DuckDB WASM and worker assets are self-hosted by the Pages build. The app chooses
the exception-handling bundle where supported and falls back to the MVP bundle.

## Dashboard Data Contract

`data-files.json` is the authoritative list of required browser assets. The committed
snapshot currently contains ten files, approximately 760 KB in total:

- governed executive, financial-performance and AP exports;
- curated SaaS product/segment and retention slices;
- curated O2C customer and region/segment slices;
- date, region and department dimensions.

`public/data/manifest.json` records the source commit, byte size and SHA-256 hash of
every file. CI runs `npm run validate-data` before building.

Refresh after a successful warehouse build and Parquet export:

```bash
npm run refresh-data
```

This command copies the standard exports, runs both curated dbt export macros, creates
the manifest and validates the completed snapshot.

## Development

Requires Node.js 22+.

```bash
npm ci
npm run dev
npm run check
npm run screenshots
```

`npm run check` validates the committed data contract and performs a production build.
`npm run screenshots` launches the dashboard locally and refreshes the portfolio images
under `docs/img/` using the installed Chrome browser.

## Deployment

`vite.config.ts` uses `/finance-intelligence-platform/` for production builds and `/`
for local development. The GitHub Actions workflow validates pull requests and deploys
successful `main` builds to GitHub Pages.

Navigation uses hash-backed page IDs, so individual pages can be linked directly without
requiring server-side route rewrites.

## Semantic Guardrails

`mart_executive_cfo_command_center` contains Company Total, Region Total and Business
Unit Total rows. Company KPIs hard-filter `reporting_scope = 'Company Total'`; incompatible
scopes are never summed together.

Business calculations belong in dbt models or curated export queries. React is responsible
for presentation, interaction and clearly labelled derived display values.
