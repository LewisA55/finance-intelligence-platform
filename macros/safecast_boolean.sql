{% macro safecast_boolean(column_name) %}
    /*
        Safely cast a raw Bronze VARCHAR value to BOOLEAN.

        Purpose:
        - trims and lowercases source strings
        - standardises common true / false encodings
        - treats blank strings and nulls as NULL
        - avoids accidental truthiness from arbitrary non-empty text

        True values:
            true, t, 1, yes, y

        False values:
            false, f, 0, no, n

        Example:
            {{ safecast_boolean('is_active_flag') }} as is_active
    */
    case
        when {{ column_name }} is null then null
        when trim(cast({{ column_name }} as varchar)) = '' then null
        when lower(trim(cast({{ column_name }} as varchar))) in ('true', 't', '1', 'yes', 'y') then true
        when lower(trim(cast({{ column_name }} as varchar))) in ('false', 'f', '0', 'no', 'n') then false
        else null
    end
{% endmacro %}
