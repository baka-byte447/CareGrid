/**
 * DashboardPage.jsx — Hospital Command-Center Overview
 *
 * Data sources:
 *   GET /metrics  → KPI cards (patients, beds, ventilators, allocations)
 *   GET /beds     → Bed status breakdown (donut chart)
 *   GET /patients → Acuity distribution (bar chart)
 *
 * All data comes from the FastAPI backend which reads from PostgreSQL
 * tables populated from data/synthetic/patients.csv, beds.csv, etc.
 */

import { useEffect, useState } from 'react'
import { fetchMetrics, fetchBeds, fetchPatients } from '../services/api.js'
import MetricCard from '../components/MetricCard.jsx'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { BedDouble, Users, Activity, CheckCircle, Wind } from 'lucide-react'

const BED_COLORS = {
  Available: '#16a34a',
  Occupied:  '#dc2626',
  Cleaning:  '#d97706',
}
const ACUITY_COLORS = ['#22c55e','#84cc16','#f59e0b','#f97316','#dc2626']

export default function DashboardPage() {
  const [metrics, setMetrics]   = useState(null)
  const [beds, setBeds]         = useState([])
  const [patients, setPatients] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const [m, b, p] = await Promise.all([
          fetchMetrics(),
          fetchBeds(),
          fetchPatients(),
        ])
        setMetrics(m)
        setBeds(b.beds || [])
        setPatients(p.patients || [])
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
    // Auto-refresh every 15 seconds to stay live
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [])

  if (loading) return <div className="loading-state"><div className="spinner" />Loading hospital data…</div>
  if (error)   return <div className="error-box">{error} — Is the FastAPI backend running at localhost:8000?</div>

  // ── Derived chart data ────────────────────────────────────────────────────────
  const bedStatusData = [
    { name: 'Available', value: metrics.beds_available },
    { name: 'Occupied',  value: metrics.beds_occupied },
    { name: 'Cleaning',  value: metrics.beds_total - metrics.beds_available - metrics.beds_occupied },
  ].filter(d => d.value > 0)

  // Count patients by acuity 1-5 from patient data
  const acuityCounts = [1,2,3,4,5].map(a => ({
    name: `Acuity ${a}`,
    count: patients.filter(p => p.acuity === a).length,
  }))

  // Count waiting patients by specialty
  const waitingBySpecialty = patients
    .filter(p => p.current_status === 'WAITING')
    .reduce((acc, p) => {
      acc[p.specialty] = (acc[p.specialty] || 0) + 1
      return acc
    }, {})
  const specialtyData = Object.entries(waitingBySpecialty)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  const occupancyPct = Math.round((metrics.bed_occupancy_rate || 0) * 100)

  return (
    <div>
      {/* ── KPI Metric Cards ── */}
      <div className="metric-grid">
        <MetricCard
          label="Total Patients"
          value={metrics.patients_total}
          sub="Loaded from database"
          icon={Users}
        />
        <MetricCard
          label="Waiting Queue"
          value={metrics.patients_waiting}
          sub="Awaiting allocation"
          color="purple"
          icon={Activity}
        />
        <MetricCard
          label="Admitted"
          value={metrics.patients_admitted}
          sub="Currently in beds"
          color="green"
          icon={CheckCircle}
        />
        <MetricCard
          label="Beds Available"
          value={metrics.beds_available}
          sub={`of ${metrics.beds_total} total`}
          color="green"
          icon={BedDouble}
        />
        <MetricCard
          label="Beds Occupied"
          value={metrics.beds_occupied}
          sub={`${occupancyPct}% occupancy`}
          color="red"
          icon={BedDouble}
        />
        <MetricCard
          label="Ventilators Free"
          value={metrics.ventilators_available}
          sub={`of ${metrics.ventilators_total} total`}
          color={metrics.ventilators_available === 0 ? 'red' : 'amber'}
          icon={Wind}
        />
        <MetricCard
          label="Approvals Today"
          value={metrics.approved_allocations}
          sub="Rule-based algorithm"
          icon={CheckCircle}
        />
      </div>

      {/* ── Charts ── */}
      <div className="charts-grid">
        {/* Bed Status Donut */}
        <div className="card">
          <div className="card-title">Bed Status Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={bedStatusData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
              >
                {bedStatusData.map((entry) => (
                  <Cell key={entry.name} fill={BED_COLORS[entry.name]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [`${v} beds`]} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Acuity Distribution Bar */}
        <div className="card">
          <div className="card-title">Patient Acuity Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={acuityCounts} barSize={28}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" name="Patients" radius={[4,4,0,0]}>
                {acuityCounts.map((_, i) => (
                  <Cell key={i} fill={ACUITY_COLORS[i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Waiting by Specialty ── */}
      {specialtyData.length > 0 && (
        <div className="card">
          <div className="card-title">Waiting Patients by Specialty</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={specialtyData} layout="vertical" barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={100} />
              <Tooltip />
              <Bar dataKey="value" name="Waiting" fill="var(--brand-primary)" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
