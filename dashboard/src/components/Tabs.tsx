import { NAV, type PageId } from '../nav';

interface TabsProps {
  current: PageId;
  onNavigate: (page: PageId) => void;
}

const STATUS_LABEL: Record<string, string> = { preview: 'PREVIEW', soon: 'SOON' };

export function Tabs({ current, onNavigate }: TabsProps) {
  return (
    <nav className="tabs">
      {NAV.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`tab ${item.id === current ? 'active' : ''}`}
          onClick={() => onNavigate(item.id)}
        >
          <span>{item.label}</span>
          {item.status !== 'live' && <span className="soon">{STATUS_LABEL[item.status]}</span>}
        </button>
      ))}
    </nav>
  );
}
