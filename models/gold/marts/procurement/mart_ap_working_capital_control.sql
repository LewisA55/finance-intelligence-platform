{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'procurement', 'ap', 'working_capital', 'cfo_control', 'p2p']
) }}

with invoice_monthly as (

    select
        vendor_hk,
        vendor_id,
        date_trunc('month', invoice_date)::date as reporting_month_date,
        count(*) as monthly_invoice_count,
        round(sum(total_gbp), 2) as monthly_invoice_total_gbp,
        round(sum(subtotal_gbp), 2) as monthly_invoice_subtotal_gbp,
        round(sum(tax_amount_gbp), 2) as monthly_tax_amount_gbp,
        sum(case when payment_status = 'Paid' then 1 else 0 end) as monthly_paid_invoice_count,
        sum(case when payment_status = 'Open' then 1 else 0 end) as monthly_open_invoice_count,
        sum(case when payment_status = 'Overdue' then 1 else 0 end) as monthly_overdue_invoice_count,
        sum(case when is_duplicate_vendor_invoice then 1 else 0 end) as duplicate_invoice_count,
        round(sum(case when is_duplicate_vendor_invoice then total_gbp else 0 end), 2) as duplicate_exposure_gbp,
        sum(case when is_ap_cutoff_failure then 1 else 0 end) as ap_cutoff_failure_count,
        round(sum(case when is_ap_cutoff_failure then total_gbp else 0 end), 2) as ap_cutoff_failure_exposure_gbp,
        sum(case when is_defect then 1 else 0 end) as defective_invoice_count,
        round(sum(case when is_defect then total_gbp else 0 end), 2) as defective_invoice_exposure_gbp
    from {{ ref('fct_vendor_invoices') }}
    group by vendor_hk, vendor_id, date_trunc('month', invoice_date)::date

),

line_monthly as (

    select
        vendor_hk,
        vendor_id,
        date_trunc('month', invoice_date)::date as reporting_month_date,
        count(*) as monthly_invoice_line_count,
        round(sum(line_amount_gbp), 2) as monthly_expense_line_amount_gbp,
        count(distinct expense_gl_account_hk) as distinct_expense_account_count,
        count(distinct expense_category) as distinct_expense_category_count,
        sum(case when is_line_defect then 1 else 0 end) as defective_invoice_line_count
    from {{ ref('fct_vendor_invoice_lines') }}
    group by vendor_hk, vendor_id, date_trunc('month', invoice_date)::date

),

payment_monthly as (

    select
        vendor_hk,
        vendor_id,
        date_trunc('month', payment_date)::date as reporting_month_date,
        count(*) as monthly_payment_count,
        round(sum(payment_amount_gbp), 2) as monthly_payment_amount_gbp,
        round(avg(date_diff('day', invoice_date, payment_date)), 2) as average_payment_cycle_days,
        min(date_diff('day', invoice_date, payment_date)) as min_payment_cycle_days,
        max(date_diff('day', invoice_date, payment_date)) as max_payment_cycle_days,
        count(distinct payment_method) as distinct_payment_method_count,
        sum(case when is_payment_defect then 1 else 0 end) as defective_payment_count,
        sum(case when has_ap_payment_control_exception then 1 else 0 end) as payment_control_exception_count
    from {{ ref('fct_vendor_payments') }}
    group by vendor_hk, vendor_id, date_trunc('month', payment_date)::date

),

