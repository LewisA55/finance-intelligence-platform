export type PageId =
  | 'command-center'
  | 'saas'
  | 'financial'
  | 'revenue'
  | 'working-capital'
  | 'control-tower'
  | 'validation';

export interface NavItem {
  id: PageId;
  label: string;
}

export const NAV: NavItem[] = [
  { id: 'command-center', label: 'CFO Command Center' },
  { id: 'saas', label: 'SaaS Performance' },
  { id: 'financial', label: 'Financial Performance' },
  { id: 'revenue', label: 'Revenue Recognition' },
  { id: 'working-capital', label: 'Working Capital' },
  { id: 'control-tower', label: 'Control Tower' },
  { id: 'validation', label: 'Data & Validation' },
];
