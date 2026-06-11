/*
    Test: mart_deferred_revenue_control deferred revenue account mapping is governed.

    Failure condition:
    A Subscription Revenue row is not mapped to deferred revenue liability
    account 2100.
*/

select
    deferred_revenue_control_hk,
    period_month,
    period_status,
    currency_code,
    revenue_category,
    mapped_account_code,
    deferred_revenue_account_mapping_method
from {{ ref('mart_deferred_revenue_control') }}
where revenue_category = 'Subscription Revenue'
  and mapped_account_code <> '2100'
