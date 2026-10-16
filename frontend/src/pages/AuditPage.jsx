/**
 * AuditPage.jsx — Audit Log, Staff Roster, and Equipment Status
 *
 * Data sources:
 *   GET /audit     → Allocation approval history (last 100 records)
 *   GET /staff     → Staff roster with workload percentages
 *   GET /equipment → Equipment availability by type
 *
 * Sections:
 *   1. Audit Log table — every approved allocation with timestamp
 *   2. Staff Workload panel — nurses and doctors with workload bars
 *   3. Equipment Status panel — Ventilators, Telemetry, Diagnostics
 */

import { useEffect, useState } from 'react'
import { fetchAuditLogs, fetchStaff, fetchEquipment } from '../services/api.js'
import { Wind, Activity, FlaskConical, RefreshCw } from 'lucide-react'

const EQUIP_ICONS = {
  VENTILATOR: Wind,
  TELEMETRY:  Activity,
  DIAGNOSTIC: FlaskConical,
}
const EQUIP_COLORS = {
  AVAILABLE:   'var(--status-available)',
  IN_USE:      'var(--status-occupied)',
  MAINTENANCE: 'var(--status-cleaning)',
}

export default function AuditPage() {
  const [audit, setAudit]       = useState([])
  const [staff, setStaff]       = useState([])
  const [equipment, setEquip]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  async function load() {
    try {
      setError(null)
      const [a, s, e] = await Promise.all([
        fetchAuditLogs(),
        fetchStaff(),
        fetchEquipment(),
      ])
      setAudit(a.audit || [])
      setStaff(s.staff || [])
      setEquip(e.equipment || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [])

  if (loading) return <div className="loading-state"><div className="spinner" />Loading resources…</div>
  if (error)   return <div className="error-box">{error}</div>

  // ── Equipment grouped by type ────────────────────────────────────────────────
  const equipByType = equipment.reduce((acc, e) => {
    if (!acc[e.type]) acc[e.type] = []
    acc[e.type].push(e)
    return acc
  }, {})

  // ── Staff grouped by role ──────────────────────────────────────────────────
  const sortedStaff = [...staff].sort((a, b) => b.workload - a.workload)

  return (
    <div style={{ display:'flex', flexDirection:'column', gap: 20 }}>

      {/* ── Refresh ── */}
      <div style={{ display:'flex', justifyContent:'flex-end' }}>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <RefreshCw size={13} /> Refresh All
        </button>
      </div>

      {/* ── Audit Log ── */}
      <div>
        <div className="section-header">
          <div>
            <div className="section-title">Allocation Audit Log</div>
            <div className="section-sub">Last {audit.length} approved allocations — ordered by timestamp</div>
          </div>
        </div>
        <div className="card" style={{ padding: 0, overflow:'hidden' }}>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Patient ID</th>
                  <th>Bed ID</th>
                  <th>Action</th>
                  <th>Algorithm</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {audit.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding: 32 }}>
                      No allocation records yet. Approve an allocation in the Patient Queue to see it here.
                    </td>
                  </tr>
                )}
                {audit.map((row, i) => (
                  <tr key={i}>
                    <td style={{ color:'var(--text-muted)', fontSize: 11 }}>{i + 1}</td>
                    <td style={{ fontWeight:600, fontFamily:'monospace', fontSize:13 }}>{row.patient_id}</td>
                    <td style={{ fontFamily:'monospace', fontSize:13 }}>{row.bed_id}</td>
                    <td>
                      <span className="badge badge-admitted">{row.action}</span>
                    </td>
                    <td style={{ fontSize:12, color:'var(--text-muted)' }}>{row.algorithm}</td>
                    <td style={{ fontSize:12, color:'var(--text-muted)' }}>
                      {new Date(row.timestamp).toLocaleString('en-IN', {
                        month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit'
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Equipment Status ── */}
      <div>
        <div className="section-header">
          <div>
            <div className="section-title">Equipment Status</div>
            <div className="section-sub">Ventilators, Telemetry units, Diagnostic devices</div>
          </div>
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {Object.entries(equipByType).map(([type, items]) => {
            const Icon = EQUIP_ICONS[type] || Activity
            const available   = items.filter(e => e.status === 'AVAILABLE').length
            const inUse       = items.filter(e => e.status === 'IN_USE').length
            const maintenance = items.filter(e => e.status === 'MAINTENANCE').length
            return (
              <div key={type} className="card">
                <div style={{ display:'flex', alignItems:'center', gap: 10, marginBottom: 14 }}>
                  <div style={{ background:'var(--brand-primary-light)', borderRadius: 8, padding: 8 }}>
                    <Icon size={18} color="var(--brand-primary)" />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{type.charAt(0) + type.slice(1).toLowerCase()}</div>
                    <div style={{ fontSize:11, color:'var(--text-muted)' }}>{items.length} total devices</div>
                  </div>
                </div>
                <div style={{ display:'flex', flexDirection:'column', gap: 6 }}>
                  {[
                    { label:'Available',   count: available,   color: EQUIP_COLORS.AVAILABLE },
                    { label:'In Use',      count: inUse,       color: EQUIP_COLORS.IN_USE },
                    { label:'Maintenance', count: maintenance, color: EQUIP_COLORS.MAINTENANCE },
                  ].map(({ label, count, color }) => (
                    <div key={label} style={{ display:'flex', alignItems:'center', gap: 10 }}>
                      <span style={{ fontSize:12, color:'var(--text-muted)', width: 80 }}>{label}</span>
                      <div className="workload-bar-bg">
                        <div
                          className="workload-bar-fill"
                          style={{ width:`${(count/items.length)*100}%`, background: color }}
                        />
                      </div>
                      <span style={{ fontSize:13, fontWeight:600, width:24, textAlign:'right' }}>{count}</span>
                    </div>
                  ))}
                </div>
                {/* Per-device list */}
                <div style={{ marginTop: 14, maxHeight: 120, overflowY:'auto' }}>
                  {items.map(e => (
                    <div key={e.equipment_id} style={{
                      display:'flex', justifyContent:'space-between', alignItems:'center',
                      padding:'3px 0', borderBottom:'1px solid var(--border-light)', fontSize: 11
                    }}>
                      <span style={{ fontFamily:'monospace', color:'var(--text-secondary)' }}>{e.equipment_id}</span>
                      <span style={{ fontSize:10, color:'var(--text-muted)' }}>{e.location}</span>
                      <span style={{ fontWeight:600, color: EQUIP_COLORS[e.status] || 'var(--text-primary)' }}>{e.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Staff Roster ── */}
      <div>
        <div className="section-header">
          <div>
            <div className="section-title">Staff Roster & Workload</div>
            <div className="section-sub">{staff.length} staff members — sorted by workload (highest first)</div>
          </div>
        </div>
        <div className="card" style={{ padding: 0, overflow:'hidden' }}>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Staff ID</th>
                  <th>Role</th>
                  <th>Skill Level</th>
                  <th>Shift</th>
                  <th style={{ minWidth: 180 }}>Workload</th>
                </tr>
              </thead>
              <tbody>
                {sortedStaff.map(s => (
                  <tr key={s.staff_id}>
                    <td style={{ fontFamily:'monospace', fontSize:13, fontWeight:600 }}>{s.staff_id}</td>
                    <td>{s.role}</td>
                    <td>
                      <span className="badge" style={{
                        background: s.skill_level === 'Critical-care' ? '#fef2f2' : s.skill_level === 'Emergency' ? '#fff7ed' : '#f0fdf4',
                        color:      s.skill_level === 'Critical-care' ? '#dc2626'  : s.skill_level === 'Emergency' ? '#f97316' : '#16a34a',
                      }}>
                        {s.skill_level}
                      </span>
                    </td>
                    <td style={{ fontSize:12, color:'var(--text-muted)' }}>{s.shift}</td>
                    <td>
                      <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
                        <div className="workload-bar-bg">
                          <div
                            className={`workload-bar-fill ${s.workload >= 85 ? 'high' : ''}`}
                            style={{ width: `${s.workload}%` }}
                          />
                        </div>
                        <span style={{ fontSize:12, fontWeight:600, width:36 }}>{s.workload}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  )
}
