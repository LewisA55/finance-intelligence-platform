with command_center as (

    select
        reporting_month_date_hk,
        sum(cash_collected_gbp) as cash_collected_gbp,
        sum(open_ar_exposure_gbp) as open_ar_exposure_gbp,
        sum(billed_amount_gbp) as billed_amount_gbp
    from {{ ref('mart_executive_cfo_command_center') }}
    where reporting_scope = 'Company Total'
    group by 1

),

source as (

    select
        invoice_month_date_hk as reporting_month_date_hk,
        sum(allocated_amount_gbp) as cash_collected_gbp,
        sum(open_invoice_exposure_gbp) as open_ar_exposure_gbp,
        sum(billed_amount_gbp) as billed_amount_gbp
    from {{ ref('mart_o2c_customer_collections') }}
    where invoice_month between date '2026-01-01' and date '2026-12-01'
    group by 1

)

select *
from command_center
inner join source using (reporting_month_date_hk)
where round(command_center.cash_collected_gbp - source.cash_collected_gbp, 2) <> 0
   or round(command_center.open_ar_exposure_gbp - source.open_ar_exposure_gbp, 2) <> 0
   or round(command_center.billed_amount_gbp - source.billed_amount_gbp, 2) <> 0
