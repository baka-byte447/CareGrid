/**
 * Sidebar.jsx — Navigation Sidebar
 *
 * Left-side navigation panel with links to all pages.
 * Uses NavLink from react-router-dom so the active route is highlighted.
 */

import { NavLink } from 'react-router-dom'
import { LayoutDashboard, BedDouble, Users, ClipboardList } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/wards',    icon: BedDouble,       label: 'Wards & Beds' },
  { to: '/patients', icon: Users,           label: 'Patient Queue' },
  { to: '/audit',    icon: ClipboardList,   label: 'Audit & Resources' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>CareGrid</h1>
        <span>Resource Allocation Platform</span>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-nav-label">Navigation</div>
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
          >
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        Backend: FastAPI + PostgreSQL<br />
        Algorithm: Rule-based baseline
      </div>
    </aside>
  )
}
