{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'executive_mart', 'billing', 'o2c', 'collections']
) }}

with invoices as (

    select
        invoice_id,
        customer_hk,
        invoice_date,
        due_date,
        cast(date_trunc('month', invoice_date) as date) as invoice_month,
        currency_code,
        total_billed_amount_local,
        total_billed_amount_gbp,
        invoice_status,
        is_defect

    from {{ ref('fct_billing_invoices') }}

),

customers as (

    select
        customer_hk,
        customer_id,
        region_hk
    from {{ ref('dim_customer') }}

),

invoice_base as (

    select
        customer_hk,
        invoice_month,

        md5(
            trim(upper(cast(customer_hk as varchar)))
            || '|'
            || strftime(invoice_month, '%Y-%m-%d')
        ) as o2c_customer_collections_hk,

        md5(strftime(invoice_month, '%Y-%m-%d')) as invoice_month_date_hk,

        count(distinct invoice_id) as invoice_count,
        count(distinct currency_code) as invoice_currency_count,

        round(sum(total_billed_amount_local), 2) as billed_amount_local,
        round(sum(total_billed_amount_gbp), 2) as billed_amount_gbp,

        round(avg(total_billed_amount_gbp), 2) as avg_invoice_amount_gbp,

        sum(case when is_defect then 1 else 0 end) as defective_invoice_count,
        sum(case when not is_defect then 1 else 0 end) as clean_invoice_count,

        sum(case when invoice_status = 'Paid' then 1 else 0 end) as paid_invoice_status_count,
        sum(case when invoice_status = 'Open' then 1 else 0 end) as open_invoice_status_count,
        sum(case when invoice_status = 'Overdue' then 1 else 0 end) as overdue_invoice_status_count,
        sum(case when invoice_status = 'Disputed' then 1 else 0 end) as disputed_invoice_status_count,
        sum(case when invoice_status = 'Written Off' then 1 else 0 end) as written_off_invoice_status_count

    from invoices
    group by
        customer_hk,
        invoice_month

),

invoice_lines as (

    select
        i.customer_hk,
        i.invoice_month,

        count(distinct l.invoice_line_id) as invoice_line_count,

        round(sum(l.line_amount_gbp), 2) as invoice_line_amount_gbp,
        round(sum(case when l.is_recurring_saas_line then l.line_amount_gbp else 0 end), 2) as recurring_saas_line_amount_gbp,
        round(sum(case when l.is_legacy_subscription_line then l.line_amount_gbp else 0 end), 2) as legacy_subscription_line_amount_gbp,
        round(sum(case when l.is_subscription_revenue then l.line_amount_gbp else 0 end), 2) as subscription_revenue_line_amount_gbp

    from {{ ref('fct_billing_invoice_lines') }} as l
    inner join invoices as i
        on l.invoice_id = i.invoice_id

    group by
        i.customer_hk,
        i.invoice_month

),

allocations_by_invoice as (

    select
        invoice_id,

        count(distinct allocation_id) as allocation_count,
        count(distinct payment_id) as distinct_payment_count,

        round(sum(allocated_amount_local), 2) as allocated_amount_local,
        round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp,

        round(sum(case when is_applied_allocation then allocated_amount_gbp else 0 end), 2) as applied_allocation_amount_gbp,
        round(sum(case when is_partially_applied_allocation then allocated_amount_gbp else 0 end), 2) as partially_applied_allocation_amount_gbp,
        round(sum(case when is_over_applied_allocation then allocated_amount_gbp else 0 end), 2) as over_applied_allocation_amount_gbp,

        sum(case when is_applied_allocation then 1 else 0 end) as applied_allocation_count,
        sum(case when is_partially_applied_allocation then 1 else 0 end) as partially_applied_allocation_count,
        sum(case when is_over_applied_allocation then 1 else 0 end) as over_applied_allocation_count,

        round(avg(days_invoice_to_allocation), 2) as avg_days_invoice_to_allocation,
        round(avg(days_due_to_allocation), 2) as avg_days_due_to_allocation,
        round(avg(days_payment_to_allocation), 2) as avg_days_payment_to_allocation

    from {{ ref('fct_billing_payment_allocations') }}
    group by invoice_id

),

