{{ config(
    materialized = 'table',
    schema = 'gold'
) }}

with dim_date as (

    select
        date_hk,
        date_day
    from {{ ref('dim_date') }}
    where date_day is not null

),

dim_department as (

    select
        department_hk,
        department_id
    from {{ ref('dim_department') }}

),

payroll_base as (

    select
        payroll.department_hk,
        cast(date_trunc('month', payroll_date.date_day) as date) as reporting_month_date,

        count(*) as payroll_line_count,
        sum(payroll.net_amount_gbp) as payroll_cost_gbp,

        sum(case when payroll.cost_component = 'BASE_SALARY' then payroll.net_amount_gbp else 0 end) as base_salary_cost_gbp,
        sum(case when payroll.cost_component = 'EMPLOYER_TAX' then payroll.net_amount_gbp else 0 end) as employer_tax_cost_gbp,
        sum(case when payroll.cost_component = 'BENEFITS' then payroll.net_amount_gbp else 0 end) as benefits_cost_gbp,
        sum(case when payroll.cost_component = 'BONUS_ACCRUAL' then payroll.net_amount_gbp else 0 end) as bonus_accrual_cost_gbp,

        sum(payroll.employee_count) as payroll_employee_count_sum

    from {{ ref('fct_payroll_expense_lines') }} as payroll

    left join dim_date as payroll_date
        on payroll.payroll_expense_period_date_hk = payroll_date.date_hk

    group by 1, 2

),

headcount_base as (

    select
        headcount.department_hk,
        cast(date_trunc('month', snapshot_date.date_day) as date) as reporting_month_date,

        count(*) as snapshot_row_count,
        sum(headcount.active_headcount_count) as active_headcount_count,
        sum(case when headcount.is_inactive_headcount then 1 else 0 end) as inactive_headcount_count,
        sum(headcount.ghost_headcount_count) as ghost_headcount_count,

        sum(headcount.fte_count) as fte_count,
        sum(headcount.active_fte_count) as active_fte_count,

        sum(headcount.monthly_salary_gbp) as monthly_salary_exposure_gbp,
        sum(case when headcount.is_ghost_headcount then headcount.monthly_salary_gbp else 0 end) as ghost_monthly_salary_exposure_gbp,
        sum(case when headcount.is_status_active_mismatch then 1 else 0 end) as status_active_mismatch_count

    from {{ ref('fct_headcount_snapshot') }} as headcount

    left join dim_date as snapshot_date
        on headcount.snapshot_month_date_hk = snapshot_date.date_hk

    group by 1, 2

),

headcount_plan_base as (

    select
        plan.department_hk,
        cast(date_trunc('month', planned_start_period.date_day) as date) as reporting_month_date,

        count(*) as plan_row_count,
        sum(plan.planned_position_count) as planned_position_count,
        sum(case when plan.is_open_budgeted_position then plan.planned_position_count else 0 end) as open_budgeted_position_count,
        sum(case when plan.is_backfill_position then plan.planned_position_count else 0 end) as backfill_position_count,
        sum(case when plan.is_open_position then plan.planned_position_count else 0 end) as open_position_count,

        sum(case when plan.is_open_position then plan.target_salary_mid_gbp else 0 end) as open_position_annual_salary_exposure_gbp,
        sum(case when plan.is_open_position then plan.target_salary_mid_gbp / 12 else 0 end) as open_position_monthly_salary_exposure_gbp,
        sum(case when plan.is_backfill then plan.target_salary_mid_gbp else 0 end) as backfill_annual_salary_exposure_gbp,
        sum(case when plan.is_open_position and not plan.is_backfill then plan.target_salary_mid_gbp else 0 end) as growth_hire_annual_salary_exposure_gbp

    from {{ ref('fct_headcount_plan') }} as plan

    left join dim_date as planned_start_period
        on plan.planned_start_period_date_hk = planned_start_period.date_hk

    where plan.is_open_position

    group by 1, 2

),

