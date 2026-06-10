{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'region']
) }}

with billing_customers as (

    select
        trim(upper(cast(region_id as varchar))) as region_id,
        count(*) as billing_customer_rows
    from {{ ref('stg_billing__billing_customers') }}
    where region_id is not null
    group by trim(upper(cast(region_id as varchar)))

),

hris_employees as (

    select
        trim(upper(cast(region_id as varchar))) as region_id,
        count(*) as hris_employee_rows
    from {{ ref('stg_hris__hr_employees') }}
    where region_id is not null
    group by trim(upper(cast(region_id as varchar)))

),

hris_headcount as (

    select
        trim(upper(cast(region_id as varchar))) as region_id,
        count(*) as hris_headcount_snapshot_rows
    from {{ ref('stg_hris__hr_headcount_snapshot') }}
    where region_id is not null
    group by trim(upper(cast(region_id as varchar)))

),

region_universe as (

    select region_id from billing_customers
    union
    select region_id from hris_employees
    union
    select region_id from hris_headcount

),

region_attributes as (

    select
        u.region_id,

        coalesce(b.billing_customer_rows, 0) as billing_customer_rows,
        coalesce(e.hris_employee_rows, 0) as hris_employee_rows,
        coalesce(h.hris_headcount_snapshot_rows, 0) as hris_headcount_snapshot_rows

    from region_universe as u
    left join billing_customers as b
        on u.region_id = b.region_id
    left join hris_employees as e
        on u.region_id = e.region_id
    left join hris_headcount as h
        on u.region_id = h.region_id

),

region_rows as (

    select
        md5(trim(upper(region_id))) as region_hk,

        region_id,

        case
            when region_id = 'UK' then 'United Kingdom'
            when region_id = 'US' then 'United States'
            when region_id = 'DE' then 'Germany'
            when region_id = 'SG' then 'Singapore'
            else 'Unknown Region'
        end as region_name,

        case
            when region_id = 'UK' then 'Europe'
            when region_id = 'DE' then 'Europe'
            when region_id = 'US' then 'North America'
            when region_id = 'SG' then 'Asia-Pacific'
            else 'Unknown'
        end as region_group,

        case
            when region_id = 'UK' then 'EMEA'
            when region_id = 'DE' then 'EMEA'
            when region_id = 'US' then 'Americas'
            when region_id = 'SG' then 'APAC'
            else 'Unknown'
        end as operating_region,

        case
            when region_id = 'UK' then 'GBP'
            when region_id = 'US' then 'USD'
            when region_id = 'DE' then 'EUR'
            when region_id = 'SG' then 'SGD'
            else 'UNKNOWN'
        end as default_currency_code,

        case
            when region_id in ('UK', 'DE') then true
            else false
        end as is_emea_region,

        case
            when region_id = 'US' then true
            else false
        end as is_americas_region,

        case
            when region_id = 'SG' then true
            else false
        end as is_apac_region,

        case
            when region_id = 'UK' then true
            else false
        end as is_home_market,

        case when billing_customer_rows > 0 then true else false end as exists_in_billing_customers,
        case when hris_employee_rows > 0 then true else false end as exists_in_hris_employees,
        case when hris_headcount_snapshot_rows > 0 then true else false end as exists_in_hris_headcount_snapshot,

        billing_customer_rows,
        hris_employee_rows,
        hris_headcount_snapshot_rows,

        case
            when region_id = 'UK' then 10
            when region_id = 'US' then 20
            when region_id = 'DE' then 30
            when region_id = 'SG' then 40
            else 99
        end as region_sort,

        false as is_unassigned

    from region_attributes

),

unassigned_row as (

    select
        md5('UNASSIGNED') as region_hk,

        'UNASSIGNED' as region_id,
        'Unassigned Region' as region_name,
        'Unassigned' as region_group,
        'Unassigned' as operating_region,
        'UNASSIGNED' as default_currency_code,

        false as is_emea_region,
        false as is_americas_region,
        false as is_apac_region,
        false as is_home_market,

        false as exists_in_billing_customers,
        false as exists_in_hris_employees,
        false as exists_in_hris_headcount_snapshot,

        0 as billing_customer_rows,
        0 as hris_employee_rows,
        0 as hris_headcount_snapshot_rows,

        -1 as region_sort,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from region_rows
