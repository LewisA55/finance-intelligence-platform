{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'vendor']
) }}

with vendor_master as (

    select
        trim(upper(cast(vendor_id as varchar))) as vendor_id,

        vendor_pk,
        nullif(trim(cast(vendor_name as varchar)), '') as vendor_name,
        coalesce(nullif(trim(cast(vendor_category as varchar)), ''), 'Unknown') as vendor_category,

        nullif(trim(cast(default_account_code as varchar)), '') as default_account_code,
        case
            when default_account_code is not null and trim(default_account_code) <> ''
            then md5(trim(upper(cast(default_account_code as varchar))))
            else md5('UNASSIGNED')
        end as default_gl_account_hk,

        coalesce(nullif(trim(upper(cast(default_department_id as varchar))), ''), 'UNASSIGNED') as default_department_id,
        md5(coalesce(nullif(trim(upper(cast(default_department_id as varchar))), ''), 'UNASSIGNED')) as default_department_hk,

        coalesce(nullif(trim(upper(cast(region_id as varchar))), ''), 'UNASSIGNED') as region_id,
        md5(coalesce(nullif(trim(upper(cast(region_id as varchar))), ''), 'UNASSIGNED')) as region_hk,

        coalesce(nullif(trim(upper(cast(currency as varchar))), ''), 'UNKNOWN') as currency_code,

        coalesce(nullif(trim(cast(cash_account_code as varchar)), ''), 'UNASSIGNED') as cash_account_code,
        md5(coalesce(nullif(trim(upper(cast(cash_account_code as varchar))), ''), 'UNASSIGNED')) as cash_gl_account_hk,

        coalesce(nullif(trim(cast(payment_terms as varchar)), ''), 'Unknown') as payment_terms,
        coalesce(nullif(trim(cast(vendor_status as varchar)), ''), 'Unknown') as vendor_status,
        coalesce(nullif(trim(cast(approval_status as varchar)), ''), 'Unknown') as approval_status,

        is_strategic_vendor,
        is_recurring_vendor,
        coalesce(nullif(trim(cast(risk_rating as varchar)), ''), 'Unknown') as risk_rating,
        coalesce(nullif(trim(cast(source_system as varchar)), ''), 'Unknown') as source_system,
        is_defect,
        nullif(trim(cast(defect_type as varchar)), '') as defect_type,
        created_date,
        updated_date,

        _atlas_row_hash,
        _atlas_ingested_at,
        _atlas_source_file

    from {{ ref('stg_procurement__vendors') }}
    where vendor_id is not null
      and trim(vendor_id) <> ''

),

vendor_invoices as (

    select
        trim(upper(cast(vendor_id as varchar))) as vendor_id,
        count(*) as vendor_invoice_rows
    from {{ ref('stg_procurement__vendor_invoices') }}
    where vendor_id is not null
      and trim(vendor_id) <> ''
    group by trim(upper(cast(vendor_id as varchar)))

),

vendor_invoice_lines as (

    select
        trim(upper(cast(vendor_id as varchar))) as vendor_id,
        count(*) as vendor_invoice_line_rows
    from {{ ref('stg_procurement__vendor_invoice_lines') }}
    where vendor_id is not null
      and trim(vendor_id) <> ''
    group by trim(upper(cast(vendor_id as varchar)))

),

vendor_payments as (

    select
        trim(upper(cast(vendor_id as varchar))) as vendor_id,
        count(*) as vendor_payment_rows
    from {{ ref('stg_procurement__vendor_payments') }}
    where vendor_id is not null
      and trim(vendor_id) <> ''
    group by trim(upper(cast(vendor_id as varchar)))

),

ap_ageing as (

    select
        trim(upper(cast(vendor_id as varchar))) as vendor_id,
        count(*) as ap_ageing_rows
    from {{ ref('stg_procurement__ap_ageing_snapshot') }}
    where vendor_id is not null
      and trim(vendor_id) <> ''
    group by trim(upper(cast(vendor_id as varchar)))

),

