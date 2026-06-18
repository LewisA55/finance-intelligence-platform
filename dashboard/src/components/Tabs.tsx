import { NAV, type PageId } from '../nav';

interface TabsProps {
  current: PageId;
  onNavigate: (page: PageId) => void;
}

export function Tabs({ current, onNavigate }: TabsProps) {
  return (
    <nav className="tabs" aria-label="Dashboard pages">
      {NAV.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`tab ${item.id === current ? 'active' : ''}`}
          onClick={() => onNavigate(item.id)}
          aria-current={item.id === current ? 'page' : undefined}
        >
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
