{#
  Publishes two small curated SaaS slices into the dashboard's committed data
  folder, aggregated from the (large) gold SaaS marts so the browser never loads
  the 200k-row detail. Run after a parquet export:

      dbt run-operation export_saas_aggregates

  Grain:
    - mart_saas_arr_by_product_segment : month x product_family x customer_segment
    - mart_saas_retention_by_segment   : month x customer_segment
  Rates (NRR/GRR/logo) are intentionally NOT precomputed -- components are shipped
  so the app can weight them correctly when slicing.
#}
{% macro export_saas_aggregates() %}

{% set arr_sql %}
copy (
  select
    reporting_month_date,
    case
      when product_id in ('100','101','102') then 'Core'
      when product_id in ('103','104','105') then 'Analytics'
      when product_id in ('106','107','108') then 'AI'
      when product_id in ('109','110','111') then 'Professional Services'
      when product_id = '112' then 'Legacy'
      else 'Other'
    end as product_family,
    customer_segment,
    round(sum(active_arr_gbp), 2)         as active_arr_gbp,
    round(sum(ending_arr_gbp), 2)         as ending_arr_gbp,
    round(sum(new_business_arr_gbp), 2)   as new_business_arr_gbp,
    round(sum(expansion_arr_gbp), 2)      as expansion_arr_gbp,
    round(sum(price_increase_arr_gbp), 2) as price_increase_arr_gbp,
    round(sum(contraction_arr_gbp), 2)    as contraction_arr_gbp,
    round(sum(churn_arr_gbp), 2)          as churn_arr_gbp,
    round(sum(pause_arr_gbp), 2)          as pause_arr_gbp,
    round(sum(net_arr_delta_gbp), 2)      as net_arr_delta_gbp,
    sum(active_subscription_count)        as active_subscriptions,
    sum(case when has_saas_control_issue then 1 else 0 end) as control_exception_count
  from read_parquet('data/exports/powerbi/parquet/mart_saas_arr_movement.parquet')
  group by 1, 2, 3
) to 'dashboard/public/data/mart_saas_arr_by_product_segment.parquet' (format parquet)
{% endset %}
{% do run_query(arr_sql) %}

{% set ret_sql %}
copy (
  select
    reporting_month_date,
    customer_segment,
    round(sum(beginning_arr_gbp), 2)      as beginning_arr_gbp,
    round(sum(gross_retained_arr_gbp), 2) as gross_retained_arr_gbp,
    round(sum(net_retained_arr_gbp), 2)   as net_retained_arr_gbp,
    round(sum(expansion_arr_gbp), 2)      as expansion_arr_gbp,
    round(sum(contraction_arr_gbp), 2)    as contraction_arr_gbp,
    round(sum(churn_arr_gbp), 2)          as churn_arr_gbp,
    sum(beginning_active_customer_count)  as beginning_customers,
    sum(ending_active_customer_count)     as ending_customers,
    sum(retained_customer_count)          as retained_customers,
    sum(churned_customer_count)           as churned_customers,
    sum(paused_customer_count)            as paused_customers,
    sum(new_customer_count)               as new_customers
  from read_parquet('data/exports/powerbi/parquet/mart_saas_retention.parquet')
  group by 1, 2
) to 'dashboard/public/data/mart_saas_retention_by_segment.parquet' (format parquet)
{% endset %}
{% do run_query(ret_sql) %}

{% do log('SaaS product/segment aggregates exported to dashboard/public/data/.', info=true) %}
{% endmacro %}
