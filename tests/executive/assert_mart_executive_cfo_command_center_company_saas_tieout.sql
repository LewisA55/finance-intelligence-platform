with command_center as (

    select
        reporting_month_date_hk,
        sum(active_arr_gbp) as active_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp
    from {{ ref('mart_executive_cfo_command_center') }}
    where reporting_scope = 'Company Total'
    group by 1

),

source as (

    select
        reporting_month_date_hk,
        sum(active_arr_gbp) as active_arr_gbp,
        sum(new_business_arr_gbp) as new_business_arr_gbp,
        sum(net_arr_delta_gbp) as net_arr_delta_gbp
    from {{ ref('mart_saas_arr_movement') }}
    where reporting_month_date between date '2026-01-01' and date '2026-12-01'
    group by 1

)

select *
from command_center
inner join source using (reporting_month_date_hk)
where round(command_center.active_arr_gbp - source.active_arr_gbp, 2) <> 0
   or round(command_center.new_business_arr_gbp - source.new_business_arr_gbp, 2) <> 0
   or round(command_center.net_arr_delta_gbp - source.net_arr_delta_gbp, 2) <> 0
