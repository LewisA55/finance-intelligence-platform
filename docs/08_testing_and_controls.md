# Testing And Controls

Project Atlas uses dbt tests and custom singular tests to validate source readiness, finance arithmetic, model grains, relationships, and executive mart guardrails.

## Final Build Result

Latest successful full build:

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

## Test Organisation

Singular tests are organised by finance domain:

```text
tests/
  accounting/
  billing/
  executive/
  planning/
  procurement/
  revenue/
  workforce/
```

## Control Themes

| Theme | Examples |
| --- | --- |
| Grain protection | Business grain uniqueness for facts and marts. |
| Relationship integrity | Invoice lines to invoices, payments to invoices, employees to workforce facts. |
| Arithmetic checks | Invoice totals, payroll components, AP amounts, revenue rollforwards. |
| Finance controls | Trial balance, GL journal balance, deferred revenue continuity. |
| SaaS controls | ARR/MRR identity, waterfall vector mapping, retention formulas. |
| Executive controls | CFO command center scope guardrails and tie-outs. |

## Validation Philosophy

The project intentionally includes source defects and control exceptions. The goal is not to hide them. The goal is to surface them in governed models and tests so executive reporting can distinguish clean metrics from control-risk areas.

## Recommended Validation Commands

```bash
dbt parse --no-partial-parse
dbt build
```

For documentation-only changes:

```bash
git diff
dbt parse --no-partial-parse
```
