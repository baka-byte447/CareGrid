import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { CommandCentrePage } from '@/pages/CommandCentrePage';
import { AdmissionQueuePage } from '@/pages/AdmissionQueuePage';
import { BedManagementPage } from '@/pages/BedManagementPage';
import { StaffPage } from '@/pages/StaffPage';
import { EquipmentPage } from '@/pages/EquipmentPage';
import { SurgePlannerPage } from '@/pages/SurgePlannerPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { AuditLogPage } from '@/pages/AuditLogPage';
import { AdminPage } from '@/pages/AdminPage';
import { LoginPage } from '@/pages/LoginPage';

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Standalone Login Route */}
      <Route path="/login" element={<LoginPage />} />

      {/* Main Clinical Layout */}
      <Route path="/" element={<AppShell />}>
        <Route index element={<CommandCentrePage />} />
        <Route path="command-centre" element={<Navigate to="/" replace />} />
        <Route path="queue" element={<AdmissionQueuePage />} />
        <Route path="beds" element={<BedManagementPage />} />
        <Route path="staff" element={<StaffPage />} />
        <Route path="equipment" element={<EquipmentPage />} />
        <Route path="surge" element={<SurgePlannerPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="audit" element={<AuditLogPage />} />
        <Route path="admin" element={<AdminPage />} />
        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};

export default App;
