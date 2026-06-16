import { useState } from 'react';
import { Layout } from './components/Layout';
import type { PageId } from './nav';
import { CfoCommandCenter } from './pages/CfoCommandCenter';
import { SaaSPerformance } from './pages/SaaSPerformance';
import { FinancialPerformance } from './pages/FinancialPerformance';
import { RevenueRecognition } from './pages/RevenueRecognition';
import { WorkingCapital } from './pages/WorkingCapital';
import { ControlTower } from './pages/ControlTower';
import { Validation } from './pages/Validation';

export default function App() {
  const [page, setPage] = useState<PageId>('command-center');

  return (
    <Layout current={page} onNavigate={setPage}>
      {page === 'command-center' && <CfoCommandCenter onNavigate={setPage} />}
      {page === 'saas' && <SaaSPerformance />}
      {page === 'financial' && <FinancialPerformance />}
      {page === 'revenue' && <RevenueRecognition />}
      {page === 'working-capital' && <WorkingCapital />}
      {page === 'control-tower' && <ControlTower />}
      {page === 'validation' && <Validation />}
    </Layout>
  );
}
