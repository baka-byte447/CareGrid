/**
 * api.js — CareGrid API Service Layer
 *
 * Every function in this file maps 1-to-1 to a backend endpoint
 * defined in backend/api/main.py and documented in backend/api/api_contract.md.
 *
 * Base URL is /api which Vite proxies to http://localhost:8000
 * (see vite.config.js → server.proxy)
 *
 * For the mentor: changing the backend URL only requires updating BASE_URL here.
 */

const BASE_URL = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ─── GET /patients ───────────────────────────────────────────────────────────
// Returns all patients loaded from data/synthetic/patients.csv (via PostgreSQL)
// Fields: patient_id, age_group, acuity (1–5), specialty, predicted_los,
//         isolation_required, ventilator_required, arrival_time, current_status
export const fetchPatients = () => request('/patients');

// ─── GET /beds ────────────────────────────────────────────────────────────────
// Returns all 100 beds from data/synthetic/beds.csv (via PostgreSQL)
// Fields: bed_id, bed_type (ICU/STEP_DOWN/WARD), ward, status, isolation_capable
export const fetchBeds = () => request('/beds');

// ─── GET /staff ───────────────────────────────────────────────────────────────
// Returns all staff from data/synthetic/staff.csv
// Fields: staff_id, role, skill_level, shift, workload (%)
export const fetchStaff = () => request('/staff');

// ─── GET /equipment ───────────────────────────────────────────────────────────
// Returns all equipment from data/synthetic/equipment.csv
// Fields: equipment_id, type (VENTILATOR/TELEMETRY/DIAGNOSTIC), status, location
export const fetchEquipment = () => request('/equipment');

// ─── GET /metrics ─────────────────────────────────────────────────────────────
// Returns live metrics computed from the database:
// patients_total, patients_waiting, patients_admitted,
// beds_total, beds_available, beds_occupied, bed_occupancy_rate,
// ventilators_total, ventilators_available, ventilators_in_use,
// approved_allocations
export const fetchMetrics = () => request('/metrics');

// ─── GET /audit ───────────────────────────────────────────────────────────────
// Returns last 100 allocation approval records from audit_log table
// Fields: patient_id, bed_id, action (APPROVED), algorithm, timestamp
export const fetchAuditLogs = () => request('/audit');

// ─── POST /allocation/recommend ───────────────────────────────────────────────
// Runs the rule-based allocation engine (simulator/hospital/allocation_rules.py logic)
// to find the best available bed for a waiting patient.
// Returns: recommended_bed_id, algorithm, reason, status (RECOMMENDED/NO_SUITABLE_BED)
export const recommendAllocation = (patientId) =>
  request('/allocation/recommend', {
    method: 'POST',
    body: JSON.stringify({ patient_id: patientId }),
  });

// ─── POST /allocation/approve ─────────────────────────────────────────────────
// Human-in-the-loop approval: atomically marks bed OCCUPIED,
// reserves ventilator if needed, marks patient ADMITTED, writes AuditLog.
// Returns 409 if bed was taken by another request (PostgreSQL row-lock).
export const approveAllocation = (patientId, bedId) =>
  request('/allocation/approve', {
    method: 'POST',
    body: JSON.stringify({ patient_id: patientId, bed_id: bedId }),
  });

// ─── POST /surge/simulate ─────────────────────────────────────────────────────
// NOTE: Backend stub — not yet fully implemented (returns NOT_IMPLEMENTED).
// Will run the discrete-event simulator under surge conditions.
export const simulateSurge = (arrivalRateMultiplier, durationHours) =>
  request('/surge/simulate', {
    method: 'POST',
    body: JSON.stringify({
      arrival_rate_multiplier: arrivalRateMultiplier,
      duration_hours: durationHours,
    }),
  });
