/**
 * MetricCard.jsx — Reusable KPI stat card
 *
 * Props:
 *   label   - Card title (e.g. "Beds Available")
 *   value   - Primary large number/text
 *   sub     - Small secondary text below the value
 *   color   - CSS class variant: 'green' | 'red' | 'amber' | 'purple' | (default blue)
 *   icon    - Lucide icon component
 */

export default function MetricCard({ label, value, sub, color, icon: Icon }) {
  return (
    <div className={`metric-card ${color || ''}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? '—'}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {Icon && (
        <div className="metric-icon">
          <Icon size={18} />
        </div>
      )}
    </div>
  )
}
