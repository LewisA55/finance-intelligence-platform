# Contributing

Project Atlas is primarily a portfolio case study, but focused corrections and
well-scoped improvements are welcome.

## Before Opening A Pull Request

1. Keep generated raw data, local warehouses, dbt targets and logs out of Git.
2. Preserve the Bronze, Silver and Gold ownership boundaries.
3. Keep finance calculations in dbt or governed export queries rather than React.
4. Run the relevant validation:

```bash
dbt parse --no-partial-parse
dbt build
```

For dashboard changes:

```bash
cd dashboard
npm ci
npm run check
```

## Pull Requests

Explain the business or control reason for the change, identify affected model grains,
and include screenshots for visible dashboard changes. Avoid unrelated refactors.
