{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with reporting_months as (

    select
        date_hk as reporting_month_date_hk,
        date_day as reporting_month_date
    from {{ ref('dim_date') }}
    where date_day between date '2026-01-01' and date '2026-12-01'
      and date_day = cast(date_trunc('month', date_day) as date)

),

region_axis as (

    select distinct region_hk
    from {{ ref('mart_saas_retention') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'

),

business_unit_axis as (

    select 'SALES_MARKETING' as business_unit_code, 'Sales & Marketing' as business_unit_name
    union all select 'PRODUCT_ENGINEERING', 'Product & Engineering'
    union all select 'CUSTOMER_SUCCESS', 'Customer Success'
    union all select 'G_AND_A', 'G&A / Corporate Functions'
    union all select 'UNKNOWN', 'Unknown / Suspense'

),

scaffold as (

    select
        reporting_months.reporting_month_date_hk,
        reporting_months.reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        'Company Total' as business_unit_name
    from reporting_months

    union all

    select
        reporting_months.reporting_month_date_hk,
        reporting_months.reporting_month_date,
        'Region Total' as reporting_scope,
        region_axis.region_hk,
        'REGION_TOTAL' as business_unit_code,
        'Region Total' as business_unit_name
    from reporting_months
    cross join region_axis

    union all

    select
        reporting_months.reporting_month_date_hk,
        reporting_months.reporting_month_date,
        'Business Unit Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        business_unit_axis.business_unit_code,
        business_unit_axis.business_unit_name
    from reporting_months
    cross join business_unit_axis

),

financial_base as (

    select
        performance_date_hk as reporting_month_date_hk,
        posting_period as reporting_month_date,
        case
            when lower(coalesce(department_id, '')) like '%sales%'
              or lower(coalesce(department_id, '')) like '%marketing%'
              or lower(coalesce(department_id, '')) like '%gtm%'
                then 'SALES_MARKETING'
            when lower(coalesce(department_id, '')) like '%product%'
              or lower(coalesce(department_id, '')) like '%engineering%'
              or lower(coalesce(department_id, '')) like '%r&d%'
              or lower(coalesce(department_id, '')) like '%research%'
                then 'PRODUCT_ENGINEERING'
            when lower(coalesce(department_id, '')) like '%customer%'
              or lower(coalesce(department_id, '')) like '%success%'
              or lower(coalesce(department_id, '')) like '%support%'
                then 'CUSTOMER_SUCCESS'
            when lower(coalesce(department_id, '')) like '%finance%'
              or lower(coalesce(department_id, '')) like '%people%'
              or lower(coalesce(department_id, '')) like '%hr%'
              or lower(coalesce(department_id, '')) like '%legal%'
              or lower(coalesce(department_id, '')) like '%admin%'
              or lower(coalesce(department_id, '')) like '%g&a%'
              or lower(coalesce(department_id, '')) like '%general%'
                then 'G_AND_A'
            else 'UNKNOWN'
        end as business_unit_code,

        sum(case when lower(account_class) = 'revenue' then actual_amount_gbp else 0 end) as actual_revenue_gbp,
        sum(case when lower(account_class) = 'expense' then actual_amount_gbp else 0 end) as actual_expense_gbp,
        sum(case when lower(account_class) = 'revenue' then budget_amount_gbp else 0 end) as budget_revenue_gbp,
        sum(case when lower(account_class) = 'expense' then budget_amount_gbp else 0 end) as budget_expense_gbp,
        sum(case when lower(account_class) = 'revenue' then forecast_amount_gbp else 0 end) as forecast_revenue_gbp,
        sum(case when lower(account_class) = 'expense' then forecast_amount_gbp else 0 end) as forecast_expense_gbp,
        sum(case when is_defect then 1 else 0 end) as financial_defect_row_count,
        count(*) as financial_performance_row_count
    from {{ ref('mart_financial_performance') }}
    where posting_period between date '2026-01-01' and date '2026-12-01'
      and forecast_version_code = 'FC_BASE_CASE'
    group by 1, 2, 3

),

financial_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(actual_revenue_gbp) as actual_revenue_gbp,
        sum(actual_expense_gbp) as actual_expense_gbp,
        sum(budget_revenue_gbp) as budget_revenue_gbp,
        sum(budget_expense_gbp) as budget_expense_gbp,
        sum(forecast_revenue_gbp) as forecast_revenue_gbp,
        sum(forecast_expense_gbp) as forecast_expense_gbp,
        sum(financial_defect_row_count) as financial_defect_row_count,
        sum(financial_performance_row_count) as financial_performance_row_count
    from financial_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Business Unit Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        business_unit_code,
        sum(actual_revenue_gbp) as actual_revenue_gbp,
        sum(actual_expense_gbp) as actual_expense_gbp,
        sum(budget_revenue_gbp) as budget_revenue_gbp,
        sum(budget_expense_gbp) as budget_expense_gbp,
        sum(forecast_revenue_gbp) as forecast_revenue_gbp,
        sum(forecast_expense_gbp) as forecast_expense_gbp,
        sum(financial_defect_row_count) as financial_defect_row_count,
        sum(financial_performance_row_count) as financial_performance_row_count
    from financial_base
    group by 1, 2, 3, 4, 5

),

o2c_base as (

    select
        invoice_month_date_hk as reporting_month_date_hk,
        invoice_month as reporting_month_date,
        region_hk,
        sum(invoice_count) as invoice_count,
        sum(billed_amount_gbp) as billed_amount_gbp,
        sum(allocated_amount_gbp) as cash_collected_gbp,
        sum(open_invoice_exposure_gbp) as open_ar_exposure_gbp,
        sum(net_unallocated_invoice_exposure_gbp) as net_unallocated_invoice_exposure_gbp,
        sum(over_applied_allocation_amount_gbp) as over_applied_cash_gbp,
        sum(overdue_invoice_status_count) as overdue_invoice_count,
        sum(disputed_invoice_status_count) as disputed_invoice_count,
        sum(defective_invoice_count) as defective_invoice_count,
        sum(case when has_open_exposure then 1 else 0 end) as customer_months_with_open_exposure,
        sum(case when has_over_applied_cash then 1 else 0 end) as customer_months_with_over_applied_cash
    from {{ ref('mart_o2c_customer_collections') }}
    where invoice_month between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3

),

o2c_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(invoice_count) as invoice_count,
        sum(billed_amount_gbp) as billed_amount_gbp,
        sum(cash_collected_gbp) as cash_collected_gbp,
        sum(open_ar_exposure_gbp) as open_ar_exposure_gbp,
        sum(net_unallocated_invoice_exposure_gbp) as net_unallocated_invoice_exposure_gbp,
        sum(over_applied_cash_gbp) as over_applied_cash_gbp,
        sum(overdue_invoice_count) as overdue_invoice_count,
        sum(disputed_invoice_count) as disputed_invoice_count,
        sum(defective_invoice_count) as defective_invoice_count,
        sum(customer_months_with_open_exposure) as customer_months_with_open_exposure,
        sum(customer_months_with_over_applied_cash) as customer_months_with_over_applied_cash
    from o2c_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Region Total' as reporting_scope,
        region_hk,
        'REGION_TOTAL' as business_unit_code,
        invoice_count,
        billed_amount_gbp,
        cash_collected_gbp,
        open_ar_exposure_gbp,
        net_unallocated_invoice_exposure_gbp,
        over_applied_cash_gbp,
        overdue_invoice_count,
        disputed_invoice_count,
        defective_invoice_count,
        customer_months_with_open_exposure,
        customer_months_with_over_applied_cash
    from o2c_base

),

revenue_base as (

    select
        reporting_month_date_hk,
        cast(reporting_month as date) as reporting_month_date,
        region_hk,
        sum(billed_amount_gbp) as revenue_waterfall_billed_gbp,
        sum(recognised_revenue_actual_gbp) as recognised_revenue_actual_gbp,
        sum(recognised_revenue_scheduled_gbp) as recognised_revenue_scheduled_gbp,
        sum(recognised_revenue_total_gbp) as recognised_revenue_total_gbp,
        sum(unscheduled_billing_leakage_gbp) as unscheduled_billing_leakage_gbp,
        sum(recognition_variance_gbp) as recognition_variance_gbp,
        sum(governance_defect_line_count) as revenue_governance_defect_count,
        sum(case when has_revenue_governance_exception then 1 else 0 end) as revenue_governance_exception_count
    from {{ ref('mart_revenue_waterfall') }}
    where cast(reporting_month as date) between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3

),

revenue_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(revenue_waterfall_billed_gbp) as revenue_waterfall_billed_gbp,
        sum(recognised_revenue_actual_gbp) as recognised_revenue_actual_gbp,
        sum(recognised_revenue_scheduled_gbp) as recognised_revenue_scheduled_gbp,
        sum(recognised_revenue_total_gbp) as recognised_revenue_total_gbp,
        sum(unscheduled_billing_leakage_gbp) as unscheduled_billing_leakage_gbp,
        sum(recognition_variance_gbp) as recognition_variance_gbp,
        sum(revenue_governance_defect_count) as revenue_governance_defect_count,
        sum(revenue_governance_exception_count) as revenue_governance_exception_count
    from revenue_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Region Total' as reporting_scope,
        region_hk,
        'REGION_TOTAL' as business_unit_code,
        revenue_waterfall_billed_gbp,
        recognised_revenue_actual_gbp,
        recognised_revenue_scheduled_gbp,
        recognised_revenue_total_gbp,
        unscheduled_billing_leakage_gbp,
        recognition_variance_gbp,
        revenue_governance_defect_count,
        revenue_governance_exception_count
    from revenue_base

),

