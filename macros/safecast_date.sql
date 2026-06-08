{% macro safecast_date(column_name) %}
    /*
        Safely cast a raw Bronze VARCHAR value to DATE using deterministic ISO parsing.

        Purpose:
        - trims source strings
        - treats blank strings as NULL
        - parses only YYYY-MM-DD format
        - uses TRY_STRPTIME so malformed dates become NULL rather than failing the model
        - avoids server locale ambiguity

        Example:
            {{ safecast_date('period_start_date') }} as period_start_date
    */
    cast(
        try_strptime(
            nullif(trim(cast({{ column_name }} as varchar)), ''),
            '%Y-%m-%d'
        )
        as date
    )
{% endmacro %}
