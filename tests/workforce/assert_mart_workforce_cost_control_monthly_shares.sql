with monthly_shares as (

    select
        reporting_month_date_hk,
        sum(payroll_cost_share_of_month) as payroll_share_sum,
        sum(active_headcount_share_of_month) as active_headcount_share_sum,
        sum(payroll_cost_gbp) as payroll_cost_gbp,
        sum(active_headcount_count) as active_headcount_count
    from {{ ref('mart_workforce_cost_control') }}
    group by 1

)

select *
from monthly_shares
where
    (payroll_cost_gbp > 0 and round(payroll_share_sum, 6) <> 1)
    or (active_headcount_count > 0 and round(active_headcount_share_sum, 6) <> 1)
