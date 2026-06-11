/*
    Test: fct_deferred_revenue_rollforward deferred revenue account mapping is governed.

    Failure condition:
    A Subscription Revenue rollforward row is not mapped to deferred revenue
    liability account 2100.
*/

select
    deferred_revenue_rollforward_hk,
    rollforward_pk,
    revenue_category,
    mapped_account_code,
    deferred_revenue_account_mapping_method
from {{ ref('fct_deferred_revenue_rollforward') }}
where revenue_category = 'Subscription Revenue'
  and mapped_account_code <> '2100'
