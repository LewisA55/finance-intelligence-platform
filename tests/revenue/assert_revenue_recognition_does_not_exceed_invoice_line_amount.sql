/*
Purpose:
    Ensure total clean recognised revenue by invoice line does not exceed the
    clean Billing invoice line amount.

Grain:
    One failing row per clean invoice_line_id where cumulative recognised
    revenue exceeds the billed line amount beyond tolerance.

Expected result:
    Zero rows.

Notes:
    This validates the upper bound of revenue release. Exact full-life
    reconciliation can be added later after confirming the treatment of future
    scheduled periods and point-in-time rows.
*/

with recognition_by_line as (

    select
        invoice_line_id,
        round(sum(recognised_revenue_local), 2) as recognised_revenue_local,
        round(sum(recognised_revenue_gbp), 2) as recognised_revenue_gbp
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    where is_defect = false
    group by invoice_line_id

),

clean_invoice_lines as (

    select
        invoice_line_id,
        round(line_amount_local, 2) as line_amount_local,
        round(line_amount_gbp, 2) as line_amount_gbp
    from {{ ref('stg_billing__billing_invoice_lines') }}
    where is_defect = false

)

select
    recognition_by_line.invoice_line_id,
    clean_invoice_lines.line_amount_local,
    recognition_by_line.recognised_revenue_local,
    clean_invoice_lines.line_amount_gbp,
    recognition_by_line.recognised_revenue_gbp,
    round(recognition_by_line.recognised_revenue_local - clean_invoice_lines.line_amount_local, 2) as local_overage,
    round(recognition_by_line.recognised_revenue_gbp - clean_invoice_lines.line_amount_gbp, 2) as gbp_overage
from recognition_by_line
inner join clean_invoice_lines
    on recognition_by_line.invoice_line_id = clean_invoice_lines.invoice_line_id
where
    recognition_by_line.recognised_revenue_local > clean_invoice_lines.line_amount_local + 0.01
    or recognition_by_line.recognised_revenue_gbp > clean_invoice_lines.line_amount_gbp + 0.01