allocation_payment_status_by_invoice as (

    select
        a.invoice_id,

        round(sum(case when p.payment_status = 'Fully Applied' then a.allocated_amount_gbp else 0 end), 2) as allocated_from_fully_applied_payments_gbp,
        round(sum(case when p.payment_status = 'Partially Applied' then a.allocated_amount_gbp else 0 end), 2) as allocated_from_partially_applied_payments_gbp,
        round(sum(case when p.payment_status = 'Unapplied' then a.allocated_amount_gbp else 0 end), 2) as allocated_from_unapplied_payments_gbp,

        count(distinct case when p.payment_status = 'Fully Applied' then p.payment_id end) as fully_applied_payment_count,
        count(distinct case when p.payment_status = 'Partially Applied' then p.payment_id end) as partially_applied_payment_count,
        count(distinct case when p.payment_status = 'Unapplied' then p.payment_id end) as unapplied_payment_count

    from {{ ref('fct_billing_payment_allocations') }} as a
    inner join {{ ref('fct_billing_payments') }} as p
        on a.payment_id = p.payment_id

    group by a.invoice_id

),

invoice_settlement as (

    select
        i.customer_hk,
        i.invoice_month,
        i.invoice_id,
        i.total_billed_amount_gbp,

        coalesce(a.allocation_count, 0) as allocation_count,
        coalesce(a.distinct_payment_count, 0) as distinct_payment_count,
        coalesce(a.allocated_amount_local, 0) as allocated_amount_local,
        coalesce(a.allocated_amount_gbp, 0) as allocated_amount_gbp,

        coalesce(a.applied_allocation_amount_gbp, 0) as applied_allocation_amount_gbp,
        coalesce(a.partially_applied_allocation_amount_gbp, 0) as partially_applied_allocation_amount_gbp,
        coalesce(a.over_applied_allocation_amount_gbp, 0) as over_applied_allocation_amount_gbp,

        coalesce(a.applied_allocation_count, 0) as applied_allocation_count,
        coalesce(a.partially_applied_allocation_count, 0) as partially_applied_allocation_count,
        coalesce(a.over_applied_allocation_count, 0) as over_applied_allocation_count,

        coalesce(ps.allocated_from_fully_applied_payments_gbp, 0) as allocated_from_fully_applied_payments_gbp,
        coalesce(ps.allocated_from_partially_applied_payments_gbp, 0) as allocated_from_partially_applied_payments_gbp,
        coalesce(ps.allocated_from_unapplied_payments_gbp, 0) as allocated_from_unapplied_payments_gbp,

        coalesce(ps.fully_applied_payment_count, 0) as fully_applied_payment_count,
        coalesce(ps.partially_applied_payment_count, 0) as partially_applied_payment_count,
        coalesce(ps.unapplied_payment_count, 0) as unapplied_payment_count,

        a.avg_days_invoice_to_allocation,
        a.avg_days_due_to_allocation,
        a.avg_days_payment_to_allocation,

        case
            when coalesce(a.allocated_amount_gbp, 0) = 0 then true
            else false
        end as has_no_allocation,

        case
            when coalesce(a.allocated_amount_gbp, 0) < i.total_billed_amount_gbp - 0.01 then true
            else false
        end as is_not_fully_allocated,

        case
            when coalesce(a.allocated_amount_gbp, 0) between i.total_billed_amount_gbp - 0.01 and i.total_billed_amount_gbp + 0.01 then true
            else false
        end as is_fully_allocated,

        case
            when coalesce(a.allocated_amount_gbp, 0) > i.total_billed_amount_gbp + 0.01 then true
            else false
        end as is_over_allocated,

        round(i.total_billed_amount_gbp - coalesce(a.allocated_amount_gbp, 0), 2) as net_unallocated_invoice_exposure_gbp,
        round(greatest(i.total_billed_amount_gbp - coalesce(a.allocated_amount_gbp, 0), 0), 2) as open_invoice_exposure_gbp

    from invoices as i

    left join allocations_by_invoice as a
        on i.invoice_id = a.invoice_id

    left join allocation_payment_status_by_invoice as ps
        on i.invoice_id = ps.invoice_id

),

