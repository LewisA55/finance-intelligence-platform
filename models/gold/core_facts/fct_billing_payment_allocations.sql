{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'billing', 'o2c', 'payment_allocations']
) }}

with allocations as (

    select
        allocation_pk,
        allocation_id,
        payment_id,
        invoice_id,
        customer_id,
        allocation_date,
        currency,
        allocated_amount_local,
        allocated_amount_gbp,
        allocation_status,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_billing__billing_payment_allocations') }}

),

invoice_headers as (

    select
        invoice_id,
        invoice_date_hk,
        invoice_date,
        due_date,
        total_billed_amount_gbp
    from {{ ref('fct_billing_invoices') }}

),

payments as (

    select
        payment_id,
        payment_date_hk,
        payment_date,
        payment_amount_gbp
    from {{ ref('fct_billing_payments') }}

),

renamed as (

    select
        md5(trim(upper(cast(a.allocation_id as varchar)))) as billing_payment_allocation_hk,

        a.allocation_pk,
        a.allocation_id,

        a.payment_id,
        a.invoice_id,

        case
            when a.allocation_date is not null
            then md5(strftime(a.allocation_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as allocation_date_hk,

        coalesce(i.invoice_date_hk, md5('UNASSIGNED')) as invoice_date_hk,
        coalesce(p.payment_date_hk, md5('UNASSIGNED')) as payment_date_hk,

        case
            when a.customer_id is not null and trim(cast(a.customer_id as varchar)) <> ''
            then md5(trim(upper(cast(a.customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        nullif(trim(upper(cast(a.customer_id as varchar))), '') as customer_id,

        a.allocation_date,
        i.invoice_date,
        i.due_date,
        p.payment_date,

        coalesce(nullif(trim(upper(cast(a.currency as varchar))), ''), 'UNKNOWN') as currency_code,
        nullif(trim(cast(a.allocation_status as varchar)), '') as allocation_status,

        coalesce(a.allocated_amount_local, 0) as allocated_amount_local,
        coalesce(a.allocated_amount_gbp, 0) as allocated_amount_gbp,

        i.total_billed_amount_gbp as parent_invoice_total_billed_amount_gbp,
        p.payment_amount_gbp as parent_payment_amount_gbp,

        case
            when i.invoice_date is not null and a.allocation_date is not null
            then date_diff('day', i.invoice_date, a.allocation_date)
            else null
        end as days_invoice_to_allocation,

        case
            when i.due_date is not null and a.allocation_date is not null
            then date_diff('day', i.due_date, a.allocation_date)
            else null
        end as days_due_to_allocation,

        case
            when p.payment_date is not null and a.allocation_date is not null
            then date_diff('day', p.payment_date, a.allocation_date)
            else null
        end as days_payment_to_allocation,

        case when a.allocation_status = 'Applied' then true else false end as is_applied_allocation,
        case when a.allocation_status = 'Partially Applied' then true else false end as is_partially_applied_allocation,
        case when a.allocation_status = 'Over Applied' then true else false end as is_over_applied_allocation,

        case when i.invoice_id is null then true else false end as is_orphan_invoice_allocation,
        case when p.payment_id is null then true else false end as is_orphan_payment_allocation,

        case when a.allocated_amount_local < 0 or a.allocated_amount_gbp < 0 then true else false end as is_negative_allocation,
        case when a.allocated_amount_local = 0 or a.allocated_amount_gbp = 0 then true else false end as is_zero_value_allocation,

        a.source_system,
        coalesce(a.is_defect, false) as is_defect,
        nullif(trim(cast(a.defect_type as varchar)), '') as defect_type,

        a.created_date,
        a.updated_date,

        a._atlas_row_hash,
        a._atlas_ingested_at,
        a._atlas_source_file

    from allocations as a

    left join invoice_headers as i
        on trim(upper(cast(a.invoice_id as varchar))) = trim(upper(cast(i.invoice_id as varchar)))

    left join payments as p
        on trim(upper(cast(a.payment_id as varchar))) = trim(upper(cast(p.payment_id as varchar)))

)

select *
from renamed
