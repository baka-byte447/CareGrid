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

export const Sidebar: React.FC = () => {
  const navItems = [
    { label: 'Command Centre', path: '/', icon: LayoutDashboard },
    { label: 'Admission Queue', path: '/queue', icon: Users },
    { label: 'Bed Management', path: '/beds', icon: BedDouble },
    { label: 'Staff Roster', path: '/staff', icon: UserCheck },
    { label: 'Equipment', path: '/equipment', icon: Stethoscope },
    { label: 'Surge Planner', path: '/surge', icon: Zap },
    { label: 'Clinical Reports', path: '/reports', icon: BarChart3 },
    { label: 'Audit Log', path: '/audit', icon: ScrollText },
    { label: 'Hospital Admin', path: '/admin', icon: Settings },
  ];

  return (
    <aside className="w-60 bg-[#0a192f] text-slate-200 flex flex-col flex-shrink-0 border-r border-slate-800 select-none">
      {/* Brand Logo & Name */}
      <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-brand-primary flex items-center justify-center text-white shadow-md">
          <Activity className="w-5 h-5 text-sky-200" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-white leading-none">
            CareGrid
          </h1>
          <span className="text-[11px] font-medium text-sky-400/80 tracking-wide block mt-1">
            HMIS Platform
          </span>
        </div>
      </div>

      {/* Navigation links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Clinical Operations
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-sky-600/90 text-white shadow-sm font-semibold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800/80 text-[11px] text-slate-400">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-semibold text-slate-300">RL Engine Active</span>
        </div>
        <p className="text-[10px] text-slate-500">v1.0.0 &bull; St. Jude Central</p>
      </div>
    </aside>
  );
};
