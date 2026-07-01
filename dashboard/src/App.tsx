import { useEffect, useState } from 'react';
import { Layout } from './components/Layout';
import { NAV, type PageId } from './nav';
import { CfoCommandCenter } from './pages/CfoCommandCenter';
import { SaaSPerformance } from './pages/SaaSPerformance';
import { FinancialPerformance } from './pages/FinancialPerformance';
import { RevenueRecognition } from './pages/RevenueRecognition';
import { WorkingCapital } from './pages/WorkingCapital';
import { WorkforceCapacity } from './pages/WorkforceCapacity';
import { ControlTower } from './pages/ControlTower';
import { Validation } from './pages/Validation';

function pageFromHash(): PageId {
  const candidate = window.location.hash.replace(/^#\/?/, '');
  return NAV.some((item) => item.id === candidate)
    ? candidate as PageId
    : 'command-center';
}

export default function App() {
  const [page, setPage] = useState<PageId>(pageFromHash);

  useEffect(() => {
    const syncFromHash = () => setPage(pageFromHash());
    window.addEventListener('hashchange', syncFromHash);
    return () => window.removeEventListener('hashchange', syncFromHash);
  }, []);

  const navigate = (next: PageId) => {
    window.location.hash = `/${next}`;
    setPage(next);
    document.getElementById('main-content')?.focus();
  };

  return (
    <Layout current={page} onNavigate={navigate}>
      {page === 'command-center' && <CfoCommandCenter onNavigate={navigate} />}
      {page === 'saas' && <SaaSPerformance />}
      {page === 'financial' && <FinancialPerformance />}
      {page === 'revenue' && <RevenueRecognition />}
      {page === 'working-capital' && <WorkingCapital />}
      {page === 'workforce' && <WorkforceCapacity />}
      {page === 'control-tower' && <ControlTower />}
      {page === 'validation' && <Validation />}
    </Layout>
  );
}
