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
    <div className="relative flex h-screen w-screen overflow-hidden bg-bg-page text-text-primary antialiased">
      {/* Cosmic Space-Navy & Cyan-Violet Aurora Waves */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
      >
        <div className="absolute -top-36 -left-24 w-[580px] h-[580px] rounded-full bg-sky-500/15 dark:bg-sky-500/20 blur-3xl animate-float-slow" />
        <div className="absolute top-1/4 -right-28 w-[540px] h-[540px] rounded-full bg-purple-600/15 dark:bg-purple-600/20 blur-3xl animate-float-rev" />
        <div className="absolute -bottom-36 left-1/3 w-[480px] h-[480px] rounded-full bg-indigo-500/12 dark:bg-cyan-500/12 blur-3xl animate-float-slow" />
      </div>

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

        {/* Page Body */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
