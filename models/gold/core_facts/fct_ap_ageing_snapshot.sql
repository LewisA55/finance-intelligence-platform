{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_fact', 'procurement', 'ap', 'ap_ageing', 'working_capital', 'p2p']
) }}

with source_ageing as (

    select
        snapshot_pk,
        snapshot_date,
        vendor_invoice_id,
        vendor_id,
        vendor_name,
        invoice_number,
        invoice_date,
        due_date,
        days_past_due,
        ageing_bucket,
        ap_status,
        currency,
        invoice_total_local,
        invoice_total_gbp,
        paid_amount_local,
        paid_amount_gbp,
        open_amount_local,
        open_amount_gbp,
        source_system,
        is_defect,
        defect_type,
        created_date,
        updated_date,
        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_procurement__ap_ageing_snapshot') }}

),

invoice_headers as (

    select
        vendor_invoice_hk,
        vendor_invoice_id,
        vendor_hk,
        invoice_number as header_invoice_number,
        invoice_date_hk as header_invoice_date_hk,
        due_date_hk as header_due_date_hk,
        posting_date_hk,
        posting_period_date_hk,
        invoice_date as header_invoice_date,
        due_date as header_due_date,
        posting_date,
        posting_period,
        currency_code as header_currency_code,
        total_local as header_invoice_total_local,
        total_gbp as header_invoice_total_gbp,
        payment_status as header_payment_status,
        is_paid as is_header_paid,
        is_open as is_header_open,
        is_overdue as is_header_overdue,
        is_defect as is_header_defect,
        defect_type as header_defect_type,
        is_duplicate_vendor_invoice as is_header_duplicate_vendor_invoice,
        is_ap_cutoff_failure as is_header_ap_cutoff_failure

    from {{ ref('fct_vendor_invoices') }}

),

payment_totals as (

    select
        vendor_invoice_hk,
        vendor_invoice_id,
        round(sum(coalesce(payment_amount_local, 0)), 2) as calculated_paid_amount_local,
        round(sum(coalesce(payment_amount_gbp, 0)), 2) as calculated_paid_amount_gbp,
        count(*) as payment_count,
        max(payment_date) as latest_payment_date
    from {{ ref('fct_vendor_payments') }}
    group by
        vendor_invoice_hk,
        vendor_invoice_id

),

joined as (

    select
        a.*,

        h.vendor_invoice_hk,
        h.vendor_hk,
        h.header_invoice_number,
        h.header_invoice_date_hk,
        h.header_due_date_hk,
        h.posting_date_hk,
        h.posting_period_date_hk,
        h.header_invoice_date,
        h.header_due_date,
        h.posting_date,
        h.posting_period,
        h.header_currency_code,
        h.header_invoice_total_local,
        h.header_invoice_total_gbp,
        h.header_payment_status,
        h.is_header_paid,
        h.is_header_open,
        h.is_header_overdue,
        h.is_header_defect,
        h.header_defect_type,
        h.is_header_duplicate_vendor_invoice,
        h.is_header_ap_cutoff_failure,

        coalesce(p.calculated_paid_amount_local, 0) as calculated_paid_amount_local,
        coalesce(p.calculated_paid_amount_gbp, 0) as calculated_paid_amount_gbp,
        coalesce(p.payment_count, 0) as payment_count,
        p.latest_payment_date,

        round(
            coalesce(h.header_invoice_total_local, a.invoice_total_local, 0)
            - coalesce(p.calculated_paid_amount_local, 0),
            2
        ) as calculated_open_amount_local,

        round(
            coalesce(h.header_invoice_total_gbp, a.invoice_total_gbp, 0)
            - coalesce(p.calculated_paid_amount_gbp, 0),
            2
        ) as calculated_open_amount_gbp

    from source_ageing as a

    left join invoice_headers as h
        on a.vendor_invoice_id = h.vendor_invoice_id

    left join payment_totals as p
        on h.vendor_invoice_hk = p.vendor_invoice_hk

),

