/* Test: mart_revenue_waterfall reconciles to fct_billing_invoice_lines. */
with mart_totals as (
    select
        round(sum(billed_amount_gbp), 2) as mart_billed_amount_gbp,
        sum(billed_invoice_line_count) as mart_billed_invoice_line_count
    from {{ ref('mart_revenue_waterfall') }}
),
fact_totals as (
    select
        round(sum(coalesce(line_amount_gbp, 0)), 2) as fact_billed_amount_gbp,
        count(*) as fact_billed_invoice_line_count
    from {{ ref('fct_billing_invoice_lines') }}
)
select
    mart_billed_amount_gbp,
    fact_billed_amount_gbp,
    mart_billed_invoice_line_count,
    fact_billed_invoice_line_count
from mart_totals
cross join fact_totals
where abs(mart_billed_amount_gbp - fact_billed_amount_gbp) > 0.01
   or mart_billed_invoice_line_count <> fact_billed_invoice_line_count
