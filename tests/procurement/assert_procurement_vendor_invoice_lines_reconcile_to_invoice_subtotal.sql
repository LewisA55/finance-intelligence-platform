/*
Purpose:
    Reconcile clean vendor invoice line totals to clean vendor invoice header subtotals.

Clean-scope rule:
    An invoice is clean only when the header is not defect-flagged and none of
    its lines are defect-flagged.

Expected result:
    Zero rows.
*/
with line_defect_flags as (
    select
        vendor_invoice_id,
        max(case when is_defect then 1 else 0 end) as has_defective_line
    from {{ ref('stg_procurement__vendor_invoice_lines') }}
    group by vendor_invoice_id
),
clean_invoice_headers as (
    select
        invoices.vendor_invoice_id,
        invoices.invoice_number,
        invoices.vendor_id,
        round(invoices.subtotal_local, 2) as subtotal_local,
        round(invoices.subtotal_gbp, 2) as subtotal_gbp
    from {{ ref('stg_procurement__vendor_invoices') }} as invoices
    left join line_defect_flags
        on invoices.vendor_invoice_id = line_defect_flags.vendor_invoice_id
    where invoices.is_defect = false
      and coalesce(line_defect_flags.has_defective_line, 0) = 0
),
line_totals as (
    select
        vendor_invoice_id,
        round(sum(line_amount_local), 2) as line_amount_local,
        round(sum(line_amount_gbp), 2) as line_amount_gbp
    from {{ ref('stg_procurement__vendor_invoice_lines') }}
    group by vendor_invoice_id
)
select
    clean_invoice_headers.vendor_invoice_id,
    clean_invoice_headers.invoice_number,
    clean_invoice_headers.vendor_id,
    clean_invoice_headers.subtotal_local,
    line_totals.line_amount_local,
    round(clean_invoice_headers.subtotal_local - line_totals.line_amount_local, 2) as local_variance,
    clean_invoice_headers.subtotal_gbp,
    line_totals.line_amount_gbp,
    round(clean_invoice_headers.subtotal_gbp - line_totals.line_amount_gbp, 2) as gbp_variance
from clean_invoice_headers
left join line_totals
    on clean_invoice_headers.vendor_invoice_id = line_totals.vendor_invoice_id
where line_totals.vendor_invoice_id is null
   or abs(clean_invoice_headers.subtotal_local - line_totals.line_amount_local) > 0.01
   or abs(clean_invoice_headers.subtotal_gbp - line_totals.line_amount_gbp) > 0.01
