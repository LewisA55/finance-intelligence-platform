{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'mart', 'revenue', 'waterfall', 'customer_month', 'cfo']
) }}

with billing_monthly as (

    select
        customer_hk,
        region_hk,
        date_trunc('month', invoice_date) as reporting_month,
        currency_code,

        count(distinct invoice_id) as billed_invoice_count,
        count(*) as billed_invoice_line_count,

        round(sum(coalesce(line_amount_local, 0)), 2) as billed_amount_local,
        round(sum(coalesce(line_amount_gbp, 0)), 2) as billed_amount_gbp,

        sum(case when is_defect then 1 else 0 end) as billed_defect_line_count,
        round(sum(case when is_defect then coalesce(line_amount_gbp, 0) else 0 end), 2) as billed_defect_amount_gbp

    from {{ ref('fct_billing_invoice_lines') }}

    group by
        customer_hk,
        region_hk,
        date_trunc('month', invoice_date),
        currency_code

),

recognition_monthly as (

    select
        customer_hk,
        region_hk,
        recognition_month as reporting_month,
        currency_code,

        count(*) as recognition_row_count,

        sum(case when is_actual_recognition then 1 else 0 end) as actual_recognition_row_count,
        sum(case when is_scheduled_recognition then 1 else 0 end) as scheduled_recognition_row_count,

        round(sum(case when is_actual_recognition then coalesce(recognised_revenue_local, 0) else 0 end), 2) as recognised_revenue_actual_local,
        round(sum(case when is_actual_recognition then coalesce(recognised_revenue_gbp, 0) else 0 end), 2) as recognised_revenue_actual_gbp,

        round(sum(case when is_scheduled_recognition then coalesce(recognised_revenue_local, 0) else 0 end), 2) as recognised_revenue_scheduled_local,
        round(sum(case when is_scheduled_recognition then coalesce(recognised_revenue_gbp, 0) else 0 end), 2) as recognised_revenue_scheduled_gbp,

        round(sum(coalesce(recognised_revenue_local, 0)), 2) as recognised_revenue_total_local,
        round(sum(coalesce(recognised_revenue_gbp, 0)), 2) as recognised_revenue_total_gbp,

        sum(case when is_recognition_window_outside_service_period then 1 else 0 end) as recognition_window_exception_count,
        sum(case when is_zero_recognised_revenue_gbp then 1 else 0 end) as zero_recognition_row_count,
        sum(case when is_defect then 1 else 0 end) as recognition_defect_row_count

    from {{ ref('fct_revenue_recognition') }}

    group by
        customer_hk,
        region_hk,
        recognition_month,
        currency_code

),

recognition_schedule_totals_by_line as (

    select
        invoice_line_id,
        count(*) as recognition_row_count,
        round(sum(coalesce(recognised_revenue_gbp, 0)), 2) as recognised_revenue_gbp

    from {{ ref('fct_revenue_recognition') }}

    group by
        invoice_line_id

),

invoice_line_recognition_coverage as (

    select
        l.customer_hk,
        l.region_hk,
        date_trunc('month', l.invoice_date) as reporting_month,
        l.currency_code,
        l.invoice_line_id,

        coalesce(l.line_amount_gbp, 0) as line_amount_gbp,
        coalesce(s.recognition_row_count, 0) as recognition_row_count,
        coalesce(s.recognised_revenue_gbp, 0) as recognised_revenue_gbp,

        round(
            coalesce(s.recognised_revenue_gbp, 0)
            - coalesce(l.line_amount_gbp, 0),
            2
        ) as recognition_variance_gbp,

        coalesce(l.is_defect, false) as is_defect,
        l.defect_type

    from {{ ref('fct_billing_invoice_lines') }} as l

    left join recognition_schedule_totals_by_line as s
        on l.invoice_line_id = s.invoice_line_id

),

governance_monthly as (

    select
        customer_hk,
        region_hk,
        reporting_month,
        currency_code,

        sum(case when recognition_row_count = 0 then 1 else 0 end) as unscheduled_billing_lines_count,

        round(
            sum(case when recognition_row_count = 0 then line_amount_gbp else 0 end),
            2
        ) as unscheduled_billing_leakage_gbp,

        sum(
            case
                when recognition_row_count > 0
                 and abs(recognition_variance_gbp) > 0.01
                then 1 else 0
            end
        ) as recognition_variance_line_count,

        round(
            sum(case when recognition_row_count > 0 then recognition_variance_gbp else 0 end),
            2
        ) as recognition_variance_gbp,

        sum(case when is_defect then 1 else 0 end) as governance_defect_line_count,

        round(
            sum(case when is_defect then line_amount_gbp else 0 end),
            2
        ) as governance_defect_amount_gbp

    from invoice_line_recognition_coverage

    group by
        customer_hk,
        region_hk,
        reporting_month,
        currency_code

),

