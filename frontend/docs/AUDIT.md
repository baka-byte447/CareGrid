# CareGrid HMIS Frontend: Architecture & API Audit Report

**Date**: October 2026  
**Auditor**: Senior Frontend Engineer & Product Designer  
**Scope**: `frontend/` architecture, backend contract alignment, and clinical safety integrity

---

## 1. Executive Summary

This audit establishes the definitive architectural foundation and backend API contract for the **CareGrid** web frontend. CareGrid is a hospital management and bed-allocation platform where clinical staff monitor hospital occupancy, manage emergency admission queues, and review reinforcement-learning (RL) bed allocation policies.

All decisions adhere strictly to the foundational build rules:
1. **Scope boundary**: Only files inside `frontend/` have been created or modified. Backend, RL, simulator, models, and root files remain untouched.
2. **Real Data Integrity**: No mock, invented, or placeholder data exists in production code. All UI models map 1:1 to real FastAPI endpoints in `backend/api/main.py`.
3. **Temporal Integrity**: Patient arrival times are simulated dates. The frontend strictly forbids comparing simulated dates against the user's local clock (`Date.now()`).
4. **Safety & Transparency**: Clinical safety checks (isolation, mechanical ventilation) are labeled as display checks. Missing backend capabilities (such as allocation rejection, admin mutations, or auth endpoints) are represented transparently via disabled actions with informative tooltips.

---

## 2. API Contract Audit & Ground Truth Verification

The authoritative ground truth for all backend endpoints is `backend/api/main.py` and the SQLAlchemy models in `backend/models/`. A discrepancy analysis between `backend/api/api_contract.md` and the actual Python source revealed critical differences:

| Endpoint | `api_contract.md` Claim | `main.py` Ground Truth (Authoritative) | Frontend Handling |
|---|---|---|---|
| `GET /metrics` | Claimed 5 keys (`total_beds`, `available_beds`, `occupied_beds`, `occupancy_rate`, `icu_capacity`) | Returns 11 keys (`patients_total`, `patients_waiting`, `patients_admitted`, `beds_total`, `beds_available`, `beds_occupied`, `bed_occupancy_rate`, `ventilators_total`, `ventilators_available`, `ventilators_in_use`, `approved_allocations`) | Mapped to `MetricsResponseSchema` in `schemas.ts` using the 11 real fields. |
| `GET /beds` | Implied bed-to-patient link with patient IDs in beds | Returns `bed_id`, `bed_type`, `ward`, `status`, `isolation_capable`. No patient ID or name is returned. | The UI does not display patient names on bed tiles; beds are grouped by ward and reflect physical status. |
| `GET /audit` | Suggested an `id` primary key was serialized | Serializes only `patient_id`, `bed_id`, `action`, `algorithm`, `timestamp`. | `AuditEntrySchema` uses composite keys for React lists; no invented `id` field is expected. |
| `POST /surge/simulate` | Suggested flat response structure | Returns `{ status, arrival_rate_multiplier, duration_hours, patients_arrived, simulation_start, simulation_end, metrics: { ... } }` | Nested metrics parsed via `SurgeMetricsSchema` matching `simulator/metrics/summary.py`. |
| `POST /allocation/reject` | Implied existence of allocation rejection | **No reject endpoint exists.** Only `/allocation/recommend` and `/allocation/approve` exist. | The Reject button is rendered disabled with tooltip: *"Reject is not available in the backend yet"*. |
| `POST /auth/login` | Mentioned authentication | **No authentication or session endpoints exist.** Backend has no user database table. | Login route is gated behind `VITE_AUTH_ENABLED=false`. When disabled, user is routed directly to the clinical dashboard. |

---

## 3. Authoritative Endpoint Inventory

### 1. `GET /patients`
- **Response**: `{ patients: Patient[] }`
- **Fields**:
  - `patient_id` (string, e.g. `"PAT-001"`)
  - `age_group` (string, e.g. `"45-64"`)
  - `acuity` (integer, `1` to `5`)
  - `specialty` (string, e.g. `"Cardiology"`)
  - `predicted_los` (float, days, e.g. `4.5`)
  - `isolation_required` (boolean)
  - `ventilator_required` (boolean)
  - `arrival_time` (ISO-8601 string, simulated hospital clock)
  - `current_status` (`"WAITING"` | `"ADMITTED"`)

