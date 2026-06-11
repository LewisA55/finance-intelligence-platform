{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'procurement', 'ap', 'vendor_payments', 'cash_out', 'p2p']
) }}

with source_payments as (

    select
        vendor_payment_pk,
        vendor_payment_id,
        vendor_invoice_id,
        vendor_id,
        vendor_name,
        invoice_number,
        payment_date,
        currency,
        payment_amount_local,
        payment_amount_gbp,
        cash_account_code,
        payment_method,
        payment_reference,
        payment_status,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_procurement__vendor_payments') }}

),

invoice_headers as (

    select
        vendor_invoice_hk,
        vendor_invoice_id,
        vendor_hk,
        invoice_number as header_invoice_number,
        invoice_date_hk,
        due_date_hk,
        posting_date_hk,
        posting_period_date_hk,
        invoice_date,
        due_date,
        posting_date,
        posting_period,
        currency_code as invoice_currency_code,
        total_local as invoice_total_local,
        total_gbp as invoice_total_gbp,
        payment_status as invoice_payment_status,
        is_paid as is_invoice_paid,
        is_open as is_invoice_open,
        is_overdue as is_invoice_overdue,
        is_defect as is_header_defect,
        defect_type as header_defect_type,
        is_duplicate_vendor_invoice as is_header_duplicate_vendor_invoice,
        is_ap_cutoff_failure as is_header_ap_cutoff_failure

    from {{ ref('fct_vendor_invoices') }}

),

payment_totals_by_invoice as (

    select
        vendor_invoice_id,
        round(sum(coalesce(payment_amount_local, 0)), 2) as invoice_paid_amount_local,
        round(sum(coalesce(payment_amount_gbp, 0)), 2) as invoice_paid_amount_gbp,
        count(*) as invoice_payment_count
    from source_payments
    group by vendor_invoice_id

),

joined as (

    select
        p.*,

        h.vendor_invoice_hk,
        h.vendor_hk,
        h.header_invoice_number,
        h.invoice_date_hk,
        h.due_date_hk,
        h.posting_date_hk,
        h.posting_period_date_hk,
        h.invoice_date,
        h.due_date,
        h.posting_date,
        h.posting_period,
        h.invoice_currency_code,
        h.invoice_total_local,
        h.invoice_total_gbp,
        h.invoice_payment_status,
        h.is_invoice_paid,
        h.is_invoice_open,
        h.is_invoice_overdue,
        h.is_header_defect,
        h.header_defect_type,
        h.is_header_duplicate_vendor_invoice,
        h.is_header_ap_cutoff_failure,

        t.invoice_paid_amount_local,
        t.invoice_paid_amount_gbp,
        t.invoice_payment_count,

        round(
            coalesce(t.invoice_paid_amount_local, 0)
            - coalesce(h.invoice_total_local, 0),
            2
        ) as invoice_paid_vs_total_variance_local,

        round(
            coalesce(t.invoice_paid_amount_gbp, 0)
            - coalesce(h.invoice_total_gbp, 0),
            2
        ) as invoice_paid_vs_total_variance_gbp

    from source_payments as p

    left join invoice_headers as h
        on p.vendor_invoice_id = h.vendor_invoice_id

    left join payment_totals_by_invoice as t
        on p.vendor_invoice_id = t.vendor_invoice_id

),

renamed as (

    select
        md5(trim(upper(cast(vendor_payment_id as varchar)))) as vendor_payment_hk,

        vendor_payment_pk,
        vendor_payment_id,

        vendor_invoice_hk,
        vendor_invoice_id,

        coalesce(vendor_hk, md5(trim(upper(cast(vendor_id as varchar))))) as vendor_hk,
        vendor_id,
        vendor_name,

        case
            when payment_date is not null
            then md5(strftime(payment_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as payment_date_hk,

        invoice_date_hk,
        due_date_hk,
        posting_date_hk,
        posting_period_date_hk,

        case
            when cash_account_code is not null and trim(cash_account_code) <> ''
            then md5(trim(upper(cast(cash_account_code as varchar))))
            else md5('UNASSIGNED_GL_ACCOUNT')
        end as cash_account_hk,

        md5('2300') as ap_control_account_hk,

        invoice_number,
        header_invoice_number,
        payment_date,
        invoice_date,
        due_date,
        posting_date,
        posting_period,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,
        invoice_currency_code,

        coalesce(payment_amount_local, 0) as payment_amount_local,
        coalesce(payment_amount_gbp, 0) as payment_amount_gbp,

        invoice_total_local,
        invoice_total_gbp,
        invoice_paid_amount_local,
        invoice_paid_amount_gbp,
        invoice_payment_count,

        invoice_paid_vs_total_variance_local,
        invoice_paid_vs_total_variance_gbp,

        coalesce(nullif(trim(cast(cash_account_code as varchar)), ''), 'UNASSIGNED') as cash_account_code,
        coalesce(nullif(trim(cast(payment_method as varchar)), ''), 'Unknown') as payment_method,
        payment_reference,
        coalesce(nullif(trim(cast(payment_status as varchar)), ''), 'Unknown') as payment_status,

        invoice_payment_status,
        coalesce(is_invoice_paid, false) as is_invoice_paid,
        coalesce(is_invoice_open, false) as is_invoice_open,
        coalesce(is_invoice_overdue, false) as is_invoice_overdue,

        case when coalesce(payment_amount_gbp, 0) > 0 then true else false end as is_positive_payment,
        case when coalesce(payment_amount_gbp, 0) < 0 then true else false end as is_negative_payment,
        case when coalesce(payment_amount_gbp, 0) = 0 then true else false end as is_zero_payment,

        case
            when coalesce(invoice_paid_amount_gbp, 0) > coalesce(invoice_total_gbp, 0) + 0.01
            then true
            else false
        end as is_payment_exceeds_invoice_total,

        case
            when vendor_invoice_hk is null then true else false
        end as is_orphan_vendor_invoice_payment,

        coalesce(is_defect, false) as is_payment_defect,
        nullif(trim(cast(defect_type as varchar)), '') as payment_defect_type,

        coalesce(is_header_defect, false) as is_header_defect,
        header_defect_type,
        coalesce(is_header_duplicate_vendor_invoice, false) as is_header_duplicate_vendor_invoice,
        coalesce(is_header_ap_cutoff_failure, false) as is_header_ap_cutoff_failure,

        case
            when coalesce(is_defect, false)
              or coalesce(is_header_defect, false)
              or vendor_invoice_hk is null
              or coalesce(payment_amount_gbp, 0) <= 0
              or coalesce(invoice_paid_amount_gbp, 0) > coalesce(invoice_total_gbp, 0) + 0.01
            then true
            else false
        end as has_ap_payment_control_exception,

        source_system,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from joined

)

select *
from renamed
