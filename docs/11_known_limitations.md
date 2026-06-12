# Known Limitations And Design Decisions

This document records current limitations, accepted caveats, and future-work boundaries for Project Atlas.

## Synthetic Data

All data is fictional and generated for portfolio/demo use. It should not be interpreted as real company data or production financial reporting.

## Planned But Not Yet Implemented

| Area | Status |
| --- | --- |
| Power BI CFO reporting pack | Planned |
| Atlas Intelligence Portal | Planned |
| AI commentary layer | Planned |
| Portfolio screenshots | Planned after reporting layer exists |

## Accepted Finance And Modelling Caveats

### P2P Gross Expense And Tax Simplification

The procurement and AP design includes a simplified treatment of gross expense and tax in the source generation layer. This is acceptable for the current portfolio milestone because downstream AP controls and marts focus on working-capital exposure, payment behaviour, and governance telemetry.

### Trial Balance Future Periods

Some generated planning and recognition structures include future-oriented periods. Downstream models distinguish actual, forecast, scheduled, and planning semantics rather than treating all future-dated rows as current actuals.

### Accepted Control Findings

The project intentionally includes control findings such as AR control pressure and deferred revenue subledger-to-ledger differences. These are not hidden. They are surfaced through tests, control fields, and Gold marts.

### Workforce Future-Dated Run Rates

Workforce planning data includes future hiring and run-rate assumptions. These support planning and forecast analysis but should not be interpreted as actual headcount.

### Ghost Headcount And Status Mismatches

Workforce defects are intentionally generated to test downstream controls. They remain visible through workforce facts and marts.

### Local-Currency Aggregation

Some marts expose both GBP and local-currency measures. GBP is the governed consolidated reporting currency. Local-currency totals should be interpreted carefully when more than one currency is present at the mart grain.

## dbt Project Hygiene Notes

- Bronze is a source boundary in DuckDB, not a dbt SQL model layer.
- Silver models are source-aligned views.
- Gold models are reporting-ready tables.
- Generated data, local warehouse files, dbt target artifacts, and logs are ignored by Git.

## Future Enhancements

- Add Power BI screenshots and report walkthrough.
- Add dbt lineage artifact screenshots or generated docs output.
- Add a portal layer for governed commentary.
- Continue tightening documentation around mart grains and accepted exceptions.