spine as (

    select department_hk, reporting_month_date from payroll_base

    union

    select department_hk, reporting_month_date from headcount_base

    union

    select department_hk, reporting_month_date from headcount_plan_base

),

combined as (

    select
        spine.department_hk,
        reporting_month_date.date_hk as reporting_month_date_hk,
        spine.reporting_month_date,
        dim_department.department_id,

        -- Payroll cost block
        coalesce(payroll_base.payroll_line_count, 0) as payroll_line_count,
        coalesce(payroll_base.payroll_cost_gbp, 0) as payroll_cost_gbp,
        coalesce(payroll_base.base_salary_cost_gbp, 0) as base_salary_cost_gbp,
        coalesce(payroll_base.employer_tax_cost_gbp, 0) as employer_tax_cost_gbp,
        coalesce(payroll_base.benefits_cost_gbp, 0) as benefits_cost_gbp,
        coalesce(payroll_base.bonus_accrual_cost_gbp, 0) as bonus_accrual_cost_gbp,
        coalesce(payroll_base.payroll_employee_count_sum, 0) as payroll_employee_count_sum,

        -- Actual headcount block
        coalesce(headcount_base.snapshot_row_count, 0) as snapshot_row_count,
        coalesce(headcount_base.active_headcount_count, 0) as active_headcount_count,
        coalesce(headcount_base.inactive_headcount_count, 0) as inactive_headcount_count,
        coalesce(headcount_base.ghost_headcount_count, 0) as ghost_headcount_count,
        coalesce(headcount_base.fte_count, 0) as fte_count,
        coalesce(headcount_base.active_fte_count, 0) as active_fte_count,
        coalesce(headcount_base.monthly_salary_exposure_gbp, 0) as monthly_salary_exposure_gbp,
        coalesce(headcount_base.ghost_monthly_salary_exposure_gbp, 0) as ghost_monthly_salary_exposure_gbp,
        coalesce(headcount_base.status_active_mismatch_count, 0) as status_active_mismatch_count,

        -- Hiring plan block
        coalesce(headcount_plan_base.plan_row_count, 0) as plan_row_count,
        coalesce(headcount_plan_base.planned_position_count, 0) as planned_position_count,
        coalesce(headcount_plan_base.open_budgeted_position_count, 0) as open_budgeted_position_count,
        coalesce(headcount_plan_base.backfill_position_count, 0) as backfill_position_count,
        coalesce(headcount_plan_base.open_position_count, 0) as open_position_count,
        coalesce(headcount_plan_base.open_position_annual_salary_exposure_gbp, 0) as open_position_annual_salary_exposure_gbp,
        coalesce(headcount_plan_base.open_position_monthly_salary_exposure_gbp, 0) as open_position_monthly_salary_exposure_gbp,
        coalesce(headcount_plan_base.backfill_annual_salary_exposure_gbp, 0) as backfill_annual_salary_exposure_gbp,
        coalesce(headcount_plan_base.growth_hire_annual_salary_exposure_gbp, 0) as growth_hire_annual_salary_exposure_gbp

    from spine

    left join dim_date as reporting_month_date
        on spine.reporting_month_date = reporting_month_date.date_day

    left join dim_department
        on spine.department_hk = dim_department.department_hk

    left join payroll_base
        on spine.department_hk = payroll_base.department_hk
       and spine.reporting_month_date = payroll_base.reporting_month_date

    left join headcount_base
        on spine.department_hk = headcount_base.department_hk
       and spine.reporting_month_date = headcount_base.reporting_month_date

    left join headcount_plan_base
        on spine.department_hk = headcount_plan_base.department_hk
       and spine.reporting_month_date = headcount_plan_base.reporting_month_date

),

