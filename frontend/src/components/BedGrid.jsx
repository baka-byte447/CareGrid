/**
 * BedGrid.jsx — Ward-by-Ward Bed Visualization
 *
 * Receives the beds array from GET /beds and groups them by ward name.
 * Each bed is shown as a color-coded card:
 *   🟢 AVAILABLE  🔴 OCCUPIED  🟡 CLEANING
 *
 * A pink dot in the top-right corner = isolation-capable bed.
 *
 * Props:
 *   beds (Array) - from fetchBeds() → beds[]
 */

export default function BedGrid({ beds }) {
  if (!beds || beds.length === 0) {
    return <div className="empty-state">No bed data available.</div>
  }

  // Group beds by ward
  const byWard = beds.reduce((acc, bed) => {
    if (!acc[bed.ward]) acc[bed.ward] = []
    acc[bed.ward].push(bed)
    return acc
  }, {})

  // Sort wards: ICU first, then STEP_DOWN, then WARD
  const typeOrder = { ICU: 0, STEP_DOWN: 1, WARD: 2 }
  const sortedWards = Object.entries(byWard).sort(([wa, a], [wb, b]) => {
    const ta = typeOrder[a[0]?.bed_type] ?? 9
    const tb = typeOrder[b[0]?.bed_type] ?? 9
    return ta - tb || wa.localeCompare(wb)
  })

  function statusClass(status) {
    if (status === 'AVAILABLE') return 'available'
    if (status === 'OCCUPIED')  return 'occupied'
    if (status === 'CLEANING')  return 'cleaning'
    return ''
  }

  function bedTypeLabel(t) {
    if (t === 'STEP_DOWN') return 'STEP'
    return t
  }

  // Count summary per ward
  function summary(wardBeds) {
    const avail   = wardBeds.filter(b => b.status === 'AVAILABLE').length
    const occ     = wardBeds.filter(b => b.status === 'OCCUPIED').length
    const cleaning = wardBeds.filter(b => b.status === 'CLEANING').length
    return { avail, occ, cleaning, total: wardBeds.length }
  }

  return (
    <div>
      {sortedWards.map(([ward, wardBeds]) => {
        const { avail, occ, cleaning, total } = summary(wardBeds)
        return (
          <div key={ward} className="bed-grid-section">
            <div className="ward-title">
              <span>{ward}</span>
              <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>
                ({wardBeds[0]?.bed_type}) — {avail} free / {occ} occupied / {cleaning} cleaning / {total} total
              </span>
            </div>
            <div className="beds-row">
              {wardBeds.map(bed => (
                <div
                  key={bed.bed_id}
                  className={`bed-card ${statusClass(bed.status)}`}
                  title={`${bed.bed_id} | ${bed.ward} | ${bed.status}${bed.isolation_capable ? ' | Isolation-capable' : ''}`}
                >
                  {bed.isolation_capable && <span className="bed-iso-dot" title="Isolation-capable" />}
                  <span className="bed-id">{bed.bed_id}</span>
                  <span style={{ fontSize: 9 }}>{bedTypeLabel(bed.bed_type)}</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {/* Legend */}
      <div style={{ display: 'flex', gap: 20, marginTop: 16, flexWrap: 'wrap' }}>
        {[
          { cls: 'available', label: 'Available' },
          { cls: 'occupied',  label: 'Occupied' },
          { cls: 'cleaning',  label: 'Cleaning (30 min turnover)' },
        ].map(({ cls, label }) => (
          <div key={cls} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
            <div className={`bed-card ${cls}`} style={{ width: 18, height: 18, minWidth: 18, fontSize: 0 }} />
            {label}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
          <div style={{ width: 10, height: 10, background: '#be185d', borderRadius: '50%' }} />
          Isolation-capable bed
        </div>
      </div>
    </div>
  )
}
