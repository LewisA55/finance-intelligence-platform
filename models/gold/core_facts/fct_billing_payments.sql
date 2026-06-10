{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'billing', 'o2c', 'payments']
) }}

with payments as (

    select
        payment_pk,
        payment_id,
        customer_id,
        payment_date,
        payment_method,
        payment_reference,
        currency,
        payment_amount_local,
        payment_amount_gbp,
        bank_account_region,
        payment_status,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_billing__billing_payments') }}

),

renamed as (

    select
        md5(trim(upper(cast(payment_id as varchar)))) as billing_payment_hk,

        payment_pk,
        payment_id,

        case
            when payment_date is not null
            then md5(strftime(payment_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as payment_date_hk,

        case
            when customer_id is not null and trim(cast(customer_id as varchar)) <> ''
            then md5(trim(upper(cast(customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        md5('UNASSIGNED_GL_ACCOUNT') as cash_account_hk,

        nullif(trim(upper(cast(customer_id as varchar))), '') as customer_id,

        payment_date,

        nullif(trim(cast(payment_method as varchar)), '') as payment_method,
        nullif(trim(cast(payment_reference as varchar)), '') as payment_reference,
        nullif(trim(cast(bank_account_region as varchar)), '') as bank_account_region,
        nullif(trim(cast(payment_status as varchar)), '') as payment_status,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(payment_amount_local, 0) as payment_amount_local,
        coalesce(payment_amount_gbp, 0) as payment_amount_gbp,

        case
            when payment_status in ('Fully Applied', 'Partially Applied', 'Unapplied')
            then true
            else false
        end as is_cash_realised,

        case when payment_status = 'Fully Applied' then true else false end as is_fully_applied_payment,
        case when payment_status = 'Partially Applied' then true else false end as is_partially_applied_payment,
        case when payment_status = 'Unapplied' then true else false end as is_unapplied_payment,

        case when payment_amount_local < 0 or payment_amount_gbp < 0 then true else false end as is_negative_payment,
        case when payment_amount_local = 0 or payment_amount_gbp = 0 then true else false end as is_zero_value_payment,

        source_system,
        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from payments

)

select *
from renamed