renamed as (

    select
        md5(trim(upper(cast(snapshot_pk as varchar)))) as ap_ageing_snapshot_hk,

        snapshot_pk,

        case
            when snapshot_date is not null
            then md5(strftime(snapshot_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as snapshot_date_hk,

        snapshot_date,

        vendor_invoice_hk,
        vendor_invoice_id,

        coalesce(vendor_hk, md5(trim(upper(cast(vendor_id as varchar))))) as vendor_hk,
        vendor_id,
        vendor_name,

        case
            when invoice_date is not null
            then md5(strftime(invoice_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as invoice_date_hk,

        case
            when due_date is not null
            then md5(strftime(due_date, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as due_date_hk,

        posting_date_hk,
        posting_period_date_hk,

        invoice_number,
        header_invoice_number,

        invoice_date,
        due_date,
        header_invoice_date,
        header_due_date,
        posting_date,
        posting_period,

        days_past_due,

        coalesce(nullif(trim(cast(ageing_bucket as varchar)), ''), 'Unknown') as source_ageing_bucket,

        case
            when days_past_due <= 0 then 'Current'
            when days_past_due between 1 and 30 then '1-30 Days Overdue'
            when days_past_due between 31 and 60 then '31-60 Days Overdue'
            when days_past_due between 61 and 90 then '61-90 Days Overdue'
            when days_past_due >= 91 then '91+ Days Overdue'
            else 'Unknown'
        end as ageing_bucket,

        case
            when days_past_due <= 0 then 1
            when days_past_due between 1 and 30 then 2
            when days_past_due between 31 and 60 then 3
            when days_past_due between 61 and 90 then 4
            when days_past_due >= 91 then 5
            else 99
        end as ageing_bucket_sort,

        coalesce(nullif(trim(cast(ap_status as varchar)), ''), 'Unknown') as ap_status,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,
        header_currency_code,

        coalesce(invoice_total_local, 0) as invoice_total_local,
        coalesce(invoice_total_gbp, 0) as invoice_total_gbp,
        coalesce(paid_amount_local, 0) as paid_amount_local,
        coalesce(paid_amount_gbp, 0) as paid_amount_gbp,
        coalesce(open_amount_local, 0) as open_amount_local,
        coalesce(open_amount_gbp, 0) as open_amount_gbp,

        header_invoice_total_local,
        header_invoice_total_gbp,
        calculated_paid_amount_local,
        calculated_paid_amount_gbp,
        calculated_open_amount_local,
        calculated_open_amount_gbp,
        payment_count,
        latest_payment_date,

        round(coalesce(invoice_total_local, 0) - coalesce(paid_amount_local, 0) - coalesce(open_amount_local, 0), 2)
            as source_open_amount_arithmetic_variance_local,

        round(coalesce(invoice_total_gbp, 0) - coalesce(paid_amount_gbp, 0) - coalesce(open_amount_gbp, 0), 2)
            as source_open_amount_arithmetic_variance_gbp,

        round(coalesce(paid_amount_local, 0) - coalesce(calculated_paid_amount_local, 0), 2)
            as paid_amount_reconciliation_variance_local,

        round(coalesce(paid_amount_gbp, 0) - coalesce(calculated_paid_amount_gbp, 0), 2)
            as paid_amount_reconciliation_variance_gbp,

        round(coalesce(open_amount_local, 0) - coalesce(calculated_open_amount_local, 0), 2)
            as open_amount_reconciliation_variance_local,

        round(coalesce(open_amount_gbp, 0) - coalesce(calculated_open_amount_gbp, 0), 2)
            as open_amount_reconciliation_variance_gbp,

        coalesce(is_header_paid, false) as is_header_paid,
        coalesce(is_header_open, false) as is_header_open,
        coalesce(is_header_overdue, false) as is_header_overdue,

        case when coalesce(open_amount_gbp, 0) > 0 then true else false end as is_open_ap_exposure,
        case when coalesce(days_past_due, 0) <= 0 then true else false end as is_current,
        case when coalesce(days_past_due, 0) > 0 then true else false end as is_overdue,
        case when days_past_due between 1 and 30 then true else false end as is_1_30_overdue,
        case when days_past_due between 31 and 60 then true else false end as is_31_60_overdue,
        case when days_past_due between 61 and 90 then true else false end as is_61_90_overdue,
        case when days_past_due >= 91 then true else false end as is_91_plus_overdue,

        case
            when vendor_invoice_hk is null then true else false
        end as is_orphan_vendor_invoice_ageing_row,

        coalesce(is_defect, false) as is_ageing_defect,
        nullif(trim(cast(defect_type as varchar)), '') as ageing_defect_type,

        coalesce(is_header_defect, false) as is_header_defect,
        header_defect_type,
        coalesce(is_header_duplicate_vendor_invoice, false) as is_header_duplicate_vendor_invoice,
        coalesce(is_header_ap_cutoff_failure, false) as is_header_ap_cutoff_failure,

        case
            when coalesce(is_defect, false)
              or coalesce(is_header_defect, false)
              or vendor_invoice_hk is null
              or abs(round(coalesce(invoice_total_gbp, 0) - coalesce(paid_amount_gbp, 0) - coalesce(open_amount_gbp, 0), 2)) > 0.01
              or abs(round(coalesce(open_amount_gbp, 0) - coalesce(calculated_open_amount_gbp, 0), 2)) > 0.01
            then true
            else false
        end as has_ap_ageing_control_exception,

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
