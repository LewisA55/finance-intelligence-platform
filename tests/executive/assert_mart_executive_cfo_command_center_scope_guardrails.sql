select *
from {{ ref('mart_executive_cfo_command_center') }}
where (reporting_scope = 'Company Total' and (business_unit_code <> 'COMPANY_TOTAL' or region_hk <> md5('UNASSIGNED')))
   or (reporting_scope = 'Region Total' and business_unit_code <> 'REGION_TOTAL')
   or (reporting_scope = 'Business Unit Total' and (business_unit_code in ('COMPANY_TOTAL', 'REGION_TOTAL') or region_hk <> md5('UNASSIGNED')))
