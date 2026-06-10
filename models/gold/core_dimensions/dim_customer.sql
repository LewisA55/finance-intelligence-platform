{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'customer']
) }}

with customer_master as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,

        customer_pk,
        nullif(trim(cast(legacy_id as varchar)), '') as legacy_id,
        nullif(trim(cast(customer_name as varchar)), '') as customer_name,
        nullif(trim(cast(customer_segment as varchar)), '') as customer_segment,
        coalesce(nullif(trim(cast(industry as varchar)), ''), 'Unknown') as industry,
        trim(upper(cast(region_id as varchar))) as region_id,
        trim(upper(cast(currency_code as varchar))) as currency_code,
        cohort_year,
        is_acquired_customer,
        nullif(trim(cast(acquisition_source as varchar)), '') as acquisition_source,
        created_date,
        nullif(trim(cast(customer_status as varchar)), '') as customer_status,
        is_active,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_billing__billing_customers') }}
    where customer_id is not null
      and trim(customer_id) <> ''

),

subscriptions as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,
        count(*) as billing_subscription_rows
    from {{ ref('stg_billing__billing_subscriptions') }}
    where customer_id is not null
      and trim(customer_id) <> ''
    group by trim(upper(cast(customer_id as varchar)))

),

invoices as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,
        count(*) as billing_invoice_rows
    from {{ ref('stg_billing__billing_invoices') }}
    where customer_id is not null
      and trim(customer_id) <> ''
    group by trim(upper(cast(customer_id as varchar)))

),

payments as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,
        count(*) as billing_payment_rows
    from {{ ref('stg_billing__billing_payments') }}
    where customer_id is not null
      and trim(customer_id) <> ''
    group by trim(upper(cast(customer_id as varchar)))

),

ar_ageing as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,
        count(*) as ar_ageing_rows
    from {{ ref('stg_billing__ar_ageing_snapshot') }}
    where customer_id is not null
      and trim(customer_id) <> ''
    group by trim(upper(cast(customer_id as varchar)))

),

revenue_recognition as (

    select
        trim(upper(cast(customer_id as varchar))) as customer_id,
        count(*) as revenue_recognition_rows
    from {{ ref('stg_revenue__revenue_recognition_schedule') }}
    where customer_id is not null
      and trim(customer_id) <> ''
    group by trim(upper(cast(customer_id as varchar)))

),

customer_rows as (

    select
        md5(trim(upper(m.customer_id))) as customer_hk,

        m.customer_pk,
        m.customer_id,
        m.legacy_id,
        m.customer_name,
        m.customer_segment,
        m.industry,
        m.region_id,
        md5(trim(upper(m.region_id))) as region_hk,
        m.currency_code,
        m.cohort_year,
        m.is_acquired_customer,
        m.acquisition_source,
        m.created_date,
        m.customer_status,
        m.is_active,

        'Standalone' as customer_level,
        cast(null as varchar) as parent_customer_id,
        cast(null as varchar) as parent_customer_name,
        m.customer_id as ultimate_parent_customer_id,
        m.customer_name as ultimate_parent_customer_name,

        case
            when upper(m.customer_id) like '%UNKNOWN%'
              or upper(coalesce(m.customer_name, '')) like '%UNKNOWN%'
            then true
            else false
        end as is_unknown_customer,

        case when coalesce(s.billing_subscription_rows, 0) > 0 then true else false end as exists_in_billing_subscriptions,
        case when coalesce(i.billing_invoice_rows, 0) > 0 then true else false end as exists_in_billing_invoices,
        case when coalesce(p.billing_payment_rows, 0) > 0 then true else false end as exists_in_billing_payments,
        case when coalesce(a.ar_ageing_rows, 0) > 0 then true else false end as exists_in_ar_ageing,
        case when coalesce(r.revenue_recognition_rows, 0) > 0 then true else false end as exists_in_revenue_recognition,

        coalesce(s.billing_subscription_rows, 0) as billing_subscription_rows,
        coalesce(i.billing_invoice_rows, 0) as billing_invoice_rows,
        coalesce(p.billing_payment_rows, 0) as billing_payment_rows,
        coalesce(a.ar_ageing_rows, 0) as ar_ageing_rows,
        coalesce(r.revenue_recognition_rows, 0) as revenue_recognition_rows,

        case
            when m.customer_segment = 'Enterprise' then 10
            when m.customer_segment = 'Mid-Market' then 20
            when m.customer_segment = 'SMB' then 30
            else 99
        end as customer_segment_sort,

        case
            when m.customer_status = 'Active' then 10
            when m.customer_status = 'Paused' then 20
            when m.customer_status = 'Churned' then 30
            else 99
        end as customer_status_sort,

        m._atlas_row_hash,
        m._atlas_ingested_at,
        m._atlas_source_file,

        false as is_unassigned

    from customer_master as m
    left join subscriptions as s
        on m.customer_id = s.customer_id
    left join invoices as i
        on m.customer_id = i.customer_id
    left join payments as p
        on m.customer_id = p.customer_id
    left join ar_ageing as a
        on m.customer_id = a.customer_id
    left join revenue_recognition as r
        on m.customer_id = r.customer_id

),

unassigned_row as (

    select
        md5('UNASSIGNED') as customer_hk,

        'UNASSIGNED_CUSTOMER' as customer_pk,
        'UNASSIGNED' as customer_id,
        cast(null as varchar) as legacy_id,
        'Unassigned Customer' as customer_name,
        'Unassigned' as customer_segment,
        'Unassigned' as industry,
        'UNASSIGNED' as region_id,
        md5('UNASSIGNED') as region_hk,
        'UNASSIGNED' as currency_code,
        cast(null as integer) as cohort_year,
        false as is_acquired_customer,
        'Unassigned' as acquisition_source,
        cast(null as date) as created_date,
        'Unassigned' as customer_status,
        false as is_active,

        'Unassigned' as customer_level,
        cast(null as varchar) as parent_customer_id,
        cast(null as varchar) as parent_customer_name,
        'UNASSIGNED' as ultimate_parent_customer_id,
        'Unassigned Customer' as ultimate_parent_customer_name,

        false as is_unknown_customer,

        false as exists_in_billing_subscriptions,
        false as exists_in_billing_invoices,
        false as exists_in_billing_payments,
        false as exists_in_ar_ageing,
        false as exists_in_revenue_recognition,

        0 as billing_subscription_rows,
        0 as billing_invoice_rows,
        0 as billing_payment_rows,
        0 as ar_ageing_rows,
        0 as revenue_recognition_rows,

        -1 as customer_segment_sort,
        -1 as customer_status_sort,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from customer_rows
