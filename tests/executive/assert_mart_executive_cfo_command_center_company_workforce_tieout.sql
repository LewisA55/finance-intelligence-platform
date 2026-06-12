with command_center as (

    select
        reporting_month_date_hk,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(active_fte_count) as active_fte_count
    from {{ ref('mart_executive_cfo_command_center') }}
    where reporting_scope = 'Company Total'
    group by 1

),

source as (

    select
        reporting_month_date_hk,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(active_fte_count) as active_fte_count
    from {{ ref('mart_workforce_cost_control') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1

)

select *
from command_center
inner join source using (reporting_month_date_hk)
where round(command_center.payroll_cost_gbp - source.payroll_cost_gbp, 2) <> 0
   or round(command_center.active_fte_count - source.active_fte_count, 4) <> 0