vendor_rows as (

    select
        md5(trim(upper(m.vendor_id))) as vendor_hk,

        m.vendor_pk,
        m.vendor_id,
        m.vendor_name,
        m.vendor_category,

        m.default_account_code,
        m.default_gl_account_hk,
        m.default_department_id,
        m.default_department_hk,
        m.region_id,
        m.region_hk,
        m.currency_code,
        m.cash_account_code,
        m.cash_gl_account_hk,

        m.payment_terms,
        m.vendor_status,
        m.approval_status,

        m.is_strategic_vendor,
        m.is_recurring_vendor,
        m.risk_rating,
        m.source_system,
        m.is_defect,
        m.defect_type,

        case
            when upper(m.vendor_id) like '%UNKNOWN%'
              or upper(coalesce(m.vendor_name, '')) like '%UNKNOWN%'
            then true
            else false
        end as is_unknown_vendor,

        case when coalesce(i.vendor_invoice_rows, 0) > 0 then true else false end as exists_in_vendor_invoices,
        case when coalesce(l.vendor_invoice_line_rows, 0) > 0 then true else false end as exists_in_vendor_invoice_lines,
        case when coalesce(p.vendor_payment_rows, 0) > 0 then true else false end as exists_in_vendor_payments,
        case when coalesce(a.ap_ageing_rows, 0) > 0 then true else false end as exists_in_ap_ageing,

        coalesce(i.vendor_invoice_rows, 0) as vendor_invoice_rows,
        coalesce(l.vendor_invoice_line_rows, 0) as vendor_invoice_line_rows,
        coalesce(p.vendor_payment_rows, 0) as vendor_payment_rows,
        coalesce(a.ap_ageing_rows, 0) as ap_ageing_rows,

        case
            when m.is_strategic_vendor then 10
            when m.is_recurring_vendor then 20
            else 30
        end as vendor_importance_sort,

        case
            when m.vendor_status = 'Active' then 10
            when m.vendor_status = 'Inactive' then 20
            else 99
        end as vendor_status_sort,

        m.created_date,
        m.updated_date,

        m._atlas_row_hash,
        m._atlas_ingested_at,
        m._atlas_source_file,

        false as is_unassigned

    from vendor_master as m
    left join vendor_invoices as i
        on m.vendor_id = i.vendor_id
    left join vendor_invoice_lines as l
        on m.vendor_id = l.vendor_id
    left join vendor_payments as p
        on m.vendor_id = p.vendor_id
    left join ap_ageing as a
        on m.vendor_id = a.vendor_id

),

unassigned_row as (

    select
        md5('UNASSIGNED') as vendor_hk,

        'UNASSIGNED_VENDOR' as vendor_pk,
        'UNASSIGNED' as vendor_id,
        'Unassigned Vendor' as vendor_name,
        'Unassigned' as vendor_category,

        'UNASSIGNED' as default_account_code,
        md5('UNASSIGNED') as default_gl_account_hk,
        'UNASSIGNED' as default_department_id,
        md5('UNASSIGNED') as default_department_hk,
        'UNASSIGNED' as region_id,
        md5('UNASSIGNED') as region_hk,
        'UNASSIGNED' as currency_code,
        'UNASSIGNED' as cash_account_code,
        md5('UNASSIGNED') as cash_gl_account_hk,

        'Unassigned' as payment_terms,
        'Unassigned' as vendor_status,
        'Unassigned' as approval_status,

        false as is_strategic_vendor,
        false as is_recurring_vendor,
        'Unassigned' as risk_rating,
        'Unassigned' as source_system,
        false as is_defect,
        cast(null as varchar) as defect_type,

        false as is_unknown_vendor,

        false as exists_in_vendor_invoices,
        false as exists_in_vendor_invoice_lines,
        false as exists_in_vendor_payments,
        false as exists_in_ap_ageing,

        0 as vendor_invoice_rows,
        0 as vendor_invoice_line_rows,
        0 as vendor_payment_rows,
        0 as ap_ageing_rows,

        -1 as vendor_importance_sort,
        -1 as vendor_status_sort,

        cast(null as date) as created_date,
        cast(null as date) as updated_date,

        cast(null as varchar) as _atlas_row_hash,
        cast(null as timestamp) as _atlas_ingested_at,
        cast(null as varchar) as _atlas_source_file,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from vendor_rows
