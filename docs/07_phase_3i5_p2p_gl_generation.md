# Phase 3I.5 Code Lock Note

## P2P General Ledger Generation Engine v1 — Gross Expense & Tax Simplification

**Status:** Pending sign-off for Project Atlas code lock
**Component:** Procure-to-Pay General Ledger Posting Logic
**Phase:** 3I.5 — ERP GL Journal Lines including Q2C and P2P

### Context

During Phase 3I.5 reconciliation, the GL generation engine was validated as successfully posting all vendor invoice transactions using the agreed v1 gross posting logic:

```text
Dr Expense / COGS              Gross vendor invoice total
Cr Accounts Payable            Gross vendor invoice total
```

This logic produces balanced journals and preserves clean subledger-to-ledger lineage from vendor invoices, vendor invoice lines, vendor payments, and AP ageing through to the ERP GL journal layer.

### Impact and Reporting Consequence

Because tax is not separated at journal creation, input tax / VAT is absorbed directly into operational expense and cost of goods sold accounts.

For the current locked run, expense accounts include:

```text
£1,835,380.29 of vendor invoice tax
```

As a result, OpEx and COGS reporting are overstated by this amount compared with a traditional net-of-tax accounting model where recoverable tax would be posted separately.

### Design Justification

This is a conscious v1 design simplification, not a processing error.

For Phase 3I.5, the priority was to validate:

* structurally balanced double-entry P2P journals;
* multi-currency cash and AP postings;
* AP subledger-to-GL control account reconciliation;
* defect traceability for AP_CUTOFF_FAILURE and DUPLICATE_VENDOR_INVOICE;
* clean lineage through `vendor_id`, `vendor_invoice_id`, and `vendor_payment_id`.

Splitting tax into a dedicated recoverable tax account would require extending the Chart of Accounts and updating the posting rule matrix. This has been deliberately deferred to avoid late-stage scope expansion within Phase 3I.5.

### Downstream Mitigation

The underlying vendor invoice source data retains invoice-level tax values, and P2P GL rows contain populated vendor invoice lineage fields. Therefore, downstream dbt models or Power BI semantic-layer measures can calculate a net-of-tax view by backing out tax from the vendor invoice source layer where required.

### Deferred Enhancement

A future v2 enhancement should introduce a dedicated recoverable tax / input VAT account and update the P2P posting logic to:

```text
Dr Expense / COGS              Net vendor invoice amount
Dr VAT Recoverable / Input Tax Vendor invoice tax amount
Cr Accounts Payable            Gross vendor invoice total
```

This would allow statutory-style net expense reporting while preserving the same balanced journal and lineage framework established in Phase 3I.5.
