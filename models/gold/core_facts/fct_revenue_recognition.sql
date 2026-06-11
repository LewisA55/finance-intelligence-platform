{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'revenue', 'revenue_recognition', 'accrual']
) }}

with source as (

    select
        revenue_recognition_pk,
        recognition_id,
        invoice_id,
        invoice_line_id,
        customer_id,
        subscription_id,
        product_id,

        recognition_month,
        service_period_start_date,
        service_period_end_date,
        recognition_start_date,
        recognition_end_date,

        days_in_service_period,
        days_recognised_in_month,

        currency,
        invoice_line_amount_local,
        invoice_line_amount_gbp,
        recognised_revenue_local,
        recognised_revenue_gbp,
        deferred_revenue_local_after_month,
        deferred_revenue_gbp_after_month,

        revenue_category,
        recognition_method,
        recognition_status,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_revenue__revenue_recognition_schedule') }}

),

invoice_headers as (

    select
        invoice_id,
        billing_invoice_hk,
        invoice_date_hk,
        invoice_date,
        invoice_status,
        is_defect as is_invoice_defect,
        defect_type as invoice_defect_type
    from {{ ref('fct_billing_invoices') }}

),

invoice_lines as (

    select
        invoice_line_id,
        billing_invoice_line_hk,
        invoice_id,
        invoice_date_hk,
        service_period_start_date_hk as invoice_line_service_period_start_date_hk,
        service_period_end_date_hk as invoice_line_service_period_end_date_hk,
        customer_hk as invoice_line_customer_hk,
        region_hk as invoice_line_region_hk,
        line_type,
        revenue_category as invoice_line_revenue_category,
        billing_frequency,
        line_amount_local as invoice_line_fact_amount_local,
        line_amount_gbp as invoice_line_fact_amount_gbp,
        is_defect as is_invoice_line_defect,
        defect_type as invoice_line_defect_type
    from {{ ref('fct_billing_invoice_lines') }}

),

customer_dimension as (

    select
        customer_hk,
        region_hk,
        customer_id
    from {{ ref('dim_customer') }}
    where is_unassigned = false

),