deferred_scoped as (

    select
        period_month_date_hk as reporting_month_date_hk,
        period_month as reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(corporate_opening_deferred_revenue_gbp) as opening_deferred_revenue_gbp,
        sum(corporate_new_billings_deferred_gbp) as new_billings_deferred_revenue_gbp,
        sum(corporate_recognised_revenue_gbp) as deferred_recognised_revenue_gbp,
        sum(corporate_closing_deferred_revenue_gbp) as closing_deferred_revenue_gbp,
        sum(corporate_rollforward_exception_count) as deferred_rollforward_exception_count,
        sum(corporate_continuity_exception_count) as deferred_continuity_exception_count,
        sum(case when has_deferred_revenue_control_exception then 1 else 0 end) as deferred_revenue_control_exception_count
    from {{ ref('mart_deferred_revenue_control') }}
    where period_month between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3, 4, 5

),

ap_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(monthly_invoice_total_gbp) as ap_invoice_spend_gbp,
        sum(monthly_payment_amount_gbp) as supplier_cash_paid_gbp,
        sum(open_payable_liability_gbp) as open_ap_liability_gbp,
        sum(overdue_payable_liability_gbp) as overdue_ap_liability_gbp,
        sum(duplicate_exposure_gbp) as duplicate_ap_exposure_gbp,
        sum(ap_cutoff_failure_exposure_gbp) as ap_cutoff_failure_exposure_gbp,
        sum(case when has_open_ap_exposure then 1 else 0 end) as vendor_months_with_open_ap,
        sum(case when has_overdue_ap_exposure then 1 else 0 end) as vendor_months_with_overdue_ap,
        sum(case when has_ap_control_exception then 1 else 0 end) as ap_control_exception_count
    from {{ ref('mart_ap_working_capital_control') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3, 4, 5

),

workforce_base as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        case
            when lower(coalesce(department_id, '')) like '%sales%'
              or lower(coalesce(department_id, '')) like '%marketing%'
              or lower(coalesce(department_id, '')) like '%gtm%'
                then 'SALES_MARKETING'
            when lower(coalesce(department_id, '')) like '%product%'
              or lower(coalesce(department_id, '')) like '%engineering%'
              or lower(coalesce(department_id, '')) like '%r&d%'
              or lower(coalesce(department_id, '')) like '%research%'
                then 'PRODUCT_ENGINEERING'
            when lower(coalesce(department_id, '')) like '%customer%'
              or lower(coalesce(department_id, '')) like '%success%'
              or lower(coalesce(department_id, '')) like '%support%'
                then 'CUSTOMER_SUCCESS'
            when lower(coalesce(department_id, '')) like '%finance%'
              or lower(coalesce(department_id, '')) like '%people%'
              or lower(coalesce(department_id, '')) like '%hr%'
              or lower(coalesce(department_id, '')) like '%legal%'
              or lower(coalesce(department_id, '')) like '%admin%'
              or lower(coalesce(department_id, '')) like '%g&a%'
              or lower(coalesce(department_id, '')) like '%general%'
                then 'G_AND_A'
            else 'UNKNOWN'
        end as business_unit_code,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(base_salary_cost_gbp) as base_salary_cost_gbp,
        sum(employer_tax_cost_gbp) as employer_tax_cost_gbp,
        sum(benefits_cost_gbp) as benefits_cost_gbp,
        sum(bonus_accrual_cost_gbp) as bonus_accrual_cost_gbp,
        sum(active_headcount_count) as active_headcount_count,
        sum(active_fte_count) as active_fte_count,
        sum(open_position_count) as open_position_count,
        sum(open_position_monthly_salary_exposure_gbp) as open_position_monthly_salary_exposure_gbp,
        sum(ghost_headcount_count) as ghost_headcount_count,
        sum(case when has_workforce_control_issue then 1 else 0 end) as workforce_control_issue_count
    from {{ ref('mart_workforce_cost_control') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3

),

workforce_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(base_salary_cost_gbp) as base_salary_cost_gbp,
        sum(employer_tax_cost_gbp) as employer_tax_cost_gbp,
        sum(benefits_cost_gbp) as benefits_cost_gbp,
        sum(bonus_accrual_cost_gbp) as bonus_accrual_cost_gbp,
        sum(active_headcount_count) as active_headcount_count,
        sum(active_fte_count) as active_fte_count,
        sum(open_position_count) as open_position_count,
        sum(open_position_monthly_salary_exposure_gbp) as open_position_monthly_salary_exposure_gbp,
        sum(ghost_headcount_count) as ghost_headcount_count,
        sum(workforce_control_issue_count) as workforce_control_issue_count
    from workforce_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Business Unit Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        business_unit_code,
        payroll_cost_gbp,
        base_salary_cost_gbp,
        employer_tax_cost_gbp,
        benefits_cost_gbp,
        bonus_accrual_cost_gbp,
        active_headcount_count,
        active_fte_count,
        open_position_count,
        open_position_monthly_salary_exposure_gbp,
        ghost_headcount_count,
        workforce_control_issue_count
    from workforce_base

),

saas_base as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        region_hk,
        sum(beginning_arr_gbp) as beginning_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(ending_arr_gbp) as ending_arr_gbp,
        sum(active_arr_gbp) as active_arr_gbp,
        sum(active_mrr_gbp) as active_mrr_gbp,
        sum(subscription_count) as subscription_count,
        sum(active_subscription_count) as active_subscription_count,
        sum(case when has_saas_control_issue then 1 else 0 end) as saas_arr_control_issue_count
    from {{ ref('mart_saas_arr_movement') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3

),

saas_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(beginning_arr_gbp) as beginning_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(expansion_arr_gbp) as expansion_arr_gbp,
        sum(price_increase_arr_gbp) as price_increase_arr_gbp,
        sum(gross_expansion_arr_gbp) as gross_expansion_arr_gbp,
        sum(contraction_arr_gbp) as contraction_arr_gbp,
        sum(churn_arr_gbp) as churn_arr_gbp,
        sum(pause_arr_gbp) as pause_arr_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp,
        sum(ending_arr_gbp) as ending_arr_gbp,
        sum(active_arr_gbp) as active_arr_gbp,
        sum(active_mrr_gbp) as active_mrr_gbp,
        sum(subscription_count) as subscription_count,
        sum(active_subscription_count) as active_subscription_count,
        sum(saas_arr_control_issue_count) as saas_arr_control_issue_count
    from saas_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Region Total' as reporting_scope,
        region_hk,
        'REGION_TOTAL' as business_unit_code,
        beginning_arr_gbp,
        new_business_arr_gbp,
        expansion_arr_gbp,
        price_increase_arr_gbp,
        gross_expansion_arr_gbp,
        contraction_arr_gbp,
        churn_arr_gbp,
        pause_arr_gbp,
        net_arr_delta_gbp,
        ending_arr_gbp,
        active_arr_gbp,
        active_mrr_gbp,
        subscription_count,
        active_subscription_count,
        saas_arr_control_issue_count
    from saas_base

),

retention_base as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        region_hk,
        sum(beginning_arr_gbp) as retention_beginning_arr_gbp,
        sum(gross_retained_arr_gbp) as gross_retained_arr_gbp,
        sum(net_retained_arr_gbp) as net_retained_arr_gbp,
        sum(net_retained_arr_including_renewal_gbp) as net_retained_arr_including_renewal_gbp,
        sum(beginning_active_customer_count) as beginning_active_customer_count,
        sum(ending_active_customer_count) as ending_active_customer_count,
        sum(retained_customer_count) as retained_customer_count,
        sum(churned_customer_count) as churned_customer_count,
        sum(paused_customer_count) as paused_customer_count,
        sum(new_customer_count) as new_customer_count,
        sum(case when has_saas_retention_control_issue then 1 else 0 end) as saas_retention_control_issue_count
    from {{ ref('mart_saas_retention') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1, 2, 3

),

retention_scoped as (

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Company Total' as reporting_scope,
        md5('UNASSIGNED') as region_hk,
        'COMPANY_TOTAL' as business_unit_code,
        sum(retention_beginning_arr_gbp) as retention_beginning_arr_gbp,
        sum(gross_retained_arr_gbp) as gross_retained_arr_gbp,
        sum(net_retained_arr_gbp) as net_retained_arr_gbp,
        sum(net_retained_arr_including_renewal_gbp) as net_retained_arr_including_renewal_gbp,
        sum(beginning_active_customer_count) as beginning_active_customer_count,
        sum(ending_active_customer_count) as ending_active_customer_count,
        sum(retained_customer_count) as retained_customer_count,
        sum(churned_customer_count) as churned_customer_count,
        sum(paused_customer_count) as paused_customer_count,
        sum(new_customer_count) as new_customer_count,
        sum(saas_retention_control_issue_count) as saas_retention_control_issue_count
    from retention_base
    group by 1, 2, 3, 4, 5

    union all

    select
        reporting_month_date_hk,
        reporting_month_date,
        'Region Total' as reporting_scope,
        region_hk,
        'REGION_TOTAL' as business_unit_code,
        retention_beginning_arr_gbp,
        gross_retained_arr_gbp,
        net_retained_arr_gbp,
        net_retained_arr_including_renewal_gbp,
        beginning_active_customer_count,
        ending_active_customer_count,
        retained_customer_count,
        churned_customer_count,
        paused_customer_count,
        new_customer_count,
        saas_retention_control_issue_count
    from retention_base

),

final as (

    select
        md5(
            scaffold.reporting_month_date_hk
            || '|'
            || scaffold.reporting_scope
            || '|'
            || scaffold.region_hk
            || '|'
            || scaffold.business_unit_code
        ) as executive_cfo_command_center_hk,

        scaffold.reporting_month_date_hk,
        scaffold.reporting_month_date,
        scaffold.reporting_scope,
        scaffold.region_hk,
        scaffold.business_unit_code,
        scaffold.business_unit_name,

        coalesce(financial_scoped.actual_revenue_gbp, 0) as actual_revenue_gbp,
        coalesce(financial_scoped.actual_expense_gbp, 0) as actual_expense_gbp,
        coalesce(financial_scoped.actual_revenue_gbp, 0) - coalesce(financial_scoped.actual_expense_gbp, 0) as actual_operating_result_gbp,
        coalesce(financial_scoped.budget_revenue_gbp, 0) as budget_revenue_gbp,
        coalesce(financial_scoped.budget_expense_gbp, 0) as budget_expense_gbp,
        coalesce(financial_scoped.forecast_revenue_gbp, 0) as forecast_revenue_gbp,
        coalesce(financial_scoped.forecast_expense_gbp, 0) as forecast_expense_gbp,
        coalesce(financial_scoped.financial_defect_row_count, 0) as financial_defect_row_count,
        coalesce(financial_scoped.financial_performance_row_count, 0) as financial_performance_row_count,

        coalesce(o2c_scoped.invoice_count, 0) as invoice_count,
        coalesce(o2c_scoped.billed_amount_gbp, 0) as billed_amount_gbp,
        coalesce(o2c_scoped.cash_collected_gbp, 0) as cash_collected_gbp,
        coalesce(o2c_scoped.open_ar_exposure_gbp, 0) as open_ar_exposure_gbp,
        coalesce(o2c_scoped.net_unallocated_invoice_exposure_gbp, 0) as net_unallocated_invoice_exposure_gbp,
        coalesce(o2c_scoped.over_applied_cash_gbp, 0) as over_applied_cash_gbp,
        coalesce(o2c_scoped.overdue_invoice_count, 0) as overdue_invoice_count,
        coalesce(o2c_scoped.disputed_invoice_count, 0) as disputed_invoice_count,
        coalesce(o2c_scoped.defective_invoice_count, 0) as defective_invoice_count,
        coalesce(o2c_scoped.customer_months_with_open_exposure, 0) as customer_months_with_open_exposure,
        coalesce(o2c_scoped.customer_months_with_over_applied_cash, 0) as customer_months_with_over_applied_cash,

        coalesce(revenue_scoped.revenue_waterfall_billed_gbp, 0) as revenue_waterfall_billed_gbp,
        coalesce(revenue_scoped.recognised_revenue_actual_gbp, 0) as recognised_revenue_actual_gbp,
        coalesce(revenue_scoped.recognised_revenue_scheduled_gbp, 0) as recognised_revenue_scheduled_gbp,
        coalesce(revenue_scoped.recognised_revenue_total_gbp, 0) as recognised_revenue_total_gbp,
        coalesce(revenue_scoped.unscheduled_billing_leakage_gbp, 0) as unscheduled_billing_leakage_gbp,
        coalesce(revenue_scoped.recognition_variance_gbp, 0) as recognition_variance_gbp,
        coalesce(revenue_scoped.revenue_governance_defect_count, 0) as revenue_governance_defect_count,
        coalesce(revenue_scoped.revenue_governance_exception_count, 0) as revenue_governance_exception_count,

        coalesce(deferred_scoped.opening_deferred_revenue_gbp, 0) as opening_deferred_revenue_gbp,
        coalesce(deferred_scoped.new_billings_deferred_revenue_gbp, 0) as new_billings_deferred_revenue_gbp,
        coalesce(deferred_scoped.deferred_recognised_revenue_gbp, 0) as deferred_recognised_revenue_gbp,
        coalesce(deferred_scoped.closing_deferred_revenue_gbp, 0) as closing_deferred_revenue_gbp,
        coalesce(deferred_scoped.deferred_rollforward_exception_count, 0) as deferred_rollforward_exception_count,
        coalesce(deferred_scoped.deferred_continuity_exception_count, 0) as deferred_continuity_exception_count,
        coalesce(deferred_scoped.deferred_revenue_control_exception_count, 0) as deferred_revenue_control_exception_count,

        coalesce(ap_scoped.ap_invoice_spend_gbp, 0) as ap_invoice_spend_gbp,
        coalesce(ap_scoped.supplier_cash_paid_gbp, 0) as supplier_cash_paid_gbp,
        coalesce(ap_scoped.open_ap_liability_gbp, 0) as open_ap_liability_gbp,
        coalesce(ap_scoped.overdue_ap_liability_gbp, 0) as overdue_ap_liability_gbp,
        coalesce(ap_scoped.duplicate_ap_exposure_gbp, 0) as duplicate_ap_exposure_gbp,
        coalesce(ap_scoped.ap_cutoff_failure_exposure_gbp, 0) as ap_cutoff_failure_exposure_gbp,
        coalesce(ap_scoped.vendor_months_with_open_ap, 0) as vendor_months_with_open_ap,
        coalesce(ap_scoped.vendor_months_with_overdue_ap, 0) as vendor_months_with_overdue_ap,
        coalesce(ap_scoped.ap_control_exception_count, 0) as ap_control_exception_count,

        coalesce(workforce_scoped.payroll_cost_gbp, 0) as payroll_cost_gbp,
        coalesce(workforce_scoped.base_salary_cost_gbp, 0) as base_salary_cost_gbp,
        coalesce(workforce_scoped.employer_tax_cost_gbp, 0) as employer_tax_cost_gbp,
        coalesce(workforce_scoped.benefits_cost_gbp, 0) as benefits_cost_gbp,
        coalesce(workforce_scoped.bonus_accrual_cost_gbp, 0) as bonus_accrual_cost_gbp,
        coalesce(workforce_scoped.active_headcount_count, 0) as active_headcount_count,
        coalesce(workforce_scoped.active_fte_count, 0) as active_fte_count,
        coalesce(workforce_scoped.open_position_count, 0) as open_position_count,
        coalesce(workforce_scoped.open_position_monthly_salary_exposure_gbp, 0) as open_position_monthly_salary_exposure_gbp,
        coalesce(workforce_scoped.ghost_headcount_count, 0) as ghost_headcount_count,
        coalesce(workforce_scoped.workforce_control_issue_count, 0) as workforce_control_issue_count,

        coalesce(saas_scoped.beginning_arr_gbp, 0) as beginning_arr_gbp,
        coalesce(saas_scoped.new_business_arr_gbp, 0) as new_business_arr_gbp,
        coalesce(saas_scoped.expansion_arr_gbp, 0) as expansion_arr_gbp,
        coalesce(saas_scoped.price_increase_arr_gbp, 0) as price_increase_arr_gbp,
        coalesce(saas_scoped.gross_expansion_arr_gbp, 0) as gross_expansion_arr_gbp,
        coalesce(saas_scoped.contraction_arr_gbp, 0) as contraction_arr_gbp,
        coalesce(saas_scoped.churn_arr_gbp, 0) as churn_arr_gbp,
        coalesce(saas_scoped.pause_arr_gbp, 0) as pause_arr_gbp,
        coalesce(saas_scoped.net_arr_delta_gbp, 0) as net_arr_delta_gbp,
        coalesce(saas_scoped.ending_arr_gbp, 0) as ending_arr_gbp,
        coalesce(saas_scoped.active_arr_gbp, 0) as active_arr_gbp,
        coalesce(saas_scoped.active_mrr_gbp, 0) as active_mrr_gbp,
        coalesce(saas_scoped.subscription_count, 0) as subscription_count,
        coalesce(saas_scoped.active_subscription_count, 0) as active_subscription_count,
        coalesce(saas_scoped.saas_arr_control_issue_count, 0) as saas_arr_control_issue_count,

        coalesce(retention_scoped.retention_beginning_arr_gbp, 0) as retention_beginning_arr_gbp,
        coalesce(retention_scoped.gross_retained_arr_gbp, 0) as gross_retained_arr_gbp,
        coalesce(retention_scoped.net_retained_arr_gbp, 0) as net_retained_arr_gbp,
        coalesce(retention_scoped.net_retained_arr_including_renewal_gbp, 0) as net_retained_arr_including_renewal_gbp,
        coalesce(retention_scoped.beginning_active_customer_count, 0) as beginning_active_customer_count,
        coalesce(retention_scoped.ending_active_customer_count, 0) as ending_active_customer_count,
        coalesce(retention_scoped.retained_customer_count, 0) as retained_customer_count,
        coalesce(retention_scoped.churned_customer_count, 0) as churned_customer_count,
        coalesce(retention_scoped.paused_customer_count, 0) as paused_customer_count,
        coalesce(retention_scoped.new_customer_count, 0) as new_customer_count,
        coalesce(retention_scoped.saas_retention_control_issue_count, 0) as saas_retention_control_issue_count,

        case
            when coalesce(o2c_scoped.billed_amount_gbp, 0) <> 0
                then coalesce(o2c_scoped.cash_collected_gbp, 0) / o2c_scoped.billed_amount_gbp
            else null
        end as cash_collection_rate,

        case
            when coalesce(workforce_scoped.payroll_cost_gbp, 0) <> 0
                then coalesce(o2c_scoped.cash_collected_gbp, 0) / workforce_scoped.payroll_cost_gbp
            else null
        end as cash_collection_to_payroll_ratio,

        case
            when coalesce(workforce_scoped.active_fte_count, 0) <> 0
                then coalesce(saas_scoped.active_arr_gbp, 0) / workforce_scoped.active_fte_count
            else null
        end as active_arr_per_active_fte_gbp,

        case
            when coalesce(workforce_scoped.active_fte_count, 0) <> 0
                then coalesce(revenue_scoped.recognised_revenue_actual_gbp, 0) / workforce_scoped.active_fte_count
            else null
        end as recognised_revenue_per_active_fte_gbp,

        case
            when coalesce(saas_scoped.active_arr_gbp, 0) <> 0
                then coalesce(revenue_scoped.recognised_revenue_actual_gbp, 0) / saas_scoped.active_arr_gbp
            else null
        end as recognised_revenue_to_active_arr_ratio,

        case
            when coalesce(saas_scoped.active_arr_gbp, 0) <> 0
                then coalesce(deferred_scoped.closing_deferred_revenue_gbp, 0) / saas_scoped.active_arr_gbp
            else null
        end as deferred_revenue_to_active_arr_ratio,

        coalesce(o2c_scoped.open_ar_exposure_gbp, 0) - coalesce(ap_scoped.open_ap_liability_gbp, 0) as net_ar_less_ap_exposure_gbp,

        coalesce(o2c_scoped.open_ar_exposure_gbp, 0)
        + coalesce(ap_scoped.overdue_ap_liability_gbp, 0)
        + coalesce(workforce_scoped.payroll_cost_gbp, 0)
        - coalesce(o2c_scoped.cash_collected_gbp, 0) as operational_cash_pressure_gbp,

        case
            when coalesce(retention_beginning_arr_gbp, 0) > 0
                then least(
                    greatest(
                        gross_retained_arr_gbp / retention_beginning_arr_gbp,
                        0
                    ),
                    1
                )
            else null
        end as gross_revenue_retention_rate,

        case
            when coalesce(retention_scoped.retention_beginning_arr_gbp, 0) > 0
                then retention_scoped.net_retained_arr_gbp / retention_scoped.retention_beginning_arr_gbp
            else null
        end as net_revenue_retention_rate,

        case
            when coalesce(retention_scoped.beginning_active_customer_count, 0) > 0
                then cast(retention_scoped.retained_customer_count as double) / retention_scoped.beginning_active_customer_count
            else null
        end as logo_retention_rate,

        case
            when coalesce(retention_scoped.beginning_active_customer_count, 0) > 0
                then cast(retention_scoped.churned_customer_count as double) / retention_scoped.beginning_active_customer_count
            else null
        end as logo_churn_rate,

        financial_scoped.reporting_month_date_hk is not null as has_financial_performance_metrics,
        o2c_scoped.reporting_month_date_hk is not null as has_o2c_metrics,
        revenue_scoped.reporting_month_date_hk is not null as has_revenue_waterfall_metrics,
        deferred_scoped.reporting_month_date_hk is not null as has_deferred_revenue_metrics,
        ap_scoped.reporting_month_date_hk is not null as has_ap_metrics,
        workforce_scoped.reporting_month_date_hk is not null as has_workforce_metrics,
        saas_scoped.reporting_month_date_hk is not null as has_saas_arr_metrics,
        retention_scoped.reporting_month_date_hk is not null as has_saas_retention_metrics,

        coalesce(financial_scoped.financial_defect_row_count, 0) > 0 as has_financial_performance_control_issue,
        coalesce(o2c_scoped.defective_invoice_count, 0) > 0
            or coalesce(o2c_scoped.customer_months_with_over_applied_cash, 0) > 0 as has_o2c_control_issue,
        coalesce(revenue_scoped.revenue_governance_exception_count, 0) > 0 as has_revenue_control_issue,
        coalesce(deferred_scoped.deferred_revenue_control_exception_count, 0) > 0 as has_deferred_revenue_control_issue,
        coalesce(ap_scoped.ap_control_exception_count, 0) > 0 as has_ap_control_issue,
        coalesce(workforce_scoped.workforce_control_issue_count, 0) > 0 as has_workforce_control_issue,
        coalesce(saas_scoped.saas_arr_control_issue_count, 0) > 0
            or coalesce(retention_scoped.saas_retention_control_issue_count, 0) > 0 as has_saas_control_issue,

        (
            coalesce(financial_scoped.financial_defect_row_count, 0) > 0
            or coalesce(o2c_scoped.defective_invoice_count, 0) > 0
            or coalesce(o2c_scoped.customer_months_with_over_applied_cash, 0) > 0
            or coalesce(revenue_scoped.revenue_governance_exception_count, 0) > 0
            or coalesce(deferred_scoped.deferred_revenue_control_exception_count, 0) > 0
            or coalesce(ap_scoped.ap_control_exception_count, 0) > 0
            or coalesce(workforce_scoped.workforce_control_issue_count, 0) > 0
            or coalesce(saas_scoped.saas_arr_control_issue_count, 0) > 0
            or coalesce(retention_scoped.saas_retention_control_issue_count, 0) > 0
        ) as has_any_executive_control_issue,

        current_timestamp as _atlas_modelled_at

    from scaffold
    left join financial_scoped
        on scaffold.reporting_month_date_hk = financial_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = financial_scoped.reporting_scope
       and scaffold.region_hk = financial_scoped.region_hk
       and scaffold.business_unit_code = financial_scoped.business_unit_code
    left join o2c_scoped
        on scaffold.reporting_month_date_hk = o2c_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = o2c_scoped.reporting_scope
       and scaffold.region_hk = o2c_scoped.region_hk
       and scaffold.business_unit_code = o2c_scoped.business_unit_code
    left join revenue_scoped
        on scaffold.reporting_month_date_hk = revenue_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = revenue_scoped.reporting_scope
       and scaffold.region_hk = revenue_scoped.region_hk
       and scaffold.business_unit_code = revenue_scoped.business_unit_code
    left join deferred_scoped
        on scaffold.reporting_month_date_hk = deferred_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = deferred_scoped.reporting_scope
       and scaffold.region_hk = deferred_scoped.region_hk
       and scaffold.business_unit_code = deferred_scoped.business_unit_code
    left join ap_scoped
        on scaffold.reporting_month_date_hk = ap_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = ap_scoped.reporting_scope
       and scaffold.region_hk = ap_scoped.region_hk
       and scaffold.business_unit_code = ap_scoped.business_unit_code
    left join workforce_scoped
        on scaffold.reporting_month_date_hk = workforce_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = workforce_scoped.reporting_scope
       and scaffold.region_hk = workforce_scoped.region_hk
       and scaffold.business_unit_code = workforce_scoped.business_unit_code
    left join saas_scoped
        on scaffold.reporting_month_date_hk = saas_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = saas_scoped.reporting_scope
       and scaffold.region_hk = saas_scoped.region_hk
       and scaffold.business_unit_code = saas_scoped.business_unit_code
    left join retention_scoped
        on scaffold.reporting_month_date_hk = retention_scoped.reporting_month_date_hk
       and scaffold.reporting_scope = retention_scoped.reporting_scope
       and scaffold.region_hk = retention_scoped.region_hk
       and scaffold.business_unit_code = retention_scoped.business_unit_code

)

select *
from final
