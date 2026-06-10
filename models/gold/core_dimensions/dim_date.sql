{{ config(
    materialized='table',
    schema='gold',
    tags=['gold', 'core_dimension', 'date']
) }}

with date_spine as (

    select
        cast(calendar_date as date) as date_day
    from generate_series(
        date '2022-01-01',
        date '2027-12-31',
        interval 1 day
    ) as t(calendar_date)

),

calendar_attributes as (

    select
        md5(strftime(date_day, '%Y-%m-%d')) as date_hk,
        cast(strftime(date_day, '%Y%m%d') as integer) as date_key,

        date_day,
        strftime(date_day, '%Y-%m-%d') as date_label,

        extract(year from date_day)::integer as calendar_year,
        extract(quarter from date_day)::integer as calendar_quarter_number,
        'Q' || extract(quarter from date_day)::varchar as calendar_quarter_label,

        extract(month from date_day)::integer as calendar_month_number,
        strftime(date_day, '%B') as calendar_month_name,
        strftime(date_day, '%b') as calendar_month_short_name,

        strftime(date_day, '%Y-%m') as calendar_year_month,
        cast(strftime(date_day, '%Y%m') as integer) as calendar_year_month_sort,

        cast(date_trunc('month', date_day) as date) as month_start_date,
        last_day(date_day) as month_end_date,

        cast(date_trunc('week', date_day) as date) as week_start_date,
        cast(date_trunc('week', date_day) + interval 6 day as date) as week_end_date,

        extract(day from date_day)::integer as day_of_month,
        cast(strftime(date_day, '%u') as integer) as day_of_week_number,
        strftime(date_day, '%A') as day_of_week_name,
        strftime(date_day, '%a') as day_of_week_short_name,

        case when cast(strftime(date_day, '%u') as integer) in (6, 7) then true else false end as is_weekend,
        case when date_day = cast(date_trunc('month', date_day) as date) then true else false end as is_month_start,
        case when date_day = last_day(date_day) then true else false end as is_month_end,
        case when date_day = cast(date_trunc('quarter', date_day) as date) then true else false end as is_quarter_start,
        case
            when date_day = cast(date_trunc('quarter', date_day) + interval 3 month - interval 1 day as date)
            then true else false
        end as is_quarter_end,
        case when date_day = cast(date_trunc('year', date_day) as date) then true else false end as is_calendar_year_start,
        case
            when date_day = cast(date_trunc('year', date_day) + interval 1 year - interval 1 day as date)
            then true else false
        end as is_calendar_year_end,

        case
            when extract(month from date_day) >= 4
            then extract(year from date_day)::integer + 1
            else extract(year from date_day)::integer
        end as fiscal_year,

        'FY' ||
        case
            when extract(month from date_day) >= 4
            then (extract(year from date_day)::integer + 1)::varchar
            else extract(year from date_day)::integer::varchar
        end as fiscal_year_label,

        (((extract(month from date_day)::integer + 8) % 12) + 1) as fiscal_month_number,

        floor(((((extract(month from date_day)::integer + 8) % 12) + 1) - 1) / 3)::integer + 1 as fiscal_quarter_number,

        'FQ' ||
        (floor(((((extract(month from date_day)::integer + 8) % 12) + 1) - 1) / 3)::integer + 1)::varchar
        as fiscal_quarter_label,

        'FY' ||
        case
            when extract(month from date_day) >= 4
            then (extract(year from date_day)::integer + 1)::varchar
            else extract(year from date_day)::integer::varchar
        end
        || '-M'
        || lpad(((((extract(month from date_day)::integer + 8) % 12) + 1))::varchar, 2, '0')
        as fiscal_year_month_label,

        (
            case
                when extract(month from date_day) >= 4
                then extract(year from date_day)::integer + 1
                else extract(year from date_day)::integer
            end * 100
        )
        + (((extract(month from date_day)::integer + 8) % 12) + 1)
        as fiscal_year_month_sort,

        case when extract(month from date_day) = 4 and extract(day from date_day) = 1 then true else false end as is_fiscal_year_start,
        case when extract(month from date_day) = 3 and extract(day from date_day) = 31 then true else false end as is_fiscal_year_end,

        false as is_unassigned

    from date_spine

),

unassigned_row as (

    select
        md5('UNASSIGNED_DATE') as date_hk,
        -1 as date_key,

        cast(null as date) as date_day,
        'Unassigned' as date_label,

        cast(null as integer) as calendar_year,
        cast(null as integer) as calendar_quarter_number,
        'Unassigned' as calendar_quarter_label,

        cast(null as integer) as calendar_month_number,
        'Unassigned' as calendar_month_name,
        'Unassigned' as calendar_month_short_name,

        'Unassigned' as calendar_year_month,
        -1 as calendar_year_month_sort,

        cast(null as date) as month_start_date,
        cast(null as date) as month_end_date,

        cast(null as date) as week_start_date,
        cast(null as date) as week_end_date,

        cast(null as integer) as day_of_month,
        cast(null as integer) as day_of_week_number,
        'Unassigned' as day_of_week_name,
        'Unassigned' as day_of_week_short_name,

        false as is_weekend,
        false as is_month_start,
        false as is_month_end,
        false as is_quarter_start,
        false as is_quarter_end,
        false as is_calendar_year_start,
        false as is_calendar_year_end,

        cast(null as integer) as fiscal_year,
        'Unassigned' as fiscal_year_label,
        cast(null as integer) as fiscal_month_number,
        cast(null as integer) as fiscal_quarter_number,
        'Unassigned' as fiscal_quarter_label,
        'Unassigned' as fiscal_year_month_label,
        -1 as fiscal_year_month_sort,

        false as is_fiscal_year_start,
        false as is_fiscal_year_end,

        true as is_unassigned

)

select *
from unassigned_row

union all

select *
from calendar_attributes
