# CareGrid API Contract

Base URL for local development: `http://localhost:8000`

This document describes the routes registered by `backend/api/main.py` and
`backend/api/auth.py`. Response examples show the JSON shape; example identifiers
and values are illustrative. Pydantic response models filter responses to the
documented fields.

## Authentication and errors

Routes marked as authenticated require a JWT bearer access token. Send it in the
HTTP `Authorization` header:

```http
Authorization: Bearer <access_token>
```

`POST /auth/login` issues the token. Protected routes return `401` when credentials
are missing or invalid, or the account is inactive. A valid token with an
insufficient role returns `403`.

Application `HTTPException` errors use this shape:

```json
{"detail":"Patient not found"}
```

Request validation failures use FastAPI's structured `422` response, generally
with a `detail` array containing error locations, messages, and error types. For
example:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "patient_id"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

Role requirements below are taken from the route dependencies. They describe the
roles currently accepted by each route, not an inferred permission matrix.

## Main API

### `GET /`

- **Purpose:** API availability message.
- **Authentication:** None; public.
- **Required roles:** None.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `RootResponse`.
- **Common errors:** None defined by this route.

```json
{"message":"CareGrid API is running"}
```

### `GET /patients`

- **Purpose:** List patient records.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`, `nurse`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `PatientsResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

```json
{
  "patients": [
    {
      "patient_id": "P0001",
      "age_group": "18-35",
      "acuity": 2,
      "specialty": "Pulmonology",
      "predicted_los": 2.3,
      "isolation_required": true,
      "ventilator_required": false,
      "arrival_time": "2026-10-01T08:09:13",
      "current_status": "WAITING"
    }
  ]
}
```

### `POST /patients/intake`

- **Purpose:** Register a new patient (or readmit a discharged patient) and create a `WAITING` Encounter.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`, `nurse`.
- **Request body:** `PatientIntakeRequest` (`patient_id` optional; auto-generated if omitted).
- **Success:** `201 Created`; `PatientIntakeResponse`.
- **Common errors:** `400` validation error; `401` missing/invalid/inactive credentials; `403` role not allowed; `409` patient already has an active waiting or admitted status; `422` invalid request body.

### `POST /patients/{patient_id}/discharge` and `POST /encounters/{encounter_id}/discharge`

- **Purpose:** Discharge an admitted patient/encounter, releasing all active bed and equipment assignments, moving the bed to `CLEANING`, and marking the patient `DISCHARGED`.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`.
- **Request body:** Optional `DischargeRequest`.
- **Success:** `200 OK`; `DischargeResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed; `404` patient or encounter not found; `409` encounter is not admitted or has no active assignment.

### `POST /patients/{patient_id}/transfer` and `POST /encounters/{encounter_id}/transfer`

- **Purpose:** Transfer an admitted patient/encounter to another compatible `AVAILABLE` bed, closing the prior `BedAssignment`, moving the old bed to `CLEANING`, and recording a new `BedAssignment`.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`.
- **Request body:** `TransferRequest`.
- **Success:** `200 OK`; `TransferResponse`.
- **Common errors:** `400` incompatible destination bed; `401` missing/invalid/inactive credentials; `403` role not allowed; `404` patient, encounter, or bed not found; `409` encounter not admitted or bed unavailable.

### `POST /beds/{bed_id}/cleaning-complete`

- **Purpose:** Mark a `CLEANING` bed as `AVAILABLE`.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `nurse`, `operator`.
- **Request:** No body.
- **Success:** `200 OK`; `BedCleaningResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed; `404` bed not found; `409` bed is not in `CLEANING` status or still has an active assignment.

### `POST /equipment/{equipment_id}/assign` and `POST /equipment/{equipment_id}/release`

- **Purpose:** Assign an `AVAILABLE` equipment item to an admitted encounter or release an `IN_USE` equipment item from its active encounter assignment.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`, `nurse`.
- **Request body:** `EquipmentAssignRequest` / optional `EquipmentReleaseRequest`.
- **Success:** `200 OK`; `EquipmentAssignmentResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed; `404` equipment, patient, or encounter not found; `409` encounter not admitted, equipment unavailable, or no active assignment.

### `GET /beds`

- **Purpose:** List beds and their current state.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`, `nurse`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `BedsResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

```json
{
  "beds": [
    {
      "bed_id": "B001",
      "bed_type": "ICU",
      "ward": "ICU-Alpha",
      "status": "OCCUPIED",
      "isolation_capable": true
    }
  ]
}
```

### `GET /staff`

- **Purpose:** List staff members.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `StaffResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

