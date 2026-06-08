/*
Purpose:
    Reconcile invoice line totals to invoice header subtotals for clean invoices only.

Grain:
    One failing row per clean invoice_id where summed invoice lines do not agree
    to the clean invoice header subtotal within tolerance.

Expected result:
    Zero rows.

Notes:
    An invoice is treated as clean only when:
    - the invoice header is not defect-flagged; and
    - none of its invoice lines are defect-flagged.

    Intentional defect populations such as ZERO_VALUE_INVOICE or defective lines
    should be surfaced later in control / exception marts, not treated as failures
    of clean Billing integrity.
*/

with invoice_line_defect_flags as (

    select
        invoice_id,
        max(case when is_defect then 1 else 0 end) as has_defective_line
    from {{ ref('stg_billing__billing_invoice_lines') }}
    group by invoice_id

),

clean_invoice_headers as (

    select
        invoices.invoice_id,
        round(invoices.subtotal_local, 2) as subtotal_local,
        round(invoices.subtotal_gbp, 2) as subtotal_gbp
    from {{ ref('stg_billing__billing_invoices') }} as invoices
    left join invoice_line_defect_flags as line_flags
        on invoices.invoice_id = line_flags.invoice_id
    where
        invoices.is_defect = false
        and coalesce(line_flags.has_defective_line, 0) = 0

),

line_totals as (

    select
        invoice_id,
        round(sum(line_amount_local), 2) as line_amount_local,
        round(sum(line_amount_gbp), 2) as line_amount_gbp
    from {{ ref('stg_billing__billing_invoice_lines') }}
    group by invoice_id

)

select
    clean_invoice_headers.invoice_id,
    clean_invoice_headers.subtotal_local,
    line_totals.line_amount_local,
    clean_invoice_headers.subtotal_gbp,
    line_totals.line_amount_gbp,
    round(clean_invoice_headers.subtotal_local - line_totals.line_amount_local, 2) as local_variance,
    round(clean_invoice_headers.subtotal_gbp - line_totals.line_amount_gbp, 2) as gbp_variance
from clean_invoice_headers
left join line_totals
    on clean_invoice_headers.invoice_id = line_totals.invoice_id
where
    line_totals.invoice_id is null
    or abs(clean_invoice_headers.subtotal_local - line_totals.line_amount_local) > 0.01
    or abs(clean_invoice_headers.subtotal_gbp - line_totals.line_amount_gbp) > 0.01