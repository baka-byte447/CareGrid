import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  BedDouble,
  UserCheck,
  Stethoscope,
  Zap,
  BarChart3,
  ScrollText,
  Settings,
  Activity,
} from 'lucide-react';
import { useAuth } from '@/auth/AuthContext';
import type { UserRole } from '@/auth/types';

interface NavItem {
  label: string;
  path: string;
  icon: React.ElementType;
  allowedRoles: UserRole[];
}

const navItems: NavItem[] = [
  {
    label: 'Command Centre',
    path: '/',
    icon: LayoutDashboard,
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Admission Queue',
    path: '/queue',
    icon: Users,
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Bed Management',
    path: '/beds',
    icon: BedDouble,
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Staff Roster',
    path: '/staff',
    icon: UserCheck,
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Equipment',
    path: '/equipment',
    icon: Stethoscope,
    allowedRoles: ['admin', 'nurse', 'operator'],
  },
  {
    label: 'Surge Planner',
    path: '/surge',
    icon: Zap,
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Clinical Reports',
    path: '/reports',
    icon: BarChart3,
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Audit Log',
    path: '/audit',
    icon: ScrollText,
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Hospital Admin',
    path: '/admin',
    icon: Settings,
    allowedRoles: ['admin'],
  },
];

export const Sidebar: React.FC = () => {
  const { user } = useAuth();

  const visibleNavItems = navItems.filter((item) =>
    user && item.allowedRoles.includes(user.role)
  );

  return (
    <aside className="relative w-64 bg-bg-sidebar backdrop-blur-xl text-text-primary flex flex-col flex-shrink-0 border-r border-border-light select-none overflow-hidden">
      {/* Subtle Cosmic Sidebar Glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-20 -left-20 w-56 h-56 rounded-full bg-sky-500/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-24 -left-16 w-56 h-56 rounded-full bg-purple-600/20 blur-3xl"
      />

      {/* Brand Logo & Name */}
      <div className="relative px-5 py-5 flex items-center gap-3 border-b border-border-light/60">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-white shadow-glow transition-transform duration-300 hover:scale-105"
          style={{ background: 'var(--brand-gradient)' }}
        >
          <Activity className="w-5 h-5 text-white" />
        </div>

        <div>
          <h1 className="text-base font-bold tracking-tight text-text-primary leading-none">
            CareGrid
          </h1>
          <span className="text-[11px] font-medium text-text-muted tracking-wide block mt-1">
            Hospital Management
          </span>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="relative flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
        {visibleNavItems.map((item, idx) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              style={{ animationDelay: `${idx * 30}ms` }}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 animate-fade-in ${
                  isActive
                    ? 'text-white font-semibold shadow-glow'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-sidebar-hover hover:translate-x-1'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-0 rounded-xl -z-10"
                      style={{ background: 'var(--brand-gradient-pill)' }}
                    />
                  )}
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Hospital Online Telemetry Card (Reference Inspired) */}
      <div className="relative p-3.5 m-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 backdrop-blur-md shadow-card">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 pulse-ring" />
            <span className="text-xs font-bold text-emerald-400">
              Hospital Online
            </span>
          </div>
          <svg className="w-10 h-4 text-emerald-400" viewBox="0 0 40 16" fill="none">
            <path
              d="M0 8 H8 L12 2 L16 14 L20 4 L24 12 L28 8 H40"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <p className="text-[10px] text-text-muted font-mono">
          RL Engine Active &bull; St. Jude Central
        </p>
      </div>
    </aside>
  );
};