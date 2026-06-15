export type PageId =
  | 'command-center'
  | 'saas'
  | 'financial'
  | 'working-capital'
  | 'control-tower'
  | 'validation';

export type PageStatus = 'live' | 'preview' | 'soon';

export interface NavItem {
  id: PageId;
  label: string;
  status: PageStatus;
}

export const NAV: NavItem[] = [
  { id: 'command-center', label: 'CFO Command Center', status: 'live' },
  { id: 'saas', label: 'SaaS Performance', status: 'preview' },
  { id: 'financial', label: 'Financial Performance', status: 'live' },
  { id: 'working-capital', label: 'Working Capital', status: 'soon' },
  { id: 'control-tower', label: 'Control Tower', status: 'soon' },
  { id: 'validation', label: 'Data & Validation', status: 'live' },
];
