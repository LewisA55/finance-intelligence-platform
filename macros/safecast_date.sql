{% macro safecast_date(column_name) -%}
cast(
    try_strptime(
        nullif(trim(cast({{ column_name }} as varchar)), ''),
        '%Y-%m-%d'
    )
    as date
)
{%- endmacro %}