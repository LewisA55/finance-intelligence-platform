/* Test: monthly invoice totals reconcile to fct_vendor_invoices. */
with source_totals as (
    select vendor_hk, date_trunc('month', invoice_date)::date as reporting_month_date,
           count(*) as invoice_count, round(sum(total_gbp), 2) as invoice_total_gbp
    from {{ ref('fct_vendor_invoices') }}
    group by vendor_hk, date_trunc('month', invoice_date)::date
)
select m.vendor_hk, m.reporting_month_date, m.monthly_invoice_count, s.invoice_count,
       m.monthly_invoice_total_gbp, s.invoice_total_gbp
from {{ ref('mart_ap_working_capital_control') }} as m
inner join source_totals as s
    on m.vendor_hk = s.vendor_hk and m.reporting_month_date = s.reporting_month_date
where m.monthly_invoice_count <> s.invoice_count
   or abs(m.monthly_invoice_total_gbp - s.invoice_total_gbp) > 0.01
