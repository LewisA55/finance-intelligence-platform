{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'gl_actuals']
) }}

with source as (

    select
        journal_line_pk,
        journal_id,
        journal_line_id,
        journal_date,
        posting_period,

        source_system,
        source_document_type,
        source_document_id,
        source_line_id,

        customer_id,
        subscription_id,
        invoice_id,
        payment_id,

        vendor_id,
        vendor_invoice_id,
        vendor_payment_id,

        allocation_id,
        revenue_schedule_id,

        account_code,
        account_name,
        account_class,
        financial_statement,

        dc_indicator,

        debit_local,
        credit_local,
        debit_gbp,
        credit_gbp,
        currency,

        description,

        is_system_generated,
        is_reversal,
        is_defect,
        defect_type,

        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_accounting__erp_gl_journal_lines') }}

),

renamed as (

    select
        md5(trim(upper(cast(journal_line_id as varchar)))) as gl_actual_hk,

        journal_line_pk,
        journal_id,
        journal_line_id,

        journal_date,
        case
            when journal_date is not null
            then md5(strftime(journal_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as journal_date_hk,

        posting_period,

        case
            when account_code is not null and trim(cast(account_code as varchar)) <> ''
            then md5(trim(upper(cast(account_code as varchar))))
            else md5('UNASSIGNED_GL_ACCOUNT')
        end as gl_account_hk,

        case
            when customer_id is not null and trim(cast(customer_id as varchar)) <> ''
            then md5(trim(upper(cast(customer_id as varchar))))
            else md5('UNASSIGNED')
        end as customer_hk,

        case
            when vendor_id is not null and trim(cast(vendor_id as varchar)) <> ''
            then md5(trim(upper(cast(vendor_id as varchar))))
            else md5('UNASSIGNED')
        end as vendor_hk,

        source_system,
        source_document_type,
        source_document_id,
        source_line_id,

        nullif(trim(upper(cast(customer_id as varchar))), '') as customer_id,
        nullif(trim(cast(subscription_id as varchar)), '') as subscription_id,
        nullif(trim(cast(invoice_id as varchar)), '') as invoice_id,
        nullif(trim(cast(payment_id as varchar)), '') as payment_id,

        nullif(trim(upper(cast(vendor_id as varchar))), '') as vendor_id,
        nullif(trim(cast(vendor_invoice_id as varchar)), '') as vendor_invoice_id,
        nullif(trim(cast(vendor_payment_id as varchar)), '') as vendor_payment_id,

        nullif(trim(cast(allocation_id as varchar)), '') as allocation_id,
        nullif(trim(cast(revenue_schedule_id as varchar)), '') as revenue_schedule_id,

        nullif(trim(cast(account_code as varchar)), '') as account_code,
        account_name,
        account_class,
        financial_statement,

        dc_indicator,

        coalesce(debit_local, 0) as debit_amount_local,
        coalesce(credit_local, 0) as credit_amount_local,
        coalesce(debit_local, 0) - coalesce(credit_local, 0) as net_amount_local,

        coalesce(debit_gbp, 0) as debit_amount_gbp,
        coalesce(credit_gbp, 0) as credit_amount_gbp,
        coalesce(debit_gbp, 0) - coalesce(credit_gbp, 0) as net_amount_gbp,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        description as line_description,

        coalesce(is_system_generated, false) as is_system_generated,
        coalesce(is_reversal, false) as is_reversal,
        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        case when customer_id is not null and trim(cast(customer_id as varchar)) <> '' then true else false end as has_customer,
        case when vendor_id is not null and trim(cast(vendor_id as varchar)) <> '' then true else false end as has_vendor,
        case when invoice_id is not null and trim(cast(invoice_id as varchar)) <> '' then true else false end as has_customer_invoice,
        case when payment_id is not null and trim(cast(payment_id as varchar)) <> '' then true else false end as has_customer_payment,
        case when vendor_invoice_id is not null and trim(cast(vendor_invoice_id as varchar)) <> '' then true else false end as has_vendor_invoice,
        case when vendor_payment_id is not null and trim(cast(vendor_payment_id as varchar)) <> '' then true else false end as has_vendor_payment,
        case when revenue_schedule_id is not null and trim(cast(revenue_schedule_id as varchar)) <> '' then true else false end as has_revenue_schedule,

        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed
