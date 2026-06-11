/*
    Test: fct_revenue_recognition recognised revenue is non-negative.

    Failure condition:
    Any row has negative recognised revenue in local or GBP currency.
*/

select
    revenue_recognition_hk,
    recognition_id,
    recognised_revenue_local,
    recognised_revenue_gbp
from {{ ref('fct_revenue_recognition') }}
where recognised_revenue_local < 0
   or recognised_revenue_gbp < 0