```json
{
  "staff": [
    {
      "staff_id": "S001",
      "role": "Nurse",
      "skill_level": "ICU",
      "shift": "Morning",
      "workload": 87
    }
  ]
}
```

### `GET /equipment`

- **Purpose:** List equipment and its current state.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `nurse`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `EquipmentResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

```json
{
  "equipment": [
    {
      "equipment_id": "E001",
      "type": "VENTILATOR",
      "status": "AVAILABLE",
      "location": "ICU-Alpha"
    }
  ]
}
```

### `POST /allocation/recommend`

- **Purpose:** Request a recommendation for a waiting patient using the current
  hospital state.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`.
- **Request body:** `AllocationRecommendRequest`.

```json
{"patient_id":"P0001"}
```

- **Success:** `200 OK`; `AllocationRecommendResponse`.
- **Common errors:** `400` invalid patient acuity; `401` missing/invalid/inactive
  credentials; `403` role not allowed; `404` patient not found; `409` patient is
  not waiting; `422` invalid request body.

Recommended response:

```json
{
  "recommendation_id": 108,
  "patient_id": "P0001",
  "recommended_bed_id": "B025",
  "algorithm": "rule_based",
  "reason": "Compatible ICU bed available",
  "status": "RECOMMENDED"
}
```

When no suitable resource is available, `recommended_bed_id` is nullable:

```json
{
  "recommendation_id": 109,
  "patient_id": "P0001",
  "recommended_bed_id": null,
  "algorithm": "rule_based",
  "reason": "No compatible available bed found",
  "status": "NO_SUITABLE_BED"
}
```

### `POST /allocation/approve`

- **Purpose:** Approve a persisted recommendation after revalidating the patient,
  encounter, bed, equipment, and (for DQN Safe) current safety result.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`.
- **Preferred request body:** `AllocationApproveRequest` with the exact
  `recommendation_id` returned by `POST /allocation/recommend`.

```json
{"recommendation_id":108}
```

- Optional `patient_id`, `bed_id`, and `encounter_id` values are consistency
  checks against the persisted recommendation. They cannot replace or override
  its stored patient, bed, or encounter.
- **Legacy compatibility:** A request with `patient_id` and `bed_id` and no
  `recommendation_id` is recorded as an `operator_override` recommendation and
  sent through the same lifecycle validation and transaction. If the patient has
  no WAITING Encounter, one is created in that transaction. A failed approval
  rolls back both the Encounter and override record. This path does not represent
  a rule-based or DQN result.
- `equipment_id` is accepted only with the legacy compatibility request; the
  lifecycle service validates that equipment and records its assignment.
- **Success:** `200 OK`; `AllocationApproveResponse`.
- **Common errors:** `400` invalid acuity, incompatible bed type, or isolation
  requirement not met; `401` missing/invalid/inactive credentials; `403` role not
  allowed; `404` patient or bed not found; `409` patient is not waiting, bed is no
  longer available, the recommendation is missing/stale/already decided, or no
  ventilator is available when required; `422` invalid request body; `500`
  allocation transaction failed and was rolled back.

```json
{"patient_id":"P0001","bed_id":"B025","status":"APPROVED"}
```

### `POST /allocation/reject`

- **Purpose:** Record an operator rejection decision against a persisted
  recommendation without changing the algorithm result.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`.
- **Preferred request body:** `recommendation_id` and a nonblank `reason` of at
  least three characters after trimming. The backend obtains the operator ID from
  the authenticated token.

```json
{"recommendation_id":108,"reason":"Clinical contraindication"}
```

