/*
Purpose:
    Ensure the HRIS headcount snapshot has only one row per employee per
    snapshot month.

Grain:
    One failing row per employee_id / snapshot_month combination with more than
    one record.

Expected result:
    Zero rows.
*/

select
    employee_id,
    snapshot_month,
    count(*) as row_count
from {{ ref('stg_hris__hr_headcount_snapshot') }}
group by
    employee_id,
    snapshot_month
having count(*) > 1