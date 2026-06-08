{% macro safecast_decimal(column_name, precision=18, scale=4) %}
    /*
        Safely cast a raw Bronze VARCHAR value to DECIMAL.

        Purpose:
        - trims source strings
        - treats blank strings as NULL
        - removes common thousands separators
        - uses TRY_CAST so malformed values become NULL rather than failing the model
        - preserves exact decimal arithmetic for finance calculations

        Example:
            {{ safecast_decimal('amount_gbp') }} as amount_gbp

            {{ safecast_decimal('amount_gbp', 20, 6) }} as amount_gbp
    */
    try_cast(
        nullif(
            replace(trim(cast({{ column_name }} as varchar)), ',', ''),
            ''
        )
        as decimal({{ precision }}, {{ scale }})
    )
{% endmacro %}