- Optional `patient_id` is checked against the recommendation. For legacy
  compatibility, a patient-only request is accepted only if it identifies one
  eligible, undecided recommendation; ambiguous requests must use
  `recommendation_id`.
- **Success:** `200 OK`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not
  allowed; `404` patient or recommendation not found; `409` patient/encounter no
  longer waiting, ownership mismatch, recommendation ineligible or already
  decided, or legacy recommendation lookup ambiguous; `422` invalid or missing
  rejection reason/request body.

```json
{
  "recommendation_id": 108,
  "patient_id": "P0001",
  "status": "REJECTED",
  "reason": "Clinical contraindication"
}
```

### `POST /surge/simulate`

- **Purpose:** Run an in-memory surge simulation over the requested duration.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `operator`.
- **Request body:** `SurgeSimulationRequest`; both values must be greater than zero.

```json
{"arrival_rate_multiplier":1.5,"duration_hours":24}
```

- **Success:** `200 OK`; `SurgeSimulationResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not
  allowed; `422` invalid request body; `500` no simulation patients were loaded or
  the simulation failed.

```json
{
  "status": "COMPLETED",
  "arrival_rate_multiplier": 1.5,
  "duration_hours": 24,
  "patients_arrived": 150,
  "simulation_start": "2026-10-01T08:09:13",
  "simulation_end": "2026-10-02T08:09:13",
  "metrics": {
    "patients_total": 150,
    "patients_admitted": 110,
    "patients_discharged": 20,
    "patients_still_waiting": 40,
    "avg_wait_min": 55.2,
    "median_wait_min": 43.0,
    "avg_wait_incl_unadmitted_min": 90.1,
    "p90_wait_incl_unadmitted_min": 180.0,
    "p90_wait_min": 120.0,
    "max_wait_min": 240.0,
    "avg_wait_by_acuity_min": {
      "1": 20.0,
      "2": 35.0,
      "3": null,
      "4": 70.0,
      "5": 80.0
    },
    "pct_admitted_within_60min": 0.72,
    "icu_utilization": 0.82,
    "step_down_utilization": null,
    "ward_utilization": 0.61,
    "overall_bed_utilization": 0.7,
    "ventilator_utilization": 0.5,
    "bed_turnover_per_bed_per_day": 0.2,
    "peak_waiting_queue": 45,
    "constraint_violations": {
      "acuity_tier": 0,
      "isolation": 0,
      "ventilator": 0,
      "double_booking": 0,
      "total": 0
    },
    "measurement_window_hours": 24.0,
    "waiting_patients_elapsed_wait_min": {
      "avg": 30.0,
      "max": 60.0
    }
  }
}
```

The example values are illustrative; nullable utilization and acuity metrics may
be `null` depending on the simulated state.

### `GET /metrics`

- **Purpose:** Return database-derived patient, bed, ventilator, occupancy, and
  approved-allocation counts.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `doctor`, `nurse`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `MetricsResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

```json
{
  "patients_total": 150,
  "patients_waiting": 40,
  "patients_admitted": 20,
  "beds_total": 80,
  "beds_available": 24,
  "beds_occupied": 56,
  "bed_occupancy_rate": 0.7,
  "ventilators_total": 20,
  "ventilators_available": 8,
  "ventilators_in_use": 12,
  "approved_allocations": 56
}
```

### `GET /audit`

- **Purpose:** Return up to the 100 most recent audit records.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`, `operator`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `AuditResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` role not allowed.

`bed_id` is nullable:

```json
{
  "audit": [
    {
      "patient_id": "P0001",
      "bed_id": null,
      "action": "BED_EVENT",
      "algorithm": "rule_based",
      "timestamp": "2026-10-05T10:30:00+00:00"
    }
  ]
}
```

## Authentication API

### `POST /auth/login`

- **Purpose:** Authenticate an active user and issue a JWT access token.
- **Authentication:** None; public.
- **Required roles:** None.
- **Request body:** `UserLogin`.

```json
{"username":"care_admin","password":"example-password"}
```

- **Success:** `200 OK`; `TokenResponse`.
- **Common errors:** `401` invalid username/password or inactive account; `422`
  invalid request body.

```json
{"access_token":"<jwt>","token_type":"bearer"}
```

### `GET /auth/me`

- **Purpose:** Return the authenticated user's public account fields.
- **Authentication:** Bearer JWT.
- **Required roles:** Any active authenticated user; no additional role restriction.
- **Request:** No body or parameters.
- **Success:** `200 OK`; `UserResponse`.
- **Common errors:** `401` missing/invalid/inactive credentials.

```json
{
  "id": 1,
  "username": "care_admin",
  "email": "care_admin@example.com",
  "role": "admin",
  "is_active": true
}
```

### `POST /auth/users`

- **Purpose:** Create a user account. This is the only registered account
  creation route and is administrator-only.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`.
