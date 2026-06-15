import type { ReactNode } from 'react';

interface TopBarProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  /** Right-aligned controls (scope pill, month selector, etc.). */
  actions?: ReactNode;
}

export function TopBar({ eyebrow, title, subtitle, actions }: TopBarProps) {
  return (
    <header className="topbar">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="topbar-actions">{actions}</div>}
    </header>
  );
}