ageing_monthly as (

    select
        vendor_hk,
        vendor_id,
        date_trunc('month', snapshot_date)::date as reporting_month_date,
        max(snapshot_date) as latest_snapshot_date,
        count(*) as open_invoice_count,
        sum(case when is_overdue then 1 else 0 end) as overdue_invoice_count,
        sum(case when is_current then 1 else 0 end) as current_invoice_count,
        round(sum(open_amount_gbp), 2) as open_payable_liability_gbp,
        round(sum(case when is_overdue then open_amount_gbp else 0 end), 2) as overdue_payable_liability_gbp,
        round(sum(case when is_current then open_amount_gbp else 0 end), 2) as current_payable_liability_gbp,
        round(sum(case when ageing_bucket = 'Current' then open_amount_gbp else 0 end), 2) as current_open_amount_gbp,
        round(sum(case when ageing_bucket = '1-30 Days Overdue' then open_amount_gbp else 0 end), 2) as one_to_thirty_overdue_gbp,
        round(sum(case when ageing_bucket = '31-60 Days Overdue' then open_amount_gbp else 0 end), 2) as thirty_one_to_sixty_overdue_gbp,
        round(sum(case when ageing_bucket = '61-90 Days Overdue' then open_amount_gbp else 0 end), 2) as sixty_one_to_ninety_overdue_gbp,
        round(sum(case when ageing_bucket = '91+ Days Overdue' then open_amount_gbp else 0 end), 2) as ninety_plus_overdue_gbp,
        max(days_past_due) as max_days_past_due,
        round(avg(days_past_due), 2) as average_days_past_due,
        sum(case when is_ageing_defect then 1 else 0 end) as defective_ageing_count,
        sum(case when has_ap_ageing_control_exception then 1 else 0 end) as ageing_control_exception_count,
        sum(case when is_header_duplicate_vendor_invoice then 1 else 0 end) as active_duplicate_invoice_count,
        round(sum(case when is_header_duplicate_vendor_invoice then open_amount_gbp else 0 end), 2) as active_duplicate_exposure_gbp,
        sum(case when is_header_ap_cutoff_failure then 1 else 0 end) as active_ap_cutoff_failure_count,
        round(sum(case when is_header_ap_cutoff_failure then open_amount_gbp else 0 end), 2) as active_ap_cutoff_failure_exposure_gbp
    from {{ ref('fct_ap_ageing_snapshot') }}
    group by vendor_hk, vendor_id, date_trunc('month', snapshot_date)::date

),

vendor_months as (
    select vendor_hk, vendor_id, reporting_month_date from invoice_monthly
    union
    select vendor_hk, vendor_id, reporting_month_date from line_monthly
    union
    select vendor_hk, vendor_id, reporting_month_date from payment_monthly
    union
    select vendor_hk, vendor_id, reporting_month_date from ageing_monthly
),

