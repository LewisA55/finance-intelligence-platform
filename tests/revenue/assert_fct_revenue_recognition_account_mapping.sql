/*
    Test: fct_revenue_recognition revenue account mapping is governed.

    Failure condition:
    A recognised Subscription Revenue row is not mapped to GL account 4100.
*/

select
    revenue_recognition_hk,
    recognition_id,
    revenue_category,
    mapped_account_code,
    revenue_account_mapping_method
from {{ ref('fct_revenue_recognition') }}
where revenue_category = 'Subscription Revenue'
  and mapped_account_code <> '4100'
