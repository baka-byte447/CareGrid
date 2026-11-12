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
import { UserRole } from './auth/types'

function LoginRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        Checking authentication...
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <LoginPage />
}

const ALL_ROLES: UserRole[] = [
  'admin',
  'doctor',
  'nurse',
  'operator',
]

const ADMIN_OPERATOR: UserRole[] = ['admin', 'operator']
const ADMIN_NURSE_OPERATOR: UserRole[] = [
  'admin',
  'nurse',
  'operator',
]
const ADMIN_ONLY: UserRole[] = ['admin']

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<AppShell />}>
          <Route index element={<CommandCentrePage />} />

          <Route
            path="command-centre"
            element={<Navigate to="/" replace />}
          />

          <Route element={<ProtectedRoute allowedRoles={ALL_ROLES} />}>
            <Route path="queue" element={<AdmissionQueuePage />} />
            <Route path="beds" element={<BedManagementPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={ADMIN_OPERATOR} />}>
            <Route path="staff" element={<StaffPage />} />
            <Route path="surge" element={<SurgePlannerPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="audit" element={<AuditLogPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={ADMIN_NURSE_OPERATOR} />}>
            <Route path="equipment" element={<EquipmentPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={ADMIN_ONLY} />}>
            <Route path="admin" element={<AdminPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
