{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'billing', 'o2c']
) }}

with invoices as (

    select
        invoice_pk,
        invoice_id,
        customer_id,

        invoice_date,
        billing_period_start_date,
        billing_period_end_date,
        due_date,

        payment_terms,
        invoice_status,
        currency,

        subtotal_local,
        tax_rate,
        tax_amount_local,
        total_local,

        subtotal_gbp,
        tax_amount_gbp,
        total_gbp,

        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_billing__billing_invoices') }}

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
        md5(trim(upper(cast(i.invoice_id as varchar)))) as billing_invoice_hk,

        i.invoice_pk,
        i.invoice_id,

        case
            when i.invoice_date is not null
            then md5(strftime(i.invoice_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as invoice_date_hk,

        case
            when i.due_date is not null
            then md5(strftime(i.due_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as due_date_hk,

        case
            when i.billing_period_start_date is not null
            then md5(strftime(i.billing_period_start_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as billing_period_start_date_hk,

        case
            when i.billing_period_end_date is not null
            then md5(strftime(i.billing_period_end_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as billing_period_end_date_hk,

        case
            when i.customer_id is not null and trim(cast(i.customer_id as varchar)) <> ''
            then md5(trim(upper(cast(i.customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        coalesce(c.region_hk, md5('UNASSIGNED')) as region_hk,

        nullif(trim(upper(cast(i.customer_id as varchar))), '') as customer_id,

        i.invoice_date,
        i.billing_period_start_date,
        i.billing_period_end_date,
        i.due_date,

        i.payment_terms,
        i.invoice_status,
        coalesce(nullif(trim(upper(cast(i.currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(i.subtotal_local, 0) as subtotal_amount_local,
        coalesce(i.tax_rate, 0) as tax_rate,
        coalesce(i.tax_amount_local, 0) as tax_amount_local,
        coalesce(i.total_local, 0) as total_billed_amount_local,

        coalesce(i.subtotal_gbp, 0) as subtotal_amount_gbp,
        coalesce(i.tax_amount_gbp, 0) as tax_amount_gbp,
        coalesce(i.total_gbp, 0) as total_billed_amount_gbp,

        coalesce(i.total_local, 0) - coalesce(i.subtotal_local, 0) - coalesce(i.tax_amount_local, 0) as local_invoice_rounding_delta,
        coalesce(i.total_gbp, 0) - coalesce(i.subtotal_gbp, 0) - coalesce(i.tax_amount_gbp, 0) as gbp_invoice_rounding_delta,

        case when i.invoice_status = 'Issued' then true else false end as is_issued_invoice,
        case when i.invoice_status = 'Open' then true else false end as is_open_invoice,
        case when i.invoice_status = 'Overdue' then true else false end as is_overdue_invoice,
        case when i.invoice_status = 'Written Off' then true else false end as is_written_off_invoice,

        case when i.due_date < i.invoice_date then true else false end as is_due_before_invoice_date,
        case when i.billing_period_end_date < i.billing_period_start_date then true else false end as is_invalid_billing_period,

        i.source_system,
        coalesce(i.is_defect, false) as is_defect,
        nullif(trim(cast(i.defect_type as varchar)), '') as defect_type,
        i.created_date,
        i.updated_date,

        i._atlas_row_hash,
        i._atlas_ingested_at,
        i._atlas_source_file

    from invoices as i
    left join customer_dimension as c
        on trim(upper(cast(i.customer_id as varchar))) = trim(upper(cast(c.customer_id as varchar)))

)

select *
from renamed
