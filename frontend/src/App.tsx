
import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { CommandCentrePage } from '@/pages/CommandCentrePage'
import { AdmissionQueuePage } from '@/pages/AdmissionQueuePage'
import { BedManagementPage } from '@/pages/BedManagementPage'
import { StaffPage } from '@/pages/StaffPage'
import { EquipmentPage } from '@/pages/EquipmentPage'
import { SurgePlannerPage } from '@/pages/SurgePlannerPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { AdminPage } from '@/pages/AdminPage'
import { LoginPage } from '@/pages/LoginPage'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { useAuth } from './auth/AuthContext'

function LoginRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center">Checking authentication...</div>
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <LoginPage />
}

export const App: React.FC = () => {
  return (
    <Routes>
      {/* Public login page */}
      <Route path="/login" element={<LoginRoute />} />

      {/* Protected clinical application */}
      <Route element={<ProtectedRoute />}>
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
        </Route>
      </Route>

      {/* Unknown routes */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
