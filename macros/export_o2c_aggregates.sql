{#
  Publishes two small curated AR / order-to-cash slices into the dashboard's
  committed data folder, aggregated from mart_o2c_customer_collections so the
  browser never loads the ~3 MB customer-level detail. Run after a parquet export:

      dbt run-operation export_o2c_aggregates

  Slices:
    - mart_o2c_top_customers     : top 25 customers by open AR at the latest month
    - mart_o2c_by_region_segment : month x region x segment collection metrics
  Note: O2C carries open exposure + overdue/disputed COUNTS, not GBP ageing buckets,
  so the AR view uses overdue exposure + collection status rather than aged buckets.
#}
{% macro export_o2c_aggregates() %}

{% set o2c = "read_parquet('data/exports/powerbi/parquet/mart_o2c_customer_collections.parquet')" %}
{% set dc = "read_parquet('data/exports/powerbi/parquet/dim_customer.parquet')" %}
{% set dr = "read_parquet('data/exports/powerbi/parquet/dim_region.parquet')" %}

{% set top_customers_sql %}
copy (
  with latest as (
    select max(invoice_month) as m
    from {{ o2c }}
    where invoice_month between date '2026-01-01' and date '2026-12-01'
      and billed_amount_gbp > 0
  )
  select
    coalesce(c.customer_name, o.customer_id)    as customer_name,
    coalesce(c.customer_segment, 'Unknown')     as customer_segment,
    coalesce(c.industry, 'Unknown')             as industry,
    coalesce(r.region_name, 'Unassigned')       as region,
    round(o.billed_amount_gbp, 2)               as billed,
    round(o.allocated_amount_gbp, 2)            as collected,
    round(o.open_invoice_exposure_gbp, 2)       as open_ar,
    o.overdue_invoice_status_count              as overdue_invoices,
    o.disputed_invoice_status_count             as disputed_invoices,
    round(o.gross_collection_rate, 4)           as collection_rate,
    o.collection_status                         as collection_status
  from {{ o2c }} as o
  join latest on o.invoice_month = latest.m
  left join {{ dc }} as c on o.customer_hk = c.customer_hk
  left join {{ dr }} as r on o.region_hk = r.region_hk
  where o.open_invoice_exposure_gbp > 0
  order by o.open_invoice_exposure_gbp desc
  limit 25
) to 'dashboard/public/data/mart_o2c_top_customers.parquet' (format parquet)
{% endset %}
{% do run_query(top_customers_sql) %}

{% set region_segment_sql %}
copy (
  select
    o.invoice_month                             as invoice_month,
    coalesce(r.region_name, 'Unassigned')       as region,
    coalesce(c.customer_segment, 'Unknown')     as customer_segment,
    round(sum(o.billed_amount_gbp), 2)          as billed,
    round(sum(o.allocated_amount_gbp), 2)       as collected,
    round(sum(o.open_invoice_exposure_gbp), 2)  as open_ar,
    sum(o.overdue_invoice_status_count)         as overdue_invoices,
    sum(o.disputed_invoice_status_count)        as disputed_invoices
  from {{ o2c }} as o
  left join {{ dc }} as c on o.customer_hk = c.customer_hk
  left join {{ dr }} as r on o.region_hk = r.region_hk
  where o.invoice_month between date '2026-01-01' and date '2026-12-01'
  group by 1, 2, 3
) to 'dashboard/public/data/mart_o2c_by_region_segment.parquet' (format parquet)
{% endset %}
{% do run_query(region_segment_sql) %}

{% do log('O2C / AR aggregates exported to dashboard/public/data/.', info=true) %}
{% endmacro %}
