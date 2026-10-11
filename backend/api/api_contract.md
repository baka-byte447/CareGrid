# CareGrid API Contract

Base URL:

http://localhost:8000

---

## 1. GET /patients

Returns the list of patients.

### Request

GET /patients

### Response

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

---

## 2. GET /beds

Returns the current hospital bed state.

### Request

GET /beds

### Response

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

---

## 3. GET /staff

Returns the list of hospital staff members.

### Request

GET /staff

### Response

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
---

## 4. GET /equipment

Returns the list of hospital equipment and its current state.

### Request

GET /equipment

### Response

{
  "equipment": [
    {
      "equipment_id": "E001",
      "type": "Ventilator",
      "status": "AVAILABLE",
      "location": "ICU-Alpha"
    }
  ]
}
---

## 5. POST /allocation/recommend

Requests a bed allocation recommendation for a patient.

### Request

POST /allocation/recommend

{
  "patient_id": "P0001"
}

### Response

{
  "patient_id": "P0001",
  "recommended_bed_id": "B025",
  "algorithm": "rule_based",
  "reason": "Compatible isolation-capable bed available",
  "status": "RECOMMENDED"
}

---

## 6. POST /allocation/approve

Approves a previously generated allocation recommendation.

### Request

POST /allocation/approve

{
  "patient_id": "P0001",
  "bed_id": "B025"
}

### Response

{
  "patient_id": "P0001",
  "bed_id": "B025",
  "status": "APPROVED"
}

---

## 7. POST /surge/simulate

Runs a hospital surge scenario.

### Request

POST /surge/simulate

{
  "arrival_rate_multiplier": 1.5,
  "duration_hours": 24
}

### Response

{
  "status": "COMPLETED",
  "arrival_rate_multiplier": 1.5,
  "duration_hours": 24,
  "patients_processed": 150
}

---

## 8. GET /metrics

Returns hospital performance metrics.

### Request

GET /metrics

### Response

{
  "average_wait_time": 19517.2,
  "icu_utilization": 0.82,
  "bed_turnover": 3.4,
  "constraint_violations": 0
}

---

## 9. GET /audit

Returns allocation and approval history.

### Request

GET /audit

### Response

{
  "audit": [
    {
      "patient_id": "P0001",
      "bed_id": "B025",
      "action": "APPROVED",
      "algorithm": "rule_based",
      "timestamp": "2026-10-05T10:30:00"
    }
  ]
}