combined as (

    select
        vm.vendor_hk,
        vm.vendor_id,
        vm.reporting_month_date,
        coalesce(i.monthly_invoice_count, 0) as monthly_invoice_count,
        coalesce(i.monthly_invoice_total_gbp, 0) as monthly_invoice_total_gbp,
        coalesce(i.monthly_invoice_subtotal_gbp, 0) as monthly_invoice_subtotal_gbp,
        coalesce(i.monthly_tax_amount_gbp, 0) as monthly_tax_amount_gbp,
        coalesce(i.monthly_paid_invoice_count, 0) as monthly_paid_invoice_count,
        coalesce(i.monthly_open_invoice_count, 0) as monthly_open_invoice_count,
        coalesce(i.monthly_overdue_invoice_count, 0) as monthly_overdue_invoice_count,
        coalesce(l.monthly_invoice_line_count, 0) as monthly_invoice_line_count,
        coalesce(l.monthly_expense_line_amount_gbp, 0) as monthly_expense_line_amount_gbp,
        coalesce(l.distinct_expense_account_count, 0) as distinct_expense_account_count,
        coalesce(l.distinct_expense_category_count, 0) as distinct_expense_category_count,
        coalesce(l.defective_invoice_line_count, 0) as defective_invoice_line_count,
        coalesce(p.monthly_payment_count, 0) as monthly_payment_count,
        coalesce(p.monthly_payment_amount_gbp, 0) as monthly_payment_amount_gbp,
        p.average_payment_cycle_days,
        p.min_payment_cycle_days,
        p.max_payment_cycle_days,
        coalesce(p.distinct_payment_method_count, 0) as distinct_payment_method_count,
        coalesce(p.defective_payment_count, 0) as defective_payment_count,
        coalesce(p.payment_control_exception_count, 0) as payment_control_exception_count,
        a.latest_snapshot_date,
        coalesce(a.open_invoice_count, 0) as open_invoice_count,
        coalesce(a.overdue_invoice_count, 0) as overdue_invoice_count,
        coalesce(a.current_invoice_count, 0) as current_invoice_count,
        coalesce(a.open_payable_liability_gbp, 0) as open_payable_liability_gbp,
        coalesce(a.overdue_payable_liability_gbp, 0) as overdue_payable_liability_gbp,
        coalesce(a.current_payable_liability_gbp, 0) as current_payable_liability_gbp,
        coalesce(a.current_open_amount_gbp, 0) as current_open_amount_gbp,
        coalesce(a.one_to_thirty_overdue_gbp, 0) as one_to_thirty_overdue_gbp,
        coalesce(a.thirty_one_to_sixty_overdue_gbp, 0) as thirty_one_to_sixty_overdue_gbp,
        coalesce(a.sixty_one_to_ninety_overdue_gbp, 0) as sixty_one_to_ninety_overdue_gbp,
        coalesce(a.ninety_plus_overdue_gbp, 0) as ninety_plus_overdue_gbp,
        a.max_days_past_due,
        a.average_days_past_due,
        coalesce(a.defective_ageing_count, 0) as defective_ageing_count,
        coalesce(a.ageing_control_exception_count, 0) as ageing_control_exception_count,
        coalesce(i.duplicate_invoice_count, 0) as duplicate_invoice_count,
        coalesce(i.duplicate_exposure_gbp, 0) as duplicate_exposure_gbp,
        coalesce(i.ap_cutoff_failure_count, 0) as ap_cutoff_failure_count,
        coalesce(i.ap_cutoff_failure_exposure_gbp, 0) as ap_cutoff_failure_exposure_gbp,
        coalesce(i.defective_invoice_count, 0) as defective_invoice_count,
        coalesce(i.defective_invoice_exposure_gbp, 0) as defective_invoice_exposure_gbp,
        coalesce(a.active_duplicate_invoice_count, 0) as active_duplicate_invoice_count,
        coalesce(a.active_duplicate_exposure_gbp, 0) as active_duplicate_exposure_gbp,
        coalesce(a.active_ap_cutoff_failure_count, 0) as active_ap_cutoff_failure_count,
        coalesce(a.active_ap_cutoff_failure_exposure_gbp, 0) as active_ap_cutoff_failure_exposure_gbp
    from vendor_months as vm
    left join invoice_monthly as i on vm.vendor_hk = i.vendor_hk and vm.reporting_month_date = i.reporting_month_date
    left join line_monthly as l on vm.vendor_hk = l.vendor_hk and vm.reporting_month_date = l.reporting_month_date
    left join payment_monthly as p on vm.vendor_hk = p.vendor_hk and vm.reporting_month_date = p.reporting_month_date
    left join ageing_monthly as a on vm.vendor_hk = a.vendor_hk and vm.reporting_month_date = a.reporting_month_date

),

month_totals as (

    select
        reporting_month_date,
        round(sum(monthly_invoice_total_gbp), 2) as total_monthly_invoice_spend_gbp,
        round(sum(monthly_payment_amount_gbp), 2) as total_monthly_payment_amount_gbp,
        round(sum(open_payable_liability_gbp), 2) as total_open_payable_liability_gbp
    from combined
    group by reporting_month_date

),

