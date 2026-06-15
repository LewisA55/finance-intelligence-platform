import type { ReactNode } from 'react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  /** Optional right-aligned slot (e.g. a legend note or source tag). */
  aside?: ReactNode;
  children: ReactNode;
}

export function ChartCard({ title, subtitle, aside, children }: ChartCardProps) {
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p className="panel-sub">{subtitle}</p>}
        </div>
        {aside && <div className="panel-aside">{aside}</div>}
      </div>
      {children}
    </div>
  );
}
