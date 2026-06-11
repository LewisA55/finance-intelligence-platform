{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'procurement', 'ap', 'vendor_invoices', 'p2p']
) }}

with source as (

    select
        vendor_invoice_pk,
        vendor_invoice_id,
        vendor_id,
        vendor_name,
        invoice_number,
        invoice_date,
        due_date,
        posting_date,
        posting_period,
        currency,
        subtotal_local,
        tax_rate,
        tax_amount_local,
        total_local,
        subtotal_gbp,
        tax_amount_gbp,
        total_gbp,
        payment_status,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_procurement__vendor_invoices') }}

),

renamed as (

    select
        md5(trim(upper(cast(vendor_invoice_id as varchar)))) as vendor_invoice_hk,

        vendor_invoice_pk,
        vendor_invoice_id,

        md5(trim(upper(cast(vendor_id as varchar)))) as vendor_hk,
        vendor_id,
        vendor_name,
        invoice_number,

        case
            when invoice_date is not null then md5(strftime(invoice_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as invoice_date_hk,

        case
            when due_date is not null then md5(strftime(due_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as due_date_hk,

        case
            when posting_date is not null then md5(strftime(posting_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as posting_date_hk,

        case
            when posting_period is not null then md5(strftime(posting_period, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as posting_period_date_hk,

        invoice_date,
        due_date,
        posting_date,
        posting_period,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(subtotal_local, 0) as subtotal_local,
        coalesce(tax_rate, 0) as tax_rate,
        coalesce(tax_amount_local, 0) as tax_amount_local,
        coalesce(total_local, 0) as total_local,

        coalesce(subtotal_gbp, 0) as subtotal_gbp,
        coalesce(tax_amount_gbp, 0) as tax_amount_gbp,
        coalesce(total_gbp, 0) as total_gbp,

        round(
            coalesce(subtotal_local, 0)
            + coalesce(tax_amount_local, 0)
            - coalesce(total_local, 0),
            2
        ) as invoice_arithmetic_variance_local,

        round(
            coalesce(subtotal_gbp, 0)
            + coalesce(tax_amount_gbp, 0)
            - coalesce(total_gbp, 0),
            2
        ) as invoice_arithmetic_variance_gbp,

        coalesce(nullif(trim(cast(payment_status as varchar)), ''), 'Unknown') as payment_status,

        case when payment_status = 'Paid' then true else false end as is_paid,
        case when payment_status = 'Open' then true else false end as is_open,
        case when payment_status = 'Overdue' then true else false end as is_overdue,

        case when coalesce(total_gbp, 0) < 0 then true else false end as is_negative_invoice_total,
        case when coalesce(total_gbp, 0) = 0 then true else false end as is_zero_invoice_total,

        coalesce(is_defect, false) as is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,

        case when defect_type = 'DUPLICATE_VENDOR_INVOICE' then true else false end as is_duplicate_vendor_invoice,
        case when defect_type = 'AP_CUTOFF_FAILURE' then true else false end as is_ap_cutoff_failure,

        source_system,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from source

)

select *
from renamed
