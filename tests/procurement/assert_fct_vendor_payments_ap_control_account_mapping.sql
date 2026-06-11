/*
    Test: fct_vendor_payments maps AP control account to 2300 Accounts Payable.

    Failure condition:
    The AP control account hash does not map to account_code 2300.
*/

select
    p.vendor_payment_hk,
    p.vendor_payment_id,
    a.account_code,
    a.account_name
from {{ ref('fct_vendor_payments') }} as p
left join {{ ref('dim_gl_account') }} as a
    on p.ap_control_account_hk = a.gl_account_hk
where a.account_code <> '2300'