final as (

    select
        md5(cast(combined.department_hk as varchar) || '|' || cast(combined.reporting_month_date_hk as varchar)) as workforce_cost_control_hk,

        combined.department_hk,
        combined.reporting_month_date_hk,
        combined.reporting_month_date,
        combined.department_id,

        combined.payroll_line_count,
        combined.payroll_cost_gbp,
        combined.base_salary_cost_gbp,
        combined.employer_tax_cost_gbp,
        combined.benefits_cost_gbp,
        combined.bonus_accrual_cost_gbp,
        combined.payroll_employee_count_sum,

        combined.snapshot_row_count,
        combined.active_headcount_count,
        combined.inactive_headcount_count,
        combined.ghost_headcount_count,
        combined.fte_count,
        combined.active_fte_count,
        combined.monthly_salary_exposure_gbp,
        combined.ghost_monthly_salary_exposure_gbp,
        combined.status_active_mismatch_count,

        combined.plan_row_count,
        combined.planned_position_count,
        combined.open_budgeted_position_count,
        combined.backfill_position_count,
        combined.open_position_count,
        combined.open_position_annual_salary_exposure_gbp,
        combined.open_position_monthly_salary_exposure_gbp,
        combined.backfill_annual_salary_exposure_gbp,
        combined.growth_hire_annual_salary_exposure_gbp,

        -- Cost efficiency metrics
        case
            when combined.active_headcount_count > 0
                then combined.payroll_cost_gbp / combined.active_headcount_count
            else 0
        end as payroll_cost_per_active_head_gbp,

        case
            when combined.active_fte_count > 0
                then combined.payroll_cost_gbp / combined.active_fte_count
            else 0
        end as payroll_cost_per_active_fte_gbp,

        case
            when combined.active_headcount_count > 0
                then combined.base_salary_cost_gbp / combined.active_headcount_count
            else 0
        end as base_salary_cost_per_active_head_gbp,

        case
            when combined.payroll_cost_gbp > 0
                then combined.employer_tax_cost_gbp / combined.payroll_cost_gbp
            else 0
        end as employer_tax_ratio,

        case
            when combined.payroll_cost_gbp > 0
                then combined.benefits_cost_gbp / combined.payroll_cost_gbp
            else 0
        end as benefits_ratio,

        case
            when combined.payroll_cost_gbp > 0
                then combined.bonus_accrual_cost_gbp / combined.payroll_cost_gbp
            else 0
        end as bonus_accrual_ratio,

        case
            when combined.open_position_count > 0
                then combined.open_position_annual_salary_exposure_gbp / combined.open_position_count
            else 0
        end as average_open_position_salary_gbp,

        -- Concentration metrics
        case
            when sum(combined.payroll_cost_gbp) over (partition by combined.reporting_month_date_hk) > 0
                then combined.payroll_cost_gbp
                    / sum(combined.payroll_cost_gbp) over (partition by combined.reporting_month_date_hk)
            else 0
        end as payroll_cost_share_of_month,

        case
            when sum(combined.active_headcount_count) over (partition by combined.reporting_month_date_hk) > 0
                then combined.active_headcount_count
                    / sum(combined.active_headcount_count) over (partition by combined.reporting_month_date_hk)
            else 0
        end as active_headcount_share_of_month,

        -- Control flags
        combined.department_id = 'DEPT_UNKNOWN' as is_unknown_department,
        combined.payroll_cost_gbp > 0 and combined.active_headcount_count = 0 as has_payroll_without_active_headcount,
        combined.ghost_headcount_count > 0 as has_ghost_headcount,
        combined.status_active_mismatch_count > 0 as has_status_active_mismatch,
        combined.open_position_count > 0 as has_open_hiring_pressure,

        (
            combined.department_id = 'DEPT_UNKNOWN'
            or (combined.payroll_cost_gbp > 0 and combined.active_headcount_count = 0)
            or combined.ghost_headcount_count > 0
            or combined.status_active_mismatch_count > 0
        ) as has_workforce_control_issue

    from combined

)

select *
from final