customer_month_spine as (

    select
        customer_hk,
        region_hk,
        reporting_month,
        currency_code
    from billing_monthly

    union

    select
        customer_hk,
        region_hk,
        reporting_month,
        currency_code
    from recognition_monthly

),

combined as (

    select
        md5(
            coalesce(spine.customer_hk, md5('UNASSIGNED_CUSTOMER'))
            || '|'
            || strftime(spine.reporting_month, '%Y-%m-%d')
            || '|'
            || coalesce(spine.currency_code, 'UNKNOWN')
        ) as revenue_waterfall_hk,

        spine.customer_hk,
        spine.region_hk,

        case
            when spine.reporting_month is not null
            then md5(strftime(spine.reporting_month, '%Y-%m-%d'))
            else md5('UNASSIGNED')
        end as reporting_month_date_hk,

        spine.reporting_month,
        spine.currency_code,

        coalesce(b.billed_invoice_count, 0) as billed_invoice_count,
        coalesce(b.billed_invoice_line_count, 0) as billed_invoice_line_count,
        coalesce(b.billed_amount_local, 0) as billed_amount_local,
        coalesce(b.billed_amount_gbp, 0) as billed_amount_gbp,
        coalesce(b.billed_defect_line_count, 0) as billed_defect_line_count,
        coalesce(b.billed_defect_amount_gbp, 0) as billed_defect_amount_gbp,

        coalesce(r.recognition_row_count, 0) as recognition_row_count,
        coalesce(r.actual_recognition_row_count, 0) as actual_recognition_row_count,
        coalesce(r.scheduled_recognition_row_count, 0) as scheduled_recognition_row_count,

        coalesce(r.recognised_revenue_actual_local, 0) as recognised_revenue_actual_local,
        coalesce(r.recognised_revenue_actual_gbp, 0) as recognised_revenue_actual_gbp,
        coalesce(r.recognised_revenue_scheduled_local, 0) as recognised_revenue_scheduled_local,
        coalesce(r.recognised_revenue_scheduled_gbp, 0) as recognised_revenue_scheduled_gbp,
        coalesce(r.recognised_revenue_total_local, 0) as recognised_revenue_total_local,
        coalesce(r.recognised_revenue_total_gbp, 0) as recognised_revenue_total_gbp,

        coalesce(r.recognition_window_exception_count, 0) as recognition_window_exception_count,
        coalesce(r.zero_recognition_row_count, 0) as zero_recognition_row_count,
        coalesce(r.recognition_defect_row_count, 0) as recognition_defect_row_count,

        coalesce(g.unscheduled_billing_lines_count, 0) as unscheduled_billing_lines_count,
        coalesce(g.unscheduled_billing_leakage_gbp, 0) as unscheduled_billing_leakage_gbp,
        coalesce(g.recognition_variance_line_count, 0) as recognition_variance_line_count,
        coalesce(g.recognition_variance_gbp, 0) as recognition_variance_gbp,
        coalesce(g.governance_defect_line_count, 0) as governance_defect_line_count,
        coalesce(g.governance_defect_amount_gbp, 0) as governance_defect_amount_gbp,

        case when b.customer_hk is not null then true else false end as has_billing,
        case when r.customer_hk is not null then true else false end as has_recognition,
        case when coalesce(r.actual_recognition_row_count, 0) > 0 then true else false end as has_actual_recognition,
        case when coalesce(r.scheduled_recognition_row_count, 0) > 0 then true else false end as has_scheduled_recognition,

        case
            when b.customer_hk is not null
             and r.customer_hk is null
            then true else false
        end as is_billing_only,

        case
            when b.customer_hk is null
             and r.customer_hk is not null
            then true else false
        end as is_recognition_only,

        case
            when b.customer_hk is not null
             and r.customer_hk is not null
            then true else false
        end as is_billing_and_recognition,

        case
            when coalesce(r.scheduled_recognition_row_count, 0) > 0
             and coalesce(b.billed_invoice_line_count, 0) = 0
            then true else false
        end as is_scheduled_backlog_month,

        case
            when coalesce(g.unscheduled_billing_lines_count, 0) > 0
              or abs(coalesce(g.recognition_variance_gbp, 0)) > 0.01
              or coalesce(r.recognition_window_exception_count, 0) > 0
              or coalesce(r.zero_recognition_row_count, 0) > 0
            then true
            else false
        end as has_revenue_governance_exception,

        current_timestamp as _atlas_modelled_at

    from customer_month_spine as spine

    left join billing_monthly as b
        on spine.customer_hk = b.customer_hk
       and spine.reporting_month = b.reporting_month
       and spine.currency_code = b.currency_code

    left join recognition_monthly as r
        on spine.customer_hk = r.customer_hk
       and spine.reporting_month = r.reporting_month
       and spine.currency_code = r.currency_code

    left join governance_monthly as g
        on spine.customer_hk = g.customer_hk
       and spine.reporting_month = g.reporting_month
       and spine.currency_code = g.currency_code

)

select *
from combined
