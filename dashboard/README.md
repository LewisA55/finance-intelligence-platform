# Atlas Dashboard

A static, interactive CFO finance-intelligence dashboard for **Project Atlas / Nexus
Technologies**. It runs entirely in the browser: **DuckDB-WASM** queries Parquet files
served as static assets — no backend, no server. Deployable to GitHub Pages or Vercel.

## Stack

- **Vite + React + TypeScript**
- **DuckDB-WASM** (`@duckdb/duckdb-wasm`) — SQL over Parquet in-browser. The wasm +
  worker bundles are **self-hosted**: Vite emits them into `dist/` via `?url` imports
  and serves them same-origin, so there is no CDN dependency at runtime (offline-capable).
  The browser downloads only the single bundle it selects (eh where supported, else mvp).
- **Recharts** for visuals

## Data

The app ships a small, committed slice of the dbt mart exports in `public/data/`
(~160 KB): the pre-aggregated executive command center mart plus the region and date
dimensions. Because the command center is already aggregated to a governed reporting
scope, the four headline views need only this slice — the multi-MB raw marts are added
per-view later, when drill-down requires them.

To refresh the slice after a new `dbt build` + parquet export:

```bash
npm run refresh-data
```

This copies from `../data/exports/powerbi/parquet/` into `public/data/`. The file list
is kept in sync with `DATA_FILES` in `src/duckdb/client.ts`.

## Develop

Requires **Node.js 20+**.

```bash
npm install
npm run dev      # http://localhost:5173
```

## Build & deploy

```bash
npm run build    # outputs to dist/
npm run preview  # serve the production build locally
```

`vite.config.ts` uses a relative `base` (`./`) so the build works unchanged on a
GitHub Pages project subpath (e.g. `/finance-intelligence-platform/`) or on Vercel (`/`).

## Structure

```
src/
  duckdb/client.ts     DuckDB-WASM init + parquet registration (singleton)   [= lib/duckdb.ts]
  duckdb/queries.ts    typed, scope-safe SQL query functions                 [= lib/atlasQueries.ts]
  hooks/useQuery.ts    run a query loader -> { data, loading, error }
  lib/format.ts        GBP / percent / count formatting                      [= lib/formatters.ts]
  nav.ts               page registry (id, label, status)
  components/          Sidebar · TopBar · Layout · KpiCard · StatusPill ·
                       ChartCard · DataQualityBanner · PlaceholderPage
  pages/               CfoCommandCenter · SaaSPerformance · FinancialPerformance ·
                       WorkingCapital · ControlTower · Validation
  types.ts
```

## Pages

- **CFO Command Center** — _live_. KPI spine (revenue/operating result/margin/ARR/working
  capital) with variance + favourable/adverse status, actual-vs-budget-vs-forecast trend,
  domain health strip, executive narrative, month selector, data-quality banner. Every
  query is hard-filtered to `reporting_scope = 'Company Total'`.
- **SaaS Performance** — _preview_. ARR trend, NRR/GRR, monthly ARR movement.
- **Financial Performance · Working Capital · Control Tower** — _planned shells_ stating
  purpose and the governed marts that will power them.
- **Data & Validation** — _live_. Loaded tables, row counts, distinct reporting scopes,
  latest reporting/actuals month — auditable provenance via DuckDB-WASM.

### Semantic guardrail
`mart_executive_cfo_command_center` mixes `Company Total`, `Region Total` and
`Business Unit Total` rows. These are **never** aggregated together — company KPIs
hard-filter `reporting_scope = 'Company Total'` (see `COMPANY_TOTAL` in `duckdb/queries.ts`).

The executive narrative is generated deterministically from the query results; the visual
contract is stable so it can be wired to a Claude/OpenAI call later.
