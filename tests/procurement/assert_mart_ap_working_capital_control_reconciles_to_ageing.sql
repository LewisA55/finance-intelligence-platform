/* Test: open AP exposure reconciles to fct_ap_ageing_snapshot. */
with source_totals as (
    select vendor_hk, date_trunc('month', snapshot_date)::date as reporting_month_date,
           count(*) as open_invoice_count,
           round(sum(open_amount_gbp), 2) as open_amount_gbp,
           round(sum(case when is_overdue then open_amount_gbp else 0 end), 2) as overdue_amount_gbp
    from {{ ref('fct_ap_ageing_snapshot') }}
    group by vendor_hk, date_trunc('month', snapshot_date)::date
)
select m.vendor_hk, m.reporting_month_date, m.open_invoice_count, s.open_invoice_count as source_open_invoice_count,
       m.open_payable_liability_gbp, s.open_amount_gbp,
       m.overdue_payable_liability_gbp, s.overdue_amount_gbp
from {{ ref('mart_ap_working_capital_control') }} as m
inner join source_totals as s
    on m.vendor_hk = s.vendor_hk and m.reporting_month_date = s.reporting_month_date
where m.open_invoice_count <> s.open_invoice_count
   or abs(m.open_payable_liability_gbp - s.open_amount_gbp) > 0.01
   or abs(m.overdue_payable_liability_gbp - s.overdue_amount_gbp) > 0.01
