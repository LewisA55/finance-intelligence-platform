{% macro safecast_decimal(column_name, precision=18, scale=4) -%}
try_cast(
    nullif(
        replace(trim(cast({{ column_name }} as varchar)), ',', ''),
        ''
    )
    as decimal({{ precision }}, {{ scale }})
)
{%- endmacro %}