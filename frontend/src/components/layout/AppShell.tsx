import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { StaleBanner } from '@/components/feedback/StaleBanner';
import { useMetrics } from '@/api/hooks';
import { STALE_THRESHOLD_MS } from '@/lib/constants';

export const AppShell: React.FC = () => {
  const location = useLocation();
  const { dataUpdatedAt, isError, refetch } = useMetrics();

  // Check if data is stale (> 2 minutes)
  const isStale = dataUpdatedAt > 0 && Date.now() - dataUpdatedAt > STALE_THRESHOLD_MS;

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-bg-page text-text-primary antialiased">
      {/* Subtle Top Architectural Vignette */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 h-72 z-0 bg-gradient-to-b from-emerald-500/[0.04] dark:from-emerald-500/[0.05] to-transparent"
      />

      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="relative z-10 flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top Header */}
        <Header />

        {/* Global Stale Data / Offline Banner */}
        <StaleBanner
          isStale={isStale}
          isError={isError}
          lastUpdated={dataUpdatedAt || null}
          onRefresh={() => refetch()}
        />

        {/* Page Body with Tab/Route Transition Animation */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div key={location.pathname} className="animate-page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
