import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { StaleBanner } from '@/components/feedback/StaleBanner';
import { useMetrics } from '@/api/hooks';
import { STALE_THRESHOLD_MS } from '@/lib/constants';

export const AppShell: React.FC = () => {
  const { dataUpdatedAt, isError, refetch } = useMetrics();

  // Check if data is stale (> 2 minutes)
  const isStale = dataUpdatedAt > 0 && Date.now() - dataUpdatedAt > STALE_THRESHOLD_MS;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-page text-text-primary antialiased">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top Header */}
        <Header />

        {/* Global Stale Data / Offline Banner */}
        <StaleBanner
          isStale={isStale}
          isError={isError}
          lastUpdated={dataUpdatedAt || null}
          onRefresh={() => refetch()}
        />

        {/* Page Body */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