### 2. `GET /beds`
- **Response**: `{ beds: Bed[] }`
- **Fields**:
  - `bed_id` (string, e.g. `"ICU-01"`)
  - `bed_type` (`"ICU"` | `"STEP_DOWN"` | `"WARD"`)
  - `ward` (string, e.g. `"ICU-A"`)
  - `status` (`"AVAILABLE"` | `"OCCUPIED"` | `"CLEANING"`)
  - `isolation_capable` (boolean)

### 3. `GET /staff`
- **Response**: `{ staff: Staff[] }`
- **Fields**:
  - `staff_id` (string, e.g. `"STF-001"`)
  - `role` (string, e.g. `"Critical-care"`)
  - `skill_level` (string, e.g. `"SENIOR"`)
  - `shift` (string, e.g. `"Day"`)
  - `workload` (integer, `0` to `100`)

### 4. `GET /equipment`
- **Response**: `{ equipment: Equipment[] }`
- **Fields**:
  - `equipment_id` (string, e.g. `"VENT-001"`)
  - `type` (`"VENTILATOR"` | `"TELEMETRY"` | `"DIAGNOSTIC"`)
  - `status` (`"AVAILABLE"` | `"IN_USE"` | `"MAINTENANCE"`)
  - `location` (string, e.g. `"ICU-A"`)

### 5. `GET /metrics`
- **Response**:
  - `patients_total` (integer)
  - `patients_waiting` (integer)
  - `patients_admitted` (integer)
  - `beds_total` (integer)
  - `beds_available` (integer)
  - `beds_occupied` (integer)
  - `bed_occupancy_rate` (float, `0.0` to `1.0`)
  - `ventilators_total` (integer)
  - `ventilators_available` (integer)
  - `ventilators_in_use` (integer)
  - `approved_allocations` (integer)

### 6. `GET /audit`
- **Response**: `{ audit: AuditEntry[] }` (Last 100 allocation actions, descending)
- **Fields**:
  - `patient_id` (string)
  - `bed_id` (string | null)
  - `action` (string, e.g. `"BED_ALLOCATED"`)
  - `algorithm` (string, e.g. `"PPO_Policy"`)
  - `timestamp` (ISO-8601 UTC string from server)

### 7. `POST /allocation/recommend`
- **Request Body**: `{ patient_id: string }`
- **Response**:
  - `patient_id` (string)
  - `recommended_bed_id` (string | null)
  - `algorithm` (string)
  - `reason` (string)
  - `status` (`"RECOMMENDED"` | `"NO_SUITABLE_BED"`)

### 8. `POST /allocation/approve`
- **Request Body**: `{ patient_id: string, bed_id: string }`
- **Response**:
  - `patient_id` (string)
  - `bed_id` (string)
  - `status`: `"APPROVED"`
- **HTTP Error Codes Handled**:
  - `400`: Invalid request payload or patient already admitted
  - `404`: Patient or bed not found
  - `409`: Conflict (bed already occupied by another patient)
  - `422`: Unprocessable entity (Pydantic validation failure)
  - `500`: Internal allocation failure

### 9. `POST /surge/simulate`
- **Request Body**: `{ arrival_rate_multiplier: number, duration_hours: number }`
- **Response**:
  - `status`: `"COMPLETED"`
  - `arrival_rate_multiplier` (number)
  - `duration_hours` (integer)
  - `patients_arrived` (integer)
  - `simulation_start` (string)
  - `simulation_end` (string)
  - `metrics`: Nested dictionary of simulation summary statistics (`avg_wait_min`, `pct_admitted_within_60min`, `overall_bed_utilization`, `icu_utilization`, `step_down_utilization`, `ward_utilization`, `peak_waiting_queue`, `constraint_violations`, etc.)

---

## 4. Frontend Architecture & Design Decisions

1. **Vite Reverse Proxy (`/api`)**:
   - The FastAPI backend does not configure CORS middleware.
   - The Vite development server configures a reverse proxy forwarding `/api/*` to `http://localhost:8000/*` with path rewrite, preventing browser cross-origin blocking.
2. **Strict TypeScript & Zod Parsing**:
   - Every network response passes through Zod validation before state ingestion. If the backend schema deviates, an explicit, user-friendly error is thrown rather than failing silently with undefined values.
3. **Data Cache & Invalidation**:
   - TanStack React Query maintains normalized caches. Approving a bed allocation immediately invalidates `['beds']`, `['patients']`, `['metrics']`, and `['audit']` queries, providing atomic real-time updates.
4. **Accessible Clinical Design System**:
   - Built on CSS custom variables with dark mode support (`prefers-color-scheme` and manual toggle).
   - High contrast ratios conforming to WCAG AA guidelines.
   - Layout-matching skeletons and explicit error boundaries to ensure the interface never crashes completely.
