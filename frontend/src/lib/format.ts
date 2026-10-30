/**
 * format.ts — Number, duration and date formatters.
 *
 * Rules:
 * - Never use Date.now() to compute patient wait times (simulated dates).
 * - Audit log timestamps are real server UTC times; label them as such.
 * - All formatters are pure functions for easy unit testing.
 */

/** Format a decimal as a percentage, e.g. 0.82 → "82%" or with custom places */
export function formatPct(value?: number | null, places?: number): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  if (places !== undefined) {
    return `${(value * 100).toFixed(places)}%`
  }
  return `${Math.round(value * 100)}%`
}

/** Format a float to fixed decimal places */
export function formatDecimal(value?: number | null, places = 1): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  return value.toFixed(places)
}

/**
 * Format minutes as a human-readable duration.
 * e.g. 90 → "1h 30m", 45 → "45m", 0 → "0m"
 */
export function formatMinutes(minutes?: number | null): string {
  if (minutes === undefined || minutes === null || Number.isNaN(minutes)) return '—'
  if (minutes <= 0) return '0m'
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

/**
 * Format a simulated arrival time (ISO string) for display.
 * Shows date + time but never computes relative time against Date.now().
 * Label: "Simulated date" context must be clear in the UI.
 */
export function formatSimulatedDate(isoString?: string | null): string {
  if (!isoString) return '—'
  try {
    const d = new Date(isoString)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toLocaleString('en-GB', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

/**
 * Format a real server UTC timestamp for the audit log.
 * This is a genuine server time, not a simulated date.
 */
export function formatServerTimestamp(isoString?: string | null): string {
  if (!isoString) return '—'
  try {
    const d = new Date(isoString)
    if (Number.isNaN(d.getTime())) return '—'
    return (
      d.toLocaleString('en-GB', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }) + ' UTC'
    )
  } catch {
    return '—'
  }
}

/** Format a float LOS as "X.X days" or "X.Xd" */
export function formatLOS(days?: number | null): string {
  if (days === undefined || days === null || Number.isNaN(days)) return '—'
  return `${days.toFixed(1)}d`
}

/** Tabular number formatting for metric values */
export function formatCount(n?: number | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return '—'
  return n.toLocaleString('en')
}