settlement_agg as (

    select
        customer_hk,
        invoice_month,

        sum(allocation_count) as allocation_count,
        sum(distinct_payment_count) as distinct_payment_count,

        round(sum(allocated_amount_local), 2) as allocated_amount_local,
        round(sum(allocated_amount_gbp), 2) as allocated_amount_gbp,

        round(sum(applied_allocation_amount_gbp), 2) as applied_allocation_amount_gbp,
        round(sum(partially_applied_allocation_amount_gbp), 2) as partially_applied_allocation_amount_gbp,
        round(sum(over_applied_allocation_amount_gbp), 2) as over_applied_allocation_amount_gbp,

        sum(applied_allocation_count) as applied_allocation_count,
        sum(partially_applied_allocation_count) as partially_applied_allocation_count,
        sum(over_applied_allocation_count) as over_applied_allocation_count,

        round(sum(allocated_from_fully_applied_payments_gbp), 2) as allocated_from_fully_applied_payments_gbp,
        round(sum(allocated_from_partially_applied_payments_gbp), 2) as allocated_from_partially_applied_payments_gbp,
        round(sum(allocated_from_unapplied_payments_gbp), 2) as allocated_from_unapplied_payments_gbp,

        sum(fully_applied_payment_count) as fully_applied_payment_count,
        sum(partially_applied_payment_count) as partially_applied_payment_count,
        sum(unapplied_payment_count) as unapplied_payment_count,

        sum(case when has_no_allocation then 1 else 0 end) as invoices_with_no_allocation,
        sum(case when is_not_fully_allocated then 1 else 0 end) as invoices_not_fully_allocated,
        sum(case when is_fully_allocated then 1 else 0 end) as invoices_fully_allocated,
        sum(case when is_over_allocated then 1 else 0 end) as invoices_over_allocated,

        round(sum(net_unallocated_invoice_exposure_gbp), 2) as net_unallocated_invoice_exposure_gbp,
        round(sum(open_invoice_exposure_gbp), 2) as open_invoice_exposure_gbp,

        round(avg(avg_days_invoice_to_allocation), 2) as avg_days_invoice_to_allocation,
        round(avg(avg_days_due_to_allocation), 2) as avg_days_due_to_allocation,
        round(avg(avg_days_payment_to_allocation), 2) as avg_days_payment_to_allocation

    from invoice_settlement
    group by
        customer_hk,
        invoice_month

),

