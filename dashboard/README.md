# Atlas Dashboard

Static CFO intelligence dashboard for the fictional Nexus Technologies portfolio case.

**Live:** https://lewisa55.github.io/finance-intelligence-platform/

The app runs entirely in the browser. React renders the interface while DuckDB-WASM
queries small, governed Parquet slices exported from the dbt Gold layer. There is no
application backend and no runtime CDN dependency.

> All data is synthetic. The dashboard is a portfolio demonstration, not production
> financial reporting or financial advice.

## Pages

- **CFO Command Center**: executive KPIs, P&L summary, plan variance, control status,
  and prioritised drill-through cues.
- **Financial Performance**: actual, budget and forecast analysis by department and account.
- **SaaS Performance**: ARR movement, product/segment mix, retention and regional exposure.
- **Revenue Recognition**: billing, earned revenue, deferred revenue and accounting controls.
- **Working Capital**: AR collections, customer exposure, AP ageing and vendor exposure.
- **Control Tower**: exception-period observations and locked dbt validation evidence.
- **Data & Validation**: loaded views, reporting scopes and snapshot provenance.

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
```

`npm run check` validates the committed data contract and performs a production build.

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