- **Request body:** `AdminUserCreate`; username length 3–50, valid email, password
  at least 8 characters and no more than 72 UTF-8 bytes, and role one of `admin`,
  `doctor`, `nurse`, or `operator`.

```json
{
  "username": "new_doctor",
  "email": "new_doctor@example.com",
  "password": "example-password",
  "role": "doctor"
}
```

- **Success:** `201 Created`; `UserResponse` (does not include the password or
  password hash).
- **Common errors:** `400` invalid role; `401` missing/invalid/inactive
  credentials; `403` caller is not an administrator; `409` username or email
  already registered; `422` invalid request body.

```json
{
  "id": 2,
  "username": "new_doctor",
  "email": "new_doctor@example.com",
  "role": "doctor",
  "is_active": true
}
```

### `GET /auth/users`

- **Purpose:** List user accounts.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`.
- **Request:** No body or parameters.
- **Success:** `200 OK`; array of `UserResponse` objects.
- **Common errors:** `401` missing/invalid/inactive credentials; `403` caller is
  not an administrator.

```json
[
  {
    "id": 1,
    "username": "care_admin",
    "email": "care_admin@example.com",
    "role": "admin",
    "is_active": true
  }
]
```

### `PATCH /auth/users/{user_id}`

- **Purpose:** Update a user's role and/or active state.
- **Authentication:** Bearer JWT.
- **Required roles:** `admin`.
- **Path parameter:** `user_id` is an integer user ID.
- **Request body:** `AdminUserUpdate`; `role` and `is_active` are optional fields.
  When provided, role must be one of `admin`, `doctor`, `nurse`, or `operator`;
  `is_active` must not be `null`. An empty update is rejected.

```json
{"role":"nurse","is_active":true}
```

- **Success:** `200 OK`; `UserResponse`.
- **Common errors:** `400` no update fields, invalid role, null `is_active`, or
  attempt to deactivate/remove the admin role from the caller's own account;
  `401` missing/invalid/inactive credentials; `403` caller is not an
  administrator; `404` user not found; `422` invalid path parameter or request
  body.

```json
{
  "id": 2,
  "username": "new_doctor",
  "email": "new_doctor@example.com",
  "role": "nurse",
  "is_active": true
}
```

## Registration availability

Public `POST /auth/register` is not registered and is unavailable (an unknown
route returns `404`). Account creation is administrator-only through
`POST /auth/users`.

## Simulated Time & Lifecycle Reconciliation

- **Simulated clock:** `build_hospital_state()` derives `state.current_time` from
  the latest `patients.arrival_time` in the database (stored as naive simulated
  datetime) rather than wall-clock UTC, falling back to UTC now only when the
  database has no patients. Wait-time calculations, G2 max-wait guardrails, and
  RL `wait_so_far` observations all operate on this simulated timeline.
- **Queue membership & status:** `encounters.status` is the authoritative
  lifecycle status (`WAITING`, `ADMITTED`, `DISCHARGED`), and
  `patients.current_status` is kept in sync as a denormalized cache by
  `backend/services/patient_lifecycle.py`.
- **Import & reconciliation:** `backend/import_data.py` creates `WAITING`
  `Encounter` rows for imported `WAITING` patients. Legacy `OCCUPIED` beds
  without `BedAssignment` rows are not backfilled with fabricated assignment
  history; `backend/reconcile_encounters.py` can be run idempotently to backfill
  missing `WAITING` encounters and report orphaned `OCCUPIED` beds.