final as (

    select
        b.o2c_customer_collections_hk,
        b.customer_hk,
        c.customer_id,
        c.region_hk,
        b.invoice_month_date_hk,
        b.invoice_month,

        b.invoice_count,
        coalesce(l.invoice_line_count, 0) as invoice_line_count,
        b.invoice_currency_count,

        b.billed_amount_local,
        b.billed_amount_gbp,
        b.avg_invoice_amount_gbp,

        coalesce(l.invoice_line_amount_gbp, 0) as invoice_line_amount_gbp,
        coalesce(l.recurring_saas_line_amount_gbp, 0) as recurring_saas_line_amount_gbp,
        coalesce(l.legacy_subscription_line_amount_gbp, 0) as legacy_subscription_line_amount_gbp,
        coalesce(l.subscription_revenue_line_amount_gbp, 0) as subscription_revenue_line_amount_gbp,

        coalesce(s.allocation_count, 0) as allocation_count,
        coalesce(s.distinct_payment_count, 0) as distinct_payment_count,

        coalesce(s.allocated_amount_local, 0) as allocated_amount_local,
        coalesce(s.allocated_amount_gbp, 0) as allocated_amount_gbp,

        case
            when b.billed_amount_gbp = 0 then 0
            else round(coalesce(s.allocated_amount_gbp, 0) / b.billed_amount_gbp, 6)
        end as gross_collection_rate,

        case
            when b.billed_amount_gbp = 0 then 0
            else round(
                least(coalesce(s.allocated_amount_gbp, 0), b.billed_amount_gbp) / b.billed_amount_gbp,
                6
            )
        end as capped_collection_rate,

        coalesce(s.net_unallocated_invoice_exposure_gbp, b.billed_amount_gbp) as net_unallocated_invoice_exposure_gbp,
        coalesce(s.open_invoice_exposure_gbp, b.billed_amount_gbp) as open_invoice_exposure_gbp,

        case
            when b.billed_amount_gbp = 0 then 0
            else round(
                coalesce(s.open_invoice_exposure_gbp, b.billed_amount_gbp) / b.billed_amount_gbp,
                6
            )
        end as open_exposure_rate,

        coalesce(s.applied_allocation_amount_gbp, 0) as applied_allocation_amount_gbp,
        coalesce(s.partially_applied_allocation_amount_gbp, 0) as partially_applied_allocation_amount_gbp,
        coalesce(s.over_applied_allocation_amount_gbp, 0) as over_applied_allocation_amount_gbp,

        coalesce(s.applied_allocation_count, 0) as applied_allocation_count,
        coalesce(s.partially_applied_allocation_count, 0) as partially_applied_allocation_count,
        coalesce(s.over_applied_allocation_count, 0) as over_applied_allocation_count,

        coalesce(s.allocated_from_fully_applied_payments_gbp, 0) as allocated_from_fully_applied_payments_gbp,
        coalesce(s.allocated_from_partially_applied_payments_gbp, 0) as allocated_from_partially_applied_payments_gbp,
        coalesce(s.allocated_from_unapplied_payments_gbp, 0) as allocated_from_unapplied_payments_gbp,

        coalesce(s.fully_applied_payment_count, 0) as fully_applied_payment_count,
        coalesce(s.partially_applied_payment_count, 0) as partially_applied_payment_count,
        coalesce(s.unapplied_payment_count, 0) as unapplied_payment_count,

        coalesce(s.invoices_with_no_allocation, b.invoice_count) as invoices_with_no_allocation,
        coalesce(s.invoices_not_fully_allocated, b.invoice_count) as invoices_not_fully_allocated,
        coalesce(s.invoices_fully_allocated, 0) as invoices_fully_allocated,
        coalesce(s.invoices_over_allocated, 0) as invoices_over_allocated,

        b.clean_invoice_count,
        b.defective_invoice_count,

        b.paid_invoice_status_count,
        b.open_invoice_status_count,
        b.overdue_invoice_status_count,
        b.disputed_invoice_status_count,
        b.written_off_invoice_status_count,

        s.avg_days_invoice_to_allocation,
        s.avg_days_due_to_allocation,
        s.avg_days_payment_to_allocation,

        case
            when coalesce(s.open_invoice_exposure_gbp, b.billed_amount_gbp) > 0 then true
            else false
        end as has_open_exposure,

        case
            when coalesce(s.over_applied_allocation_amount_gbp, 0) > 0 then true
            else false
        end as has_over_applied_cash,

        case
            when coalesce(s.allocated_amount_gbp, 0) = 0 then 'No Collections'
            when coalesce(s.allocated_amount_gbp, 0) < b.billed_amount_gbp - 0.01 then 'Partially Collected'
            when coalesce(s.allocated_amount_gbp, 0) > b.billed_amount_gbp + 0.01 then 'Over Collected'
            else 'Fully Collected'
        end as collection_status

    from invoice_base as b

    left join invoice_lines as l
        on b.customer_hk = l.customer_hk
        and b.invoice_month = l.invoice_month

    left join settlement_agg as s
        on b.customer_hk = s.customer_hk
        and b.invoice_month = s.invoice_month

    left join customers as c
        on b.customer_hk = c.customer_hk

)

select *
from final
