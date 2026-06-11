/*
    Test: duplicate vendor invoice candidates are defect-flagged.

    Failure condition:
    Two or more vendor invoices share the same vendor_id, invoice_number,
    currency_code and rounded total_gbp, but at least one candidate is not
    flagged as DUPLICATE_VENDOR_INVOICE.

    This preserves intentional duplicate AP defects while ensuring the control
    population is explicitly labelled.
*/

with duplicate_candidates as (

    select
        vendor_id,
        invoice_number,
        currency_code,
        round(total_gbp, 2) as total_gbp_rounded,
        count(*) as invoice_count,
        sum(case when is_duplicate_vendor_invoice then 1 else 0 end) as duplicate_flag_count
    from {{ ref('fct_vendor_invoices') }}
    group by
        vendor_id,
        invoice_number,
        currency_code,
        round(total_gbp, 2)
    having count(*) > 1

)

select *
from duplicate_candidates
where duplicate_flag_count <> invoice_count
