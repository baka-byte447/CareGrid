/**
 * PatientsPage.jsx — Patient Queue and Allocation Workflow
 *
 * Data: GET /patients → shows all patients filtered by status tab.
 *
 * Features:
 *   - Tab filter: All | Waiting | Admitted
 *   - Search by patient_id or specialty
 *   - Acuity badge (1=green → 5=red)
 *   - Isolation & Ventilator requirement badges
 *   - "Recommend & Allocate" button → opens AllocationModal
 *   - Auto-refreshes after a successful allocation
 */

import { useEffect, useState, useCallback } from 'react'
import { fetchPatients } from '../services/api.js'
import AllocationModal from '../components/AllocationModal.jsx'
import { RefreshCw, Search, Shield, Wind } from 'lucide-react'

const ACUITY_LABELS = { 1:'Non-urgent', 2:'Less Urgent', 3:'Urgent', 4:'Emergent', 5:'Critical' }
const STATUS_TABS   = ['All', 'WAITING', 'ADMITTED']

export default function PatientsPage() {
  const [patients, setPatients] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [tab, setTab]           = useState('WAITING')
  const [search, setSearch]     = useState('')
  const [selected, setSelected] = useState(null)   // patient selected for modal

  const load = useCallback(async () => {
    try {
      setError(null)
      const data = await fetchPatients()
      // Sort: highest acuity first (5→1), then by arrival time
      const sorted = (data.patients || []).sort((a, b) =>
        b.acuity - a.acuity || new Date(a.arrival_time) - new Date(b.arrival_time)
      )
      setPatients(sorted)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  // Filter by tab + search
  const filtered = patients.filter(p => {
    if (tab !== 'All' && p.current_status !== tab) return false
    if (search) {
      const q = search.toLowerCase()
      return p.patient_id.toLowerCase().includes(q) || p.specialty.toLowerCase().includes(q)
    }
    return true
  })

  // Counts for tab badges
  const counts = {
    All:      patients.length,
    WAITING:  patients.filter(p => p.current_status === 'WAITING').length,
    ADMITTED: patients.filter(p => p.current_status === 'ADMITTED').length,
  }

  function formatArrival(t) {
    if (!t) return '—'
    return new Date(t).toLocaleString('en-IN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })
  }

  return (
    <div>
      {/* ── Filter Row ── */}
      <div style={{ display:'flex', alignItems:'center', gap: 12, marginBottom: 16, flexWrap:'wrap' }}>
        {/* Status Tabs */}
        <div style={{ display:'flex', background:'var(--bg-surface)', border:'1px solid var(--border-light)', borderRadius:'var(--radius-sm)', overflow:'hidden' }}>
          {STATUS_TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '7px 14px',
                fontSize: 12,
                fontWeight: tab === t ? 700 : 500,
                background: tab === t ? 'var(--brand-primary)' : 'transparent',
                color: tab === t ? 'white' : 'var(--text-secondary)',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              {t === 'All' ? 'All' : t.charAt(0) + t.slice(1).toLowerCase()} ({counts[t]})
            </button>
          ))}
        </div>

        {/* Search */}
        <div style={{ display:'flex', alignItems:'center', gap: 6, background:'var(--bg-surface)', border:'1px solid var(--border-light)', borderRadius:'var(--radius-sm)', padding:'6px 10px', flex: 1, maxWidth: 260 }}>
          <Search size={13} color="var(--text-muted)" />
          <input
            placeholder="Search patient ID or specialty…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ border:'none', outline:'none', fontSize:12, background:'transparent', width:'100%', color:'var(--text-primary)' }}
          />
        </div>

        <button className="btn btn-ghost btn-sm" onClick={load} style={{ marginLeft:'auto' }}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* ── Table ── */}
      {loading && <div className="loading-state"><div className="spinner" />Loading patients…</div>}
      {error   && <div className="error-box">{error}</div>}
      {!loading && !error && (
        <div className="card" style={{ padding: 0, overflow:'hidden' }}>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Patient ID</th>
                  <th>Acuity</th>
                  <th>Specialty</th>
                  <th>Age Group</th>
                  <th>LOS (days)</th>
                  <th>Requirements</th>
                  <th>Status</th>
                  <th>Arrival</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={9} style={{ textAlign:'center', color:'var(--text-muted)', padding: 32 }}>
                      No patients match the current filter.
                    </td>
                  </tr>
                )}
                {filtered.map(p => (
                  <tr key={p.patient_id}>
                    <td style={{ fontWeight: 600, fontFamily:'monospace', fontSize:13 }}>{p.patient_id}</td>
                    <td>
                      <div style={{ display:'flex', alignItems:'center', gap: 6 }}>
                        <span className={`acuity-badge acuity-${p.acuity}`}>{p.acuity}</span>
                        <span style={{ fontSize:11, color:'var(--text-muted)' }}>{ACUITY_LABELS[p.acuity]}</span>
                      </div>
                    </td>
                    <td>{p.specialty}</td>
                    <td>{p.age_group}</td>
                    <td>{p.predicted_los}</td>
                    <td>
                      <div style={{ display:'flex', gap: 4, flexWrap:'wrap' }}>
                        {p.isolation_required && (
                          <span className="badge badge-isolation"><Shield size={9} /> Isolation</span>
                        )}
                        {p.ventilator_required && (
                          <span className="badge badge-vent"><Wind size={9} /> Ventilator</span>
                        )}
                        {!p.isolation_required && !p.ventilator_required && (
                          <span style={{ fontSize:11, color:'var(--text-muted)' }}>—</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`badge badge-${p.current_status?.toLowerCase()}`}>
                        {p.current_status}
                      </span>
                    </td>
                    <td style={{ fontSize:12, color:'var(--text-muted)' }}>{formatArrival(p.arrival_time)}</td>
                    <td>
                      {p.current_status === 'WAITING' ? (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => setSelected(p)}
                        >
                          Allocate
                        </button>
                      ) : (
                        <span style={{ fontSize: 11, color:'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding:'10px 14px', fontSize:11, color:'var(--text-muted)', borderTop:'1px solid var(--border-light)' }}>
            Showing {filtered.length} of {patients.length} patients · Sorted by acuity (highest first)
          </div>
        </div>
      )}

      {/* ── Allocation Modal ── */}
      {selected && (
        <AllocationModal
          patient={selected}
          onClose={() => setSelected(null)}
          onSuccess={() => { setSelected(null); load() }}
        />
      )}
    </div>
  )
}
