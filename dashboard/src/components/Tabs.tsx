import { NAV, NAV_SECTIONS, type PageId } from '../nav';

interface TabsProps {
  current: PageId;
  onNavigate: (page: PageId) => void;
}

export function Tabs({ current, onNavigate }: TabsProps) {
  return (
    <nav className="tabs" aria-label="Dashboard pages">
      {NAV_SECTIONS.map((section) => (
        <div key={section} className="tab-group">
          <span className="tab-group-label" aria-hidden="true">{section}</span>
          <div className="tab-group-items">
            {NAV.filter((item) => item.section === section).map((item) => (
              <button
                key={item.id}
                type="button"
                className={`tab ${item.id === current ? 'active' : ''}${item.section === 'Modelling' ? ' tab-modelling' : ''}`}
                onClick={() => onNavigate(item.id)}
                aria-current={item.id === current ? 'page' : undefined}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}