renamed as (

    select
        md5(trim(upper(cast(s.recognition_id as varchar)))) as revenue_recognition_hk,

        s.revenue_recognition_pk,
        s.recognition_id,

        case
            when s.recognition_month is not null
            then md5(strftime(s.recognition_month, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as recognition_month_date_hk,

        case
            when s.service_period_start_date is not null
            then md5(strftime(s.service_period_start_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_start_date_hk,

        case
            when s.service_period_end_date is not null
            then md5(strftime(s.service_period_end_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_end_date_hk,

        case
            when s.recognition_start_date is not null
            then md5(strftime(s.recognition_start_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as recognition_start_date_hk,

        case
            when s.recognition_end_date is not null
            then md5(strftime(s.recognition_end_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as recognition_end_date_hk,

        case
            when s.customer_id is not null and trim(cast(s.customer_id as varchar)) <> ''
            then md5(trim(upper(cast(s.customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        coalesce(c.region_hk, il.invoice_line_region_hk, md5('UNASSIGNED')) as region_hk,

        case
            when s.revenue_category = 'Subscription Revenue' then md5('4100')
            else md5('UNASSIGNED_GL_ACCOUNT')
        end as gl_account_hk,

        case
            when s.revenue_category = 'Subscription Revenue' then '4100'
            else 'UNASSIGNED'
        end as mapped_account_code,

        case
            when s.revenue_category = 'Subscription Revenue' then 'Revenue category fallback'
            else 'Unassigned fallback'
        end as revenue_account_mapping_method,

        nullif(trim(upper(cast(s.customer_id as varchar))), '') as customer_id,
        nullif(trim(cast(s.invoice_id as varchar)), '') as invoice_id,
        nullif(trim(cast(s.invoice_line_id as varchar)), '') as invoice_line_id,
        nullif(trim(cast(s.subscription_id as varchar)), '') as subscription_id,
        nullif(trim(cast(s.product_id as varchar)), '') as product_id,

        ih.billing_invoice_hk,
        il.billing_invoice_line_hk,

        ih.invoice_date_hk,
        ih.invoice_date,
        ih.invoice_status,

        s.recognition_month,
        s.service_period_start_date,
        s.service_period_end_date,
        s.recognition_start_date,
        s.recognition_end_date,

        coalesce(s.days_in_service_period, 0) as days_in_service_period,
        coalesce(s.days_recognised_in_month, 0) as days_recognised_in_month,

        coalesce(nullif(trim(upper(cast(s.currency as varchar))), ''), 'UNKNOWN') as currency_code,
        s.revenue_category,
        s.recognition_method,
        s.recognition_status,

        il.line_type,
        il.billing_frequency,
        il.invoice_line_revenue_category,

        coalesce(s.invoice_line_amount_local, 0) as schedule_invoice_line_amount_local,
        coalesce(s.invoice_line_amount_gbp, 0) as schedule_invoice_line_amount_gbp,

        coalesce(il.invoice_line_fact_amount_local, 0) as invoice_line_fact_amount_local,
        coalesce(il.invoice_line_fact_amount_gbp, 0) as invoice_line_fact_amount_gbp,

        coalesce(s.recognised_revenue_local, 0) as recognised_revenue_local,
        coalesce(s.recognised_revenue_gbp, 0) as recognised_revenue_gbp,

        coalesce(s.deferred_revenue_local_after_month, 0) as deferred_revenue_local_after_month,
        coalesce(s.deferred_revenue_gbp_after_month, 0) as deferred_revenue_gbp_after_month,

        case
            when coalesce(s.days_in_service_period, 0) = 0 then 0
            else round(
                cast(coalesce(s.days_recognised_in_month, 0) as double)
                / cast(s.days_in_service_period as double),
                8
            )
        end as service_period_recognition_ratio,

        case when s.recognition_status = 'Actual' then true else false end as is_actual_recognition,
        case when s.recognition_status = 'Scheduled' then true else false end as is_scheduled_recognition,

        case when s.recognition_method = 'Daily Pro-Rata Straight Line' then true else false end as is_daily_pro_rata_recognition,
        case when s.recognition_method = 'Point in Time' then true else false end as is_point_in_time_recognition,

        case when coalesce(s.recognised_revenue_local, 0) = 0 then true else false end as is_zero_recognised_revenue_local,
        case when coalesce(s.recognised_revenue_gbp, 0) = 0 then true else false end as is_zero_recognised_revenue_gbp,

        case
            when s.recognition_start_date < s.service_period_start_date
              or s.recognition_end_date > s.service_period_end_date
            then true
            else false
        end as is_recognition_window_outside_service_period,

        case when ih.invoice_id is null then true else false end as is_orphan_invoice_recognition,
        case when il.invoice_line_id is null then true else false end as is_orphan_invoice_line_recognition,
        case when c.customer_hk is null then true else false end as is_orphan_customer_recognition,

        coalesce(s.is_defect, false) as is_defect,
        nullif(trim(cast(s.defect_type as varchar)), '') as defect_type,

        coalesce(ih.is_invoice_defect, false) as is_parent_invoice_defect,
        ih.invoice_defect_type,
        coalesce(il.is_invoice_line_defect, false) as is_parent_invoice_line_defect,
        il.invoice_line_defect_type,

        s.source_system,
        s.created_date,
        s.updated_date,

        s._atlas_row_hash,
        s._atlas_ingested_at,
        s._atlas_source_file

    from source as s

    left join invoice_headers as ih
        on trim(upper(cast(s.invoice_id as varchar))) = trim(upper(cast(ih.invoice_id as varchar)))

    left join invoice_lines as il
        on trim(upper(cast(s.invoice_line_id as varchar))) = trim(upper(cast(il.invoice_line_id as varchar)))

    left join customer_dimension as c
        on trim(upper(cast(s.customer_id as varchar))) = trim(upper(cast(c.customer_id as varchar)))

)

select *
from renamed
