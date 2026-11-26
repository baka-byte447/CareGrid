import React, { useState } from 'react';
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
  PanelLeftClose,
  PanelLeftOpen,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '@/auth/AuthContext';
import { usePatients } from '@/api/hooks';
import { Tooltip } from '@/components/ui/Tooltip';
import type { UserRole } from '@/auth/types';

interface NavItem {
  label: string;
  path: string;
  icon: React.ElementType;
  section: 'operations' | 'resources' | 'governance';
  allowedRoles: UserRole[];
}

const navItems: NavItem[] = [
  {
    label: 'Command Centre',
    path: '/',
    icon: LayoutDashboard,
    section: 'operations',
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Admission Queue',
    path: '/queue',
    icon: Users,
    section: 'operations',
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Bed Management',
    path: '/beds',
    icon: BedDouble,
    section: 'resources',
    allowedRoles: ['admin', 'doctor', 'nurse', 'operator'],
  },
  {
    label: 'Staff Roster',
    path: '/staff',
    icon: UserCheck,
    section: 'resources',
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Equipment',
    path: '/equipment',
    icon: Stethoscope,
    section: 'resources',
    allowedRoles: ['admin', 'nurse', 'operator'],
  },
  {
    label: 'Surge Planner',
    path: '/surge',
    icon: Zap,
    section: 'governance',
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Clinical Reports',
    path: '/reports',
    icon: BarChart3,
    section: 'governance',
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Audit Log',
    path: '/audit',
    icon: ScrollText,
    section: 'governance',
    allowedRoles: ['admin', 'operator'],
  },
  {
    label: 'Hospital Admin',
    path: '/admin',
    icon: Settings,
    section: 'governance',
    allowedRoles: ['admin'],
  },
];

const SECTIONS: { key: NavItem['section']; label: string }[] = [
  { key: 'operations', label: 'Clinical Flow' },
  { key: 'resources', label: 'Capacity & Assets' },
  { key: 'governance', label: 'Analytics & Admin' },
];

export const Sidebar: React.FC = () => {
  const { user } = useAuth();
  const { data: patients } = usePatients();
  const [collapsed, setCollapsed] = useState(false);

  const waitingCount = (patients ?? []).filter(
    (p) => p.current_status === 'WAITING'
  ).length;

  const visibleNavItems = navItems.filter(
    (item) => user && item.allowedRoles.includes(user.role)
  );

  return (
    <aside
      className={`relative bg-bg-sidebar text-text-primary flex flex-col flex-shrink-0 border-r border-border-light select-none transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        collapsed ? 'w-[76px]' : 'w-64'
      }`}
    >
      {/* Brand Header + Collapse Toggle */}
      <div
        className={`px-4 py-4 flex items-center border-b border-border-light ${
          collapsed ? 'justify-center' : 'justify-between'
        }`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-brand-primary flex items-center justify-center text-white dark:text-zinc-950 shadow-xs flex-shrink-0 transition-transform duration-200 hover:scale-105">
            <Activity className="w-5 h-5" />
          </div>

          {!collapsed && (
            <div className="min-w-0 animate-fade-in">
              <h1 className="text-sm font-bold tracking-tight text-text-primary leading-none truncate">
                CareGrid
              </h1>
              <span className="text-[11px] font-medium text-text-muted block mt-1 truncate">
                Clinical Operations
              </span>
            </div>
          )}
        </div>

        {!collapsed && (
          <Tooltip content="Collapse sidebar">
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-sidebar-hover transition-colors"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </Tooltip>
        )}
      </div>

      {collapsed && (
        <div className="flex justify-center pt-3">
          <Tooltip content="Expand sidebar">
            <button
              type="button"
              onClick={() => setCollapsed(false)}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-bg-sidebar-hover transition-colors"
              aria-label="Expand sidebar"
            >
              <PanelLeftOpen className="w-4 h-4" />
            </button>
          </Tooltip>
        </div>
      )}

      {/* Grouped Navigation Links */}
      <nav className="flex-1 px-2.5 py-3 space-y-4 overflow-y-auto overflow-x-hidden">
        {SECTIONS.map((section) => {
          const items = visibleNavItems.filter(
            (item) => item.section === section.key
          );
          if (items.length === 0) return null;

          return (
            <div key={section.key} className="space-y-1">
              {!collapsed ? (
                <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted/80">
                  {section.label}
                </div>
              ) : (
                <div className="mx-3 my-1.5 h-px bg-border-light" />
              )}

              {items.map((item, idx) => {
                const Icon = item.icon;
                const showWaitingBadge = item.path === '/queue' && waitingCount > 0;

                const link = (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    style={{ animationDelay: `${idx * 25}ms` }}
                    className={({ isActive }) =>
                      `group relative flex items-center ${
                        collapsed ? 'justify-center px-2' : 'justify-between px-3'
                      } py-2 rounded-xl text-xs font-medium transition-all duration-200 animate-fade-in ${
                        isActive
                          ? 'bg-bg-sidebar-active text-text-primary dark:text-white font-semibold border border-border-medium shadow-xs'
                          : 'text-text-secondary hover:text-text-primary hover:bg-bg-sidebar-hover hover:translate-x-0.5'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span
                            aria-hidden="true"
                            className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-brand-primary animate-tab-pop"
                          />
                        )}

                        <div className="flex items-center gap-3 min-w-0">
                          <Icon
                            className={`w-4 h-4 flex-shrink-0 transition-transform duration-200 group-hover:scale-110 ${
                              isActive ? 'text-brand-primary' : ''
                            }`}
                          />
                          {!collapsed && (
                            <span className="truncate">{item.label}</span>
                          )}
                        </div>

                        {!collapsed && (
                          <div className="flex items-center gap-1.5">
                            {showWaitingBadge && (
                              <span className="px-1.5 py-0.5 rounded-full bg-brand-primary/15 text-brand-primary font-mono text-[10px] font-bold">
                                {waitingCount}
                              </span>
                            )}
                            <ChevronRight
                              className={`w-3.5 h-3.5 text-text-muted transition-all duration-200 ${
                                isActive
                                  ? 'opacity-80 translate-x-0 text-brand-primary'
                                  : 'opacity-0 -translate-x-1 group-hover:opacity-70 group-hover:translate-x-0'
                              }`}
                            />
                          </div>
                        )}

                        {collapsed && showWaitingBadge && (
                          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-brand-primary" />
                        )}
                      </>
                    )}
                  </NavLink>
                );

                return collapsed ? (
                  <Tooltip key={item.path} content={item.label}>
                    <div>{link}</div>
                  </Tooltip>
                ) : (
                  link
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Minimal System Status Footer */}
      <div className="p-2.5 m-2.5 rounded-xl border border-border-light bg-bg-surface/60 transition-all duration-200">
        {collapsed ? (
          <div className="flex justify-center py-1" title="System Online • Hospital Operations">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          </div>
        ) : (
          <div className="px-1">
            <div className="flex items-center justify-between mb-0.5">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-semibold text-text-primary">
                  System Online
                </span>
              </div>
              <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-bg-surface-hover border border-border-light">
                RL
              </span>
            </div>
            <p className="text-[10px] text-text-muted font-mono">
              Hospital Operations
            </p>
          </div>
        )}
      </div>
    </aside>
  );
};