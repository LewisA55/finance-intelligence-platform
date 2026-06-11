/* Test: monthly payment totals reconcile to fct_vendor_payments. */
with source_totals as (
    select vendor_hk, date_trunc('month', payment_date)::date as reporting_month_date,
           count(*) as payment_count, round(sum(payment_amount_gbp), 2) as payment_amount_gbp
    from {{ ref('fct_vendor_payments') }}
    group by vendor_hk, date_trunc('month', payment_date)::date
)
select m.vendor_hk, m.reporting_month_date, m.monthly_payment_count, s.payment_count,
       m.monthly_payment_amount_gbp, s.payment_amount_gbp
from {{ ref('mart_ap_working_capital_control') }} as m
inner join source_totals as s
    on m.vendor_hk = s.vendor_hk and m.reporting_month_date = s.reporting_month_date
where m.monthly_payment_count <> s.payment_count
   or abs(m.monthly_payment_amount_gbp - s.payment_amount_gbp) > 0.01
