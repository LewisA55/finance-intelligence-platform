export type PageId =
  | 'command-center'
  | 'saas'
  | 'financial'
  | 'revenue'
  | 'working-capital'
  | 'workforce'
  | 'model'
  | 'control-tower'
  | 'validation';

export type SectionId = 'Overview' | 'Performance' | 'Operations' | 'Modelling' | 'Governance';

export interface NavItem {
  id: PageId;
  label: string;
  section: SectionId;
}

export const NAV: NavItem[] = [
  { id: 'command-center', label: 'Command Center', section: 'Overview' },
  { id: 'saas', label: 'SaaS', section: 'Performance' },
  { id: 'financial', label: 'Financial', section: 'Performance' },
  { id: 'revenue', label: 'Revenue Quality', section: 'Performance' },
  { id: 'working-capital', label: 'Working Capital', section: 'Operations' },
  { id: 'workforce', label: 'Workforce', section: 'Operations' },
  { id: 'model', label: 'Forecast & Valuation', section: 'Modelling' },
  { id: 'control-tower', label: 'Control Tower', section: 'Governance' },
  { id: 'validation', label: 'Data & Validation', section: 'Governance' },
];

export const NAV_SECTIONS: SectionId[] = ['Overview', 'Performance', 'Operations', 'Modelling', 'Governance'];
