# Phase 3J.1 Documentation Note

## Future Scheduled Recognition Periods in Trial Balance Extract

**Component:** Trial Balance Generation Engine
**Phase:** 3J.1 — Trial Balance Extract
**Status:** Accepted v1 design stance

### Context

The Phase 3J.1 Trial Balance engine evaluates all posting periods present in the upstream ledger source, `erp_gl_journal_lines.csv`.

As a result, the generated `trial_balance.csv` output includes future posting periods through `2027-05`. These periods exist because the upstream revenue recognition engine generates scheduled deferred revenue release journals for future service periods already present in the ledger source.

### Impact and Reporting Consequence

If a downstream consumer aggregates the full `trial_balance.csv` file without applying a date or period-status filter, results will combine realised actual accounting periods with future scheduled recognition periods.

This is especially relevant for:

```text
Revenue
Deferred Revenue
Trial Balance closing balances
Financial Statement extracts
CFO reporting views
```

### Design Justification

This behaviour is an intentional v1 design stance.

The Trial Balance generator is designed to preserve full ledger-to-TB reconciliation. Since future-dated recognition journals are structurally valid, balanced entries within `erp_gl_journal_lines.csv`, excluding them from the raw Trial Balance extract would break continuity between the source ledger and the generated Trial Balance.

For Phase 3J.1, the priority is therefore:

```text
Completeness of ledger extraction
Mathematical continuity
Full period roll-forward integrity
Source-to-Trial-Balance reconciliation
```

rather than prematurely introducing period-state logic into the raw source generator.

### Downstream Mitigation

Actual versus scheduled reporting should be handled in the downstream analytics layer.

For v1, dbt transformation models or Power BI semantic-layer logic can isolate actual reporting periods by filtering to periods less than or equal to the current reporting month.

Example logic:

```text
posting_period <= current_reporting_month
```

This allows downstream models to produce both:

```text
Actual-only Trial Balance views
Full ledger-period Trial Balance views
```

without compromising the raw source extract.

### v2 Roadmap

A future enhancement may introduce explicit status fields such as:

```text
journal_status: POSTED, SCHEDULED, REVERSED
period_status: OPEN, CLOSED, FUTURE
```

This would allow Trial Balance and Financial Statement extracts to be sliced programmatically by accounting state rather than relying only on date filtering.

This enhancement is deferred deliberately to avoid unnecessary complexity in the Phase 3J.1 raw source generation layer.
