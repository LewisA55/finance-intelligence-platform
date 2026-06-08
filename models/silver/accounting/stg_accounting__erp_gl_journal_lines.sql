{{ config(
    materialized='view',
    schema='silver',
    tags=['silver', 'staging', 'accounting', 'general_ledger']
) }}

with source as (

    select *
    from {{ source('bronze', 'accounting__erp_gl_journal_lines') }}

),

renamed_and_casted as (

    select
        -- Primary keys / line identifiers
        trim(cast(journal_line_pk as varchar)) as journal_line_pk,
        trim(cast(journal_id as varchar)) as journal_id,
        trim(cast(journal_line_id as varchar)) as journal_line_id,

        -- Accounting dates / periods
        {{ safecast_date('journal_date') }} as journal_date,
        trim(cast(posting_period as varchar)) as posting_period,

        -- Source document lineage
        trim(cast(source_system as varchar)) as source_system,
        trim(cast(source_document_type as varchar)) as source_document_type,
        trim(cast(source_document_id as varchar)) as source_document_id,
        nullif(trim(cast(source_line_id as varchar)), '') as source_line_id,

        -- Optional subledger identifiers
        nullif(trim(cast(customer_id as varchar)), '') as customer_id,
        nullif(trim(cast(subscription_id as varchar)), '') as subscription_id,
        nullif(trim(cast(invoice_id as varchar)), '') as invoice_id,
        nullif(trim(cast(payment_id as varchar)), '') as payment_id,
        nullif(trim(cast(vendor_id as varchar)), '') as vendor_id,
        nullif(trim(cast(vendor_invoice_id as varchar)), '') as vendor_invoice_id,
        nullif(trim(cast(vendor_payment_id as varchar)), '') as vendor_payment_id,
        nullif(trim(cast(allocation_id as varchar)), '') as allocation_id,
        nullif(trim(cast(revenue_schedule_id as varchar)), '') as revenue_schedule_id,

        -- Account attributes
        trim(cast(account_code as varchar)) as account_code,
        trim(cast(account_name as varchar)) as account_name,
        trim(cast(account_class as varchar)) as account_class,
        trim(cast(financial_statement as varchar)) as financial_statement,
        trim(cast(dc_indicator as varchar)) as dc_indicator,

        -- Monetary values
        {{ safecast_decimal('debit_local') }} as debit_local,
        {{ safecast_decimal('credit_local') }} as credit_local,
        {{ safecast_decimal('debit_gbp') }} as debit_gbp,
        {{ safecast_decimal('credit_gbp') }} as credit_gbp,

        -- Currency / description
        upper(trim(cast(currency as varchar))) as currency,
        nullif(trim(cast(description as varchar)), '') as description,

        -- Operational flags
        {{ safecast_boolean('is_system_generated') }} as is_system_generated,
        {{ safecast_boolean('is_reversal') }} as is_reversal,
        {{ safecast_boolean('is_defect_flag') }} as is_defect,

        -- Defect metadata
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        -- Source operational dates
        {{ safecast_date('created_at') }} as created_date,
        {{ safecast_date('updated_at') }} as updated_date,

        -- Atlas Bronze lineage metadata
        _atlas_row_hash,
        cast(_atlas_ingested_at as timestamp) as _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed_and_casted
