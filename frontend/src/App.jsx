/**
 * App.jsx — Application Shell
 *
 * Sets up the two-panel layout:
 *   ┌─────────────────────────────────────┐
 *   │  Sidebar  │  Topbar + Page Body     │
 *   │  (nav)    │  (Routes rendered here) │
 *   └─────────────────────────────────────┘
 *
 * Routes:
 *   /            → DashboardPage  (hospital KPI overview)
 *   /wards       → WardsPage      (full bed grid by ward)
 *   /patients    → PatientsPage   (patient queue + allocation workflow)
 *   /audit       → AuditPage      (audit log + staff + equipment)
 */

import { Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import WardsPage from './pages/WardsPage.jsx'
import PatientsPage from './pages/PatientsPage.jsx'
import AuditPage from './pages/AuditPage.jsx'

const PAGE_TITLES = {
  '/':         { title: 'Command Center',     sub: 'Real-time hospital resource overview' },
  '/wards':    { title: 'Ward & Bed Status',  sub: 'All 100 beds across ICU, Step-Down, and Ward units' },
  '/patients': { title: 'Patient Queue',      sub: 'Triage queue and allocation workflow' },
  '/audit':    { title: 'Audit & Resources',  sub: 'Allocation history, staff roster, and equipment status' },
}

export default function App() {
  const { pathname } = useLocation()
  const { title, sub } = PAGE_TITLES[pathname] || PAGE_TITLES['/']

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="main-content">
        {/* ── Top Bar ── */}
        <div className="topbar">
          <div>
            <div className="topbar-title">{title}</div>
            <div className="topbar-subtitle">{sub}</div>
          </div>
          <div className="topbar-right">
            <span className="topbar-badge">🏥 CareGrid RL</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {new Date().toLocaleDateString('en-IN', { weekday:'short', month:'short', day:'numeric' })}
            </span>
          </div>
        </div>

        {/* ── Page Content ── */}
        <div className="page-body">
          <Routes>
            <Route path="/"         element={<DashboardPage />} />
            <Route path="/wards"    element={<WardsPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/audit"    element={<AuditPage />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
