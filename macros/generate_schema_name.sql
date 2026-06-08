{% macro generate_schema_name(custom_schema_name, node) -%}
    {#
        Project Atlas schema naming override.

        dbt's default behaviour appends custom schemas to the target schema,
        producing names such as main_silver or dev_silver.

        For Project Atlas, custom schemas are treated as absolute warehouse
        schemas. If a model configures schema='silver', it must materialize in
        the silver schema exactly.

        Examples:
            schema='bronze' -> bronze
            schema='silver' -> silver
            schema='gold'   -> gold
            schema='marts'  -> marts

        If no custom schema is supplied, fall back to the target schema from
        profiles.yml.
    #}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
