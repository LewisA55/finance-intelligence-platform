{% macro safecast_boolean(column_name) -%}
case
    when {{ column_name }} is null then null
    when trim(cast({{ column_name }} as varchar)) = '' then null
    when lower(trim(cast({{ column_name }} as varchar))) in ('true', 't', '1', 'yes', 'y') then true
    when lower(trim(cast({{ column_name }} as varchar))) in ('false', 'f', '0', 'no', 'n') then false
    else null
end
{%- endmacro %}