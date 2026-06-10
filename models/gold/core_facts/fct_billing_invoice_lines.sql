{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'billing', 'o2c', 'invoice_lines']
) }}

with invoice_lines as (

    select
        invoice_line_pk,
        invoice_line_id,
        invoice_id,
        subscription_id,
        customer_id,
        product_id,
        line_type,
        service_period_start_date,
        service_period_end_date,
        billing_frequency,
        quantity,
        unit_price_local,
        line_amount_local,
        unit_price_gbp,
        line_amount_gbp,
        currency,
        revenue_category,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_billing__billing_invoice_lines') }}

),

invoice_headers as (

    select
        invoice_id,
        invoice_date_hk,
        invoice_date,
        invoice_status
    from {{ ref('fct_billing_invoices') }}

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
        md5(trim(upper(cast(l.invoice_line_id as varchar)))) as billing_invoice_line_hk,

        l.invoice_line_pk,
        l.invoice_line_id,
        l.invoice_id,

        coalesce(i.invoice_date_hk, md5('UNASSIGNED')) as invoice_date_hk,

        case
            when l.service_period_start_date is not null
            then md5(strftime(l.service_period_start_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_start_date_hk,

        case
            when l.service_period_end_date is not null
            then md5(strftime(l.service_period_end_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_end_date_hk,

        case
            when l.customer_id is not null and trim(cast(l.customer_id as varchar)) <> ''
            then md5(trim(upper(cast(l.customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        coalesce(c.region_hk, md5('UNASSIGNED')) as region_hk,

        md5('UNASSIGNED_GL_ACCOUNT') as gl_account_hk,

        nullif(trim(upper(cast(l.customer_id as varchar))), '') as customer_id,
        nullif(trim(cast(l.subscription_id as varchar)), '') as subscription_id,
        nullif(trim(cast(l.product_id as varchar)), '') as product_id,

        i.invoice_date,
        l.service_period_start_date,
        l.service_period_end_date,

        l.line_type,
        l.revenue_category,
        l.billing_frequency,
        coalesce(nullif(trim(upper(cast(l.currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(l.quantity, 0) as quantity,
        coalesce(l.unit_price_local, 0) as unit_price_local,
        coalesce(l.line_amount_local, 0) as line_amount_local,
        coalesce(l.unit_price_gbp, 0) as unit_price_gbp,
        coalesce(l.line_amount_gbp, 0) as line_amount_gbp,

        coalesce(l.line_amount_local, 0)
            - (coalesce(l.quantity, 0) * coalesce(l.unit_price_local, 0)) as local_line_rounding_delta,

        coalesce(l.line_amount_gbp, 0)
            - (coalesce(l.quantity, 0) * coalesce(l.unit_price_gbp, 0)) as gbp_line_rounding_delta,

        i.invoice_status,

        case when l.revenue_category = 'Subscription Revenue' then true else false end as is_subscription_revenue,
        case when l.line_type = 'Recurring SaaS' then true else false end as is_recurring_saas_line,
        case when l.line_type = 'Legacy Subscription' then true else false end as is_legacy_subscription_line,
        case when l.service_period_end_date < l.service_period_start_date then true else false end as is_invalid_service_period,
        case when i.invoice_id is null then true else false end as is_orphan_invoice_line,

        coalesce(l.is_defect, false) as is_defect,
        nullif(trim(cast(l.defect_type as varchar)), '') as defect_type,

        l.created_date,
        l.updated_date,

        l._atlas_row_hash,
        l._atlas_ingested_at,
        l._atlas_source_file

    from invoice_lines as l

    left join invoice_headers as i
        on trim(upper(cast(l.invoice_id as varchar))) = trim(upper(cast(i.invoice_id as varchar)))

    left join customer_dimension as c
        on trim(upper(cast(l.customer_id as varchar))) = trim(upper(cast(c.customer_id as varchar)))

)

select *
from renamed
