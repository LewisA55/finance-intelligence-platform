import type { ReactNode } from 'react';
import { PackHeader } from './PackHeader';
import { Tabs } from './Tabs';
import { GovernanceFooter } from './GovernanceFooter';
import type { PageId } from '../nav';

interface LayoutProps {
  current: PageId;
  onNavigate: (page: PageId) => void;
  children: ReactNode;
}

export function Layout({ current, onNavigate, children }: LayoutProps) {
  return (
    <div className="doc">
      <a className="skip-link" href="#main-content">Skip to dashboard content</a>
      <PackHeader />
      <Tabs current={current} onNavigate={onNavigate} />
      <main id="main-content" className="main" tabIndex={-1}>{children}</main>
      <GovernanceFooter current={current} />
    </div>
  );
}
