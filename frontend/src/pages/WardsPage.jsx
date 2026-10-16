/**
 * WardsPage.jsx — Full Bed Grid by Ward
 *
 * Data: GET /beds → groups all 100 beds by ward and renders BedGrid.
 * Shows live occupancy counts per ward type.
 */

import { useEffect, useState } from 'react'
import { fetchBeds } from '../services/api.js'
import BedGrid from '../components/BedGrid.jsx'
import { RefreshCw } from 'lucide-react'

export default function WardsPage() {
  const [beds, setBeds]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  async function load() {
    try {
      setError(null)
      const data = await fetchBeds()
      setBeds(data.beds || [])
      setLastRefresh(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [])

  const byType = beds.reduce((a, b) => {
    a[b.bed_type] = a[b.bed_type] || { total: 0, avail: 0 }
    a[b.bed_type].total++
    if (b.status === 'AVAILABLE') a[b.bed_type].avail++
    return a
  }, {})

  return (
    <div>
      {/* Summary row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        {['ICU','STEP_DOWN','WARD'].map(t => (
          byType[t] ? (
            <div key={t} className="card" style={{ padding: '12px 18px', minWidth: 160 }}>
              <div className="metric-label">{t.replace('_',' ')}</div>
              <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>
                {byType[t].avail} <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--text-muted)' }}>/ {byType[t].total} free</span>
              </div>
            </div>
          ) : null
        ))}

        <button className="btn btn-ghost btn-sm" onClick={load} style={{ alignSelf: 'center', marginLeft: 'auto' }}>
          <RefreshCw size={13} /> Refresh
        </button>
        {lastRefresh && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
            Last updated {lastRefresh.toLocaleTimeString()}
          </span>
        )}
      </div>

      {loading && <div className="loading-state"><div className="spinner" />Loading beds…</div>}
      {error   && <div className="error-box">{error}</div>}
      {!loading && !error && (
        <div className="card">
          <BedGrid beds={beds} />
        </div>
      )}
    </div>
  )
}
