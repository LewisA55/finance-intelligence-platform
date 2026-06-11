/*
    Test: mart_o2c_customer_collections exposure arithmetic.

    Failure condition:
    Billed amount less allocated amount does not equal net unallocated exposure.
*/

select
    o2c_customer_collections_hk,
    customer_id,
    invoice_month,
    billed_amount_gbp,
    allocated_amount_gbp,
    net_unallocated_invoice_exposure_gbp,
    round(billed_amount_gbp - allocated_amount_gbp, 2) as expected_net_unallocated_invoice_exposure_gbp
from {{ ref('mart_o2c_customer_collections') }}
where abs(
    round(billed_amount_gbp - allocated_amount_gbp, 2)
    - net_unallocated_invoice_exposure_gbp
) > 0.01
