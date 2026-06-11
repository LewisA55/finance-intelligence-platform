/*
    Test: fct_vendor_payments cash account maps to a cash account.

    Failure condition:
    The cash account hash does not map to an active cash account.
*/

select
    p.vendor_payment_hk,
    p.vendor_payment_id,
    p.cash_account_code,
    a.account_code,
    a.account_name,
    a.is_cash_account,
    a.is_active
from {{ ref('fct_vendor_payments') }} as p
left join {{ ref('dim_gl_account') }} as a
    on p.cash_account_hk = a.gl_account_hk
where coalesce(a.is_cash_account, false) = false
   or coalesce(a.is_active, false) = false