final as (

    select
        md5(cast(c.vendor_hk as varchar) || '|' || strftime(c.reporting_month_date, '%Y-%m-%d')) as ap_working_capital_control_hk,
        c.vendor_hk,
        c.vendor_id,
        v.vendor_name,
        v.vendor_category,
        v.vendor_status,
        v.currency_code as vendor_default_currency_code,
        md5(strftime(c.reporting_month_date, '%Y-%m-%d')) as reporting_month_date_hk,
        c.reporting_month_date,
        c.latest_snapshot_date,
        c.monthly_invoice_count,
        c.monthly_invoice_total_gbp,
        c.monthly_invoice_subtotal_gbp,
        c.monthly_tax_amount_gbp,
        c.monthly_paid_invoice_count,
        c.monthly_open_invoice_count,
        c.monthly_overdue_invoice_count,
        c.monthly_invoice_line_count,
        c.monthly_expense_line_amount_gbp,
        c.distinct_expense_account_count,
        c.distinct_expense_category_count,
        c.defective_invoice_line_count,
        c.monthly_payment_count,
        c.monthly_payment_amount_gbp,
        c.average_payment_cycle_days,
        c.min_payment_cycle_days,
        c.max_payment_cycle_days,
        c.distinct_payment_method_count,
        c.defective_payment_count,
        c.payment_control_exception_count,
        c.open_invoice_count,
        c.overdue_invoice_count,
        c.current_invoice_count,
        c.open_payable_liability_gbp,
        c.overdue_payable_liability_gbp,
        c.current_payable_liability_gbp,
        c.current_open_amount_gbp,
        c.one_to_thirty_overdue_gbp,
        c.thirty_one_to_sixty_overdue_gbp,
        c.sixty_one_to_ninety_overdue_gbp,
        c.ninety_plus_overdue_gbp,
        c.max_days_past_due,
        c.average_days_past_due,
        case
            when c.monthly_invoice_total_gbp > 0
            then round(c.open_payable_liability_gbp / c.monthly_invoice_total_gbp * date_diff('day', c.reporting_month_date, (c.reporting_month_date + interval 1 month)::date), 2)
            else null
        end as dpo_proxy_days,
        case when t.total_monthly_invoice_spend_gbp > 0 then round(c.monthly_invoice_total_gbp / t.total_monthly_invoice_spend_gbp * 100, 4) else 0 end as vendor_spend_share_percentage,
        case when t.total_monthly_payment_amount_gbp > 0 then round(c.monthly_payment_amount_gbp / t.total_monthly_payment_amount_gbp * 100, 4) else 0 end as vendor_payment_share_percentage,
        case when t.total_open_payable_liability_gbp > 0 then round(c.open_payable_liability_gbp / t.total_open_payable_liability_gbp * 100, 4) else 0 end as vendor_open_ap_share_percentage,
        c.duplicate_invoice_count,
        c.duplicate_exposure_gbp,
        c.ap_cutoff_failure_count,
        c.ap_cutoff_failure_exposure_gbp,
        c.defective_invoice_count,
        c.defective_invoice_exposure_gbp,
        c.defective_ageing_count,
        c.ageing_control_exception_count,
        c.active_duplicate_invoice_count,
        c.active_duplicate_exposure_gbp,
        c.active_ap_cutoff_failure_count,
        c.active_ap_cutoff_failure_exposure_gbp,
        case when c.open_payable_liability_gbp > 0 then true else false end as has_open_ap_exposure,
        case when c.overdue_payable_liability_gbp > 0 then true else false end as has_overdue_ap_exposure,
        case when c.ninety_plus_overdue_gbp > 0 then true else false end as has_critical_overdue_exposure,
        case
            when c.active_duplicate_invoice_count > 0
              or c.active_ap_cutoff_failure_count > 0
              or c.defective_invoice_count > 0
              or c.defective_payment_count > 0
              or c.defective_ageing_count > 0
              or c.payment_control_exception_count > 0
              or c.ageing_control_exception_count > 0
            then true else false
        end as has_ap_control_exception,
        t.total_monthly_invoice_spend_gbp,
        t.total_monthly_payment_amount_gbp,
        t.total_open_payable_liability_gbp
    from combined as c
    left join month_totals as t on c.reporting_month_date = t.reporting_month_date
    left join {{ ref('dim_vendor') }} as v on c.vendor_hk = v.vendor_hk

)

select *
from final
