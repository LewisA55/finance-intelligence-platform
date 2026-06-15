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
      <PackHeader />
      <Tabs current={current} onNavigate={onNavigate} />
      <main className="main">{children}</main>
      <GovernanceFooter />
    </div>
  );
}
