# CareGrid-RL Synthetic Hospital Datasets & Generator

This directory contains the synthetic operational data and generation tooling for the CareGrid Reinforcement Learning and Discrete-Event Simulation environments.

## 1. Data Schema & Entities

### Patients (`patients.csv` / `patients_normal_1000.csv`)
- `patient_id`: Unique identifier (`P0001`, `P0002`, ...)
- `age_group`: Demographic bracket (`18-35`, `36-50`, `51-65`, `65+`)
- `acuity`: Clinical urgency score from `1` (Non-urgent) to `5` (Resuscitation/Critical)
- `specialty`: Admitting department (`General`, `Cardiology`, `Pulmonology`, `Neurology`, `Trauma`)
- `predicted_los`: Estimated inpatient duration in days (`1.0` to `10.0` days)
- `isolation_required`: `YES` or `NO` (infectious pathogen / contact / respiratory precaution)
- `ventilator_required`: `YES` or `NO` (invasive mechanical ventilation)
- `arrival_time`: Timestamp of patient triage arrival
- `current_status`: Initial state in queue (`WAITING`)

### Beds (`beds.csv`)
- `bed_id`: Identifier (`B001` - `B100`)
- `bed_type`: Care level (`ICU`, `STEP_DOWN`, `WARD`)
- `ward`: Unit location (e.g. `ICU-Alpha`, `StepDown-East`, `Medical-North`)
- `status`: State (`AVAILABLE`, `OCCUPIED`, `CLEANING`)
- `isolation_capable`: `YES` or `NO` (negative pressure or dedicated anteroom)

### Staff (`staff.csv`)
- `staff_id`: Nurse/Physician ID (`N001`, `D001`)
- `role`: Clinical position (`RN`, `Charge Nurse`, `Resident`)
- `skill_level`: Specialization (`Critical-care`, `Emergency`, `General`)
- `shift`: Shift assignment (`Day`, `Night`, `Evening`)
- `workload`: Active utilization percentage (`45%` - `88%`)

### Medical Equipment (`equipment.csv`)
- `equipment_id`: Device tag (`E_VENT_001`, `E_TELM_001`, `E_DIAG_001`)
- `type`: Equipment category (`VENTILATOR`, `TELEMETRY`, `DIAGNOSTIC`)
- `status`: Availability (`AVAILABLE`, `IN_USE`, `MAINTENANCE`)
- `location`: Current ward or depot (`ICU-Alpha`, `Emergency`, `Central Storage`)

### Discrete-Event Triggers (`simulator_events.json`)
Defines simulation lifecycle transitions:
- `PATIENT_ARRIVAL`
- `PATIENT_ADMISSION`
- `PATIENT_TRANSFER`
- `PATIENT_DISCHARGE`
- `BED_RELEASE`
- `EQUIPMENT_RELEASE`
- `SHIFT_START`
- `SHIFT_END`
- `SURGE_START`
- `SURGE_END`

---

## 2. Generating Datasets (1,000, 5,000, 10,000 & Surge Scenarios)

The generator script `generate_synthetic_data.py` uses non-homogeneous Poisson processes with realistic diurnal curves and clinical correlation logic.

### Commands

1. **Default Normal Dataset (1,000 virtual patients, ~5 patients/hour)**:
   ```bash
   python data/synthetic/generate_synthetic_data.py --patients 1000 --mode normal
   ```

2. **Scale to 5,000 Patients**:
   ```bash
   python data/synthetic/generate_synthetic_data.py --patients 5000 --mode normal
   ```

3. **Scale to 10,000 Patients**:
   ```bash
   python data/synthetic/generate_synthetic_data.py --patients 10000 --mode normal
   ```

4. **Moderate Surge Scenario (~8 patients/hour)**:
   ```bash
   python data/synthetic/generate_synthetic_data.py --patients 1000 --mode moderate_surge
   ```

5. **Severe Surge Scenario (~12-15 patients/hour)**:
   ```bash
   python data/synthetic/generate_synthetic_data.py --patients 1000 --mode severe_surge
   ```
