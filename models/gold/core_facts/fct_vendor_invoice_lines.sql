{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'procurement', 'ap', 'vendor_invoice_lines', 'p2p']
) }}

with source_lines as (

    select
        vendor_invoice_line_pk,
        vendor_invoice_line_id,
        vendor_invoice_id,
        vendor_id,
        vendor_name,
        line_number,
        account_code,
        expense_category,
        service_period_start_date,
        service_period_end_date,
        line_description,
        line_amount_local,
        line_amount_gbp,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_procurement__vendor_invoice_lines') }}

),

invoice_headers as (

    select
        vendor_invoice_hk,
        vendor_invoice_id,
        vendor_hk,
        invoice_number,
        invoice_date_hk,
        due_date_hk,
        posting_date_hk,
        posting_period_date_hk,
        invoice_date,
        due_date,
        posting_date,
        posting_period,
        currency_code,
        payment_status,
        is_paid,
        is_open,
        is_overdue,
        subtotal_local as header_subtotal_local,
        subtotal_gbp as header_subtotal_gbp,
        tax_amount_local as header_tax_amount_local,
        tax_amount_gbp as header_tax_amount_gbp,
        total_local as header_total_local,
        total_gbp as header_total_gbp,
        is_defect as is_header_defect,
        defect_type as header_defect_type,
        is_duplicate_vendor_invoice as is_header_duplicate_vendor_invoice,
        is_ap_cutoff_failure as is_header_ap_cutoff_failure

    from {{ ref('fct_vendor_invoices') }}

),

line_subtotal_totals as (

    select
        vendor_invoice_id,
        round(sum(coalesce(line_amount_local, 0)), 2) as invoice_line_subtotal_local,
        round(sum(coalesce(line_amount_gbp, 0)), 2) as invoice_line_subtotal_gbp,
        count(*) as invoice_line_count
    from source_lines
    group by vendor_invoice_id

),

joined as (

    select
        l.*,

        h.vendor_invoice_hk,
        h.vendor_hk,
        h.invoice_number,
        h.invoice_date_hk,
        h.due_date_hk,
        h.posting_date_hk,
        h.posting_period_date_hk,
        h.invoice_date,
        h.due_date,
        h.posting_date,
        h.posting_period,
        h.currency_code,
        h.payment_status,
        h.is_paid,
        h.is_open,
        h.is_overdue,
        h.header_subtotal_local,
        h.header_subtotal_gbp,
        h.header_tax_amount_local,
        h.header_tax_amount_gbp,
        h.header_total_local,
        h.header_total_gbp,
        h.is_header_defect,
        h.header_defect_type,
        h.is_header_duplicate_vendor_invoice,
        h.is_header_ap_cutoff_failure,

        t.invoice_line_subtotal_local,
        t.invoice_line_subtotal_gbp,
        t.invoice_line_count,

        round(
            coalesce(t.invoice_line_subtotal_local, 0)
            - coalesce(h.header_subtotal_local, 0),
            2
        ) as invoice_subtotal_reconciliation_variance_local,

        round(
            coalesce(t.invoice_line_subtotal_gbp, 0)
            - coalesce(h.header_subtotal_gbp, 0),
            2
        ) as invoice_subtotal_reconciliation_variance_gbp

    from source_lines as l

    left join invoice_headers as h
        on l.vendor_invoice_id = h.vendor_invoice_id

    left join line_subtotal_totals as t
        on l.vendor_invoice_id = t.vendor_invoice_id

),

renamed as (

    select
        md5(trim(upper(cast(vendor_invoice_line_id as varchar)))) as vendor_invoice_line_hk,

        vendor_invoice_line_pk,
        vendor_invoice_line_id,

        vendor_invoice_hk,
        vendor_invoice_id,

        coalesce(vendor_hk, md5(trim(upper(cast(vendor_id as varchar))))) as vendor_hk,
        vendor_id,
        vendor_name,

        case
            when account_code is not null and trim(account_code) <> ''
            then md5(trim(upper(cast(account_code as varchar))))
            else md5('UNASSIGNED_GL_ACCOUNT')
        end as expense_gl_account_hk,

        coalesce(nullif(trim(cast(account_code as varchar)), ''), 'UNASSIGNED') as account_code,
        coalesce(nullif(trim(cast(expense_category as varchar)), ''), 'Unknown') as expense_category,

        invoice_date_hk,
        due_date_hk,
        posting_date_hk,
        posting_period_date_hk,

        case
            when service_period_start_date is not null
            then md5(strftime(service_period_start_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_start_date_hk,

        case
            when service_period_end_date is not null
            then md5(strftime(service_period_end_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as service_period_end_date_hk,

        invoice_number,
        invoice_date,
        due_date,
        posting_date,
        posting_period,

        service_period_start_date,
        service_period_end_date,

        line_number,
        line_description,

        currency_code,

        coalesce(line_amount_local, 0) as line_amount_local,
        coalesce(line_amount_gbp, 0) as line_amount_gbp,

        header_subtotal_local,
        header_subtotal_gbp,
        header_tax_amount_local,
        header_tax_amount_gbp,
        header_total_local,
        header_total_gbp,

        invoice_line_subtotal_local,
        invoice_line_subtotal_gbp,
        invoice_line_count,

        invoice_subtotal_reconciliation_variance_local,
        invoice_subtotal_reconciliation_variance_gbp,

        payment_status,
        coalesce(is_paid, false) as is_paid,
        coalesce(is_open, false) as is_open,
        coalesce(is_overdue, false) as is_overdue,

        case
            when service_period_start_date is not null
             and service_period_end_date is not null
             and service_period_end_date < service_period_start_date
            then true
            else false
        end as is_invalid_service_period,

        coalesce(is_defect, false) as is_line_defect,
        nullif(trim(cast(defect_type as varchar)), '') as line_defect_type,

        coalesce(is_header_defect, false) as is_header_defect,
        header_defect_type,
        coalesce(is_header_duplicate_vendor_invoice, false) as is_header_duplicate_vendor_invoice,
        coalesce(is_header_ap_cutoff_failure, false) as is_header_ap_cutoff_failure,

        case
            when coalesce(is_defect, false)
              or coalesce(is_header_defect, false)
            then true
            else false
        end as has_ap_control_exception,

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
