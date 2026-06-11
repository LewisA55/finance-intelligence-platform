/*
    Test: fct_vendor_invoice_lines map to expense-class GL accounts.

    Failure condition:
    A line-level account maps to a non-expense account class.
*/

select
    l.vendor_invoice_line_hk,
    l.vendor_invoice_line_id,
    l.account_code,
    a.account_name,
    a.account_class,
    a.account_type
from {{ ref('fct_vendor_invoice_lines') }} as l
left join {{ ref('dim_gl_account') }} as a
    on l.expense_gl_account_hk = a.gl_account_hk
where a.account_class <> 'Expense'
