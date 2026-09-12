"""
CareGrid-RL: Synthetic Healthcare Data Generator
Simulates realistic hospital operational entities:
- Patients (Normal, Moderate Surge, Severe Surge arrival patterns)
- Beds (ICU, Step-down, Ward with isolation capability)
- Clinical Staff (RN, Charge Nurse, Attending with workload and skill levels)
- Medical Equipment (Ventilator, Telemetry, Diagnostic)
- Simulator Event Triggers
"""

import argparse
import csv
import json
import math
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# Seed for reproducibility while maintaining natural variability
SEED = 42
random.seed(SEED)

SPECIALTIES = ['General', 'Cardiology', 'Pulmonology', 'Neurology', 'Trauma']
AGE_GROUPS = ['18-35', '36-50', '51-65', '65+']
AGE_WEIGHTS = [0.20, 0.25, 0.30, 0.25]

# Hourly arrival distribution weights (24-hour cycle, peaking around 10-14h and 18-21h)
DIURNAL_WEIGHTS = [
    0.35, 0.25, 0.20, 0.18, 0.22, 0.35,  # 00:00 - 05:00 (Quiet early morning)
    0.60, 0.90, 1.25, 1.45, 1.50, 1.40,  # 06:00 - 11:00 (Morning surge/admissions)
    1.30, 1.25, 1.35, 1.40, 1.30, 1.45,  # 12:00 - 17:00 (Afternoon peak)
    1.50, 1.35, 1.10, 0.85, 0.65, 0.45   # 18:00 - 23:00 (Evening triage drop-off)
]
NORM_FACTOR = sum(DIURNAL_WEIGHTS) / 24.0
HOURLY_MODIFIERS = [w / NORM_FACTOR for w in DIURNAL_WEIGHTS]


def sample_patient(patient_num: int, arrival_dt: datetime) -> dict:
    """
    Generates a single patient record with realistic clinical dependencies:
    - Acuity: 1 (Mild) to 5 (Critical/Resuscitation)
    - Older patients have slightly higher acuity and longer LOS
    - High acuity Pulmonology/Trauma heavily correlates with ventilators
    - Pulmonology has higher isolation need (respiratory isolation)
    - Predicted LOS scales with acuity and age with natural clinical variance
    """
    age_group = random.choices(AGE_GROUPS, weights=AGE_WEIGHTS)[0]
    specialty = random.choice(SPECIALTIES)

    # Acuity distribution skewed towards 2-3 (typical emergency/hospital admissions)
    # Acuity 5 is critical/resuscitation, Acuity 1 is non-urgent
    if age_group == '65+':
        acuity_weights = [0.08, 0.22, 0.35, 0.23, 0.12]
    elif age_group == '51-65':
        acuity_weights = [0.12, 0.28, 0.34, 0.18, 0.08]
    elif specialty == 'Trauma':
        acuity_weights = [0.05, 0.15, 0.30, 0.30, 0.20]
    else:
        acuity_weights = [0.20, 0.35, 0.30, 0.11, 0.04]

    acuity = random.choices([1, 2, 3, 4, 5], weights=acuity_weights)[0]

    # Clinical dependencies for Ventilator
    if acuity == 5:
        if specialty in ['Pulmonology', 'Trauma']:
            vent_prob = 0.75
        elif specialty == 'Cardiology':
            vent_prob = 0.50
        else:
            vent_prob = 0.35
    elif acuity == 4:
        if specialty == 'Pulmonology':
            vent_prob = 0.40
        elif specialty == 'Trauma':
            vent_prob = 0.30
        else:
            vent_prob = 0.15
    elif acuity == 3 and specialty == 'Pulmonology':
        vent_prob = 0.08
    else:
        vent_prob = 0.0

    ventilator_required = 'YES' if random.random() < vent_prob else 'NO'

    # Clinical dependencies for Isolation (droplet/airborne, infectious, immunosuppressed)
    if specialty == 'Pulmonology':
        iso_prob = 0.35
    elif acuity >= 4:
        iso_prob = 0.15
    else:
        iso_prob = 0.05

    isolation_required = 'YES' if random.random() < iso_prob else 'NO'

    # Length of Stay (days): base 1-10 days with gamma-like distribution
    # Acuity 1: 1.0 - 2.5 days
    # Acuity 2: 1.5 - 3.5 days
    # Acuity 3: 2.5 - 5.5 days
    # Acuity 4: 4.0 - 8.0 days
    # Acuity 5: 5.0 - 10.0 days
    base_los = {
        1: (1.2, 0.4),
        2: (2.3, 0.6),
        3: (3.8, 1.0),
        4: (5.8, 1.3),
        5: (7.4, 1.5)
    }
    mean_los, std_los = base_los[acuity]
    raw_los = random.gauss(mean_los, std_los)
    if age_group == '65+':
        raw_los += random.uniform(0.3, 1.1)
    if ventilator_required == 'YES':
        raw_los += random.uniform(0.8, 1.8)

    predicted_los = round(max(1.0, min(10.0, raw_los)), 1)

    return {
        'patient_id': f'P{patient_num:04d}',
        'age_group': age_group,
        'acuity': acuity,
        'specialty': specialty,
        'predicted_los': predicted_los,
        'isolation_required': isolation_required,
        'ventilator_required': ventilator_required,
        'arrival_time': arrival_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'current_status': 'WAITING'
    }


def generate_patients(num_patients: int = 1000, mode: str = 'normal', start_time: datetime = None) -> list:
    """
    Generates virtual patients following non-homogeneous Poisson arrival process.
    Arrival rate:
    - normal: 5 patients/hour average
    - moderate_surge: 8 patients/hour average
    - severe_surge: 13.5 patients/hour average
    """
    if start_time is None:
        start_time = datetime(2026, 10, 1, 8, 0, 0)

    rates = {
        'normal': 5.0,
        'moderate_surge': 8.0,
        'severe_surge': 13.5
    }
    base_rate = rates.get(mode, 5.0)

    patients = []
    current_time = start_time

    for i in range(1, num_patients + 1):
        hour_of_day = current_time.hour
        effective_rate = base_rate * HOURLY_MODIFIERS[hour_of_day]

        # Inter-arrival time in minutes (exponential distribution)
        mean_interval_min = 60.0 / effective_rate
        interval_min = random.expovariate(1.0 / mean_interval_min)
        interval_min = max(0.5, interval_min)

        current_time += timedelta(minutes=interval_min)
        patient = sample_patient(i, current_time)
        patients.append(patient)

    return patients


def generate_beds() -> list:
    """
    Generates initial hospital bed fleet (100 beds total):
    - 20 ICU beds (Ward: ICU-Alpha, ICU-Bravo)
    - 30 STEP_DOWN beds (Ward: StepDown-East, StepDown-West)
    - 50 WARD beds (Ward: Medical-North, Medical-South, Surgical-East, Surgical-West)
    """
    beds = []
    bed_id_counter = 1

    configs = [
        ('ICU', 'ICU-Alpha', 10, True, 4),      # 10 beds, 4 isolation capable
        ('ICU', 'ICU-Bravo', 10, True, 4),      # 10 beds, 4 isolation capable
        ('STEP_DOWN', 'StepDown-East', 15, True, 3),
        ('STEP_DOWN', 'StepDown-West', 15, True, 3),
        ('WARD', 'Medical-North', 15, True, 2),
        ('WARD', 'Medical-South', 15, False, 0),
        ('WARD', 'Surgical-East', 10, False, 0),
        ('WARD', 'Surgical-West', 10, False, 0),
    ]

    for bed_type, ward, count, iso_avail, iso_count in configs:
        for idx in range(1, count + 1):
            is_iso = 'YES' if idx <= iso_count else 'NO'
            status_roll = random.random()
            if status_roll < 0.65:
                status = 'OCCUPIED'
            elif status_roll < 0.90:
                status = 'AVAILABLE'
            else:
                status = 'CLEANING'

            beds.append({
                'bed_id': f'B{bed_id_counter:03d}',
                'bed_type': bed_type,
                'ward': ward,
                'status': status,
                'isolation_capable': is_iso
            })
            bed_id_counter += 1

    return beds


def generate_staff() -> list:
    """
    Generates clinical staff roster (45 staff members across shifts and units).
    """
    roles_skills = [
        ('RN', 'Critical-care', 15),
        ('RN', 'Emergency', 12),
        ('RN', 'General', 10),
        ('Charge Nurse', 'Critical-care', 4),
        ('Resident', 'General', 4)
    ]
    shifts = ['Day', 'Night', 'Evening']
    staff = []
    staff_id_counter = 1

    for role, skill, count in roles_skills:
        for _ in range(count):
            shift = random.choice(shifts)
            workload_val = random.randint(45, 88)
            staff.append({
                'staff_id': f'N{staff_id_counter:03d}' if 'Nurse' in role or role == 'RN' else f'D{staff_id_counter:03d}',
                'role': role,
                'skill_level': skill,
                'shift': shift,
                'workload': f'{workload_val}%'
            })
            staff_id_counter += 1

    return staff


def generate_equipment() -> list:
    """
    Generates hospital critical equipment fleet (80 devices).
    """
    configs = [
        ('VENTILATOR', 25, ['ICU-Alpha', 'ICU-Bravo', 'Emergency', 'Central Storage']),
        ('TELEMETRY', 40, ['StepDown-East', 'StepDown-West', 'Medical-North', 'Emergency', 'Central Storage']),
        ('DIAGNOSTIC', 15, ['Emergency', 'Radiology', 'Central Storage'])
    ]

    equipment = []
    eq_id_counter = 1

    for eq_type, count, locations in configs:
        prefix = 'VENT' if eq_type == 'VENTILATOR' else ('TELM' if eq_type == 'TELEMETRY' else 'DIAG')
        for _ in range(count):
            loc = random.choice(locations)
            status_roll = random.random()
            if status_roll < 0.60:
                status = 'IN_USE'
            elif status_roll < 0.90:
                status = 'AVAILABLE'
            else:
                status = 'MAINTENANCE'

            equipment.append({
                'equipment_id': f'E_{prefix}_{eq_id_counter:03d}',
                'type': eq_type,
                'status': status,
                'location': loc
            })
            eq_id_counter += 1

    return equipment


def generate_simulator_event_templates() -> list:
    """
    Defines event types used by the discrete-event simulator engine.
    """
    return [
        {
            "event_type": "PATIENT_ARRIVAL",
            "description": "Patient arrives at ED/triage queue with triage acuity and initial clinical profile.",
            "payload_fields": ["patient_id", "acuity", "specialty", "arrival_time", "isolation_required", "ventilator_required"]
        },
        {
            "event_type": "PATIENT_ADMISSION",
            "description": "RL decision engine allocates patient to bed, clinical staff, and equipment.",
            "payload_fields": ["patient_id", "bed_id", "staff_id", "equipment_ids", "admission_time"]
        },
        {
            "event_type": "PATIENT_TRANSFER",
            "description": "Patient condition escalated or de-escalated, triggering transfer between ICU/Step-down/Ward.",
            "payload_fields": ["patient_id", "source_bed_id", "target_bed_id", "transfer_time", "reason"]
        },
        {
            "event_type": "PATIENT_DISCHARGE",
            "description": "Patient LOS reaches completion or safe discharge threshold.",
            "payload_fields": ["patient_id", "bed_id", "discharge_time", "actual_los"]
        },
        {
            "event_type": "BED_RELEASE",
            "description": "Bed transitions to CLEANING status, then becomes AVAILABLE for next patient.",
            "payload_fields": ["bed_id", "cleaned_at", "turnaround_duration_minutes"]
        },
        {
            "event_type": "EQUIPMENT_RELEASE",
            "description": "Ventilator or telemetry unit sanitized and returned to storage or redeployed.",
            "payload_fields": ["equipment_id", "source_ward", "status"]
        },
        {
            "event_type": "SHIFT_START",
            "description": "New shift roster takes effect, recalculating nurse/patient staffing ratios.",
            "payload_fields": ["shift_name", "active_staff_count", "start_time"]
        },
        {
            "event_type": "SHIFT_END",
            "description": "Shift handover protocols executed.",
            "payload_fields": ["shift_name", "end_time"]
        },
        {
            "event_type": "SURGE_START",
            "description": "Surge trigger activated, accelerating arrival rates to 8-15 patients/hr.",
            "payload_fields": ["surge_tier", "start_time", "expected_duration_hours"]
        },
        {
            "event_type": "SURGE_END",
            "description": "Hospital returns to baseline arrival intensity.",
            "payload_fields": ["end_time", "peak_queue_length"]
        }
    ]


def save_csv(data: list, filepath: Path):
    if not data:
        return
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} rows to {filepath}")


def save_json(data, filepath: Path):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Saved JSON to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="CareGrid-RL Synthetic Data Generator")
    parser.add_argument('--patients', type=int, default=1000, help="Number of virtual patients (default: 1000)")
    parser.add_argument('--mode', choices=['normal', 'moderate_surge', 'severe_surge'], default='normal',
                        help="Arrival pattern scenario")
    parser.add_argument('--outdir', type=str, default='data/synthetic', help="Output directory path")
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating synthetic hospital data (Patients: {args.patients}, Scenario: {args.mode})...")

    # 1. Generate Patients
    patients = generate_patients(num_patients=args.patients, mode=args.mode)
    save_csv(patients, out_dir / 'patients.csv')
    save_csv(patients, out_dir / f'patients_{args.mode}_{args.patients}.csv')

    # 2. Generate Beds
    beds = generate_beds()
    save_csv(beds, out_dir / 'beds.csv')

    # 3. Generate Staff
    staff = generate_staff()
    save_csv(staff, out_dir / 'staff.csv')

    # 4. Generate Equipment
    equipment = generate_equipment()
    save_csv(equipment, out_dir / 'equipment.csv')

    # 5. Event definitions for the simulator
    events = generate_simulator_event_templates()
    save_json(events, out_dir / 'simulator_events.json')

    print("Synthetic dataset generation completed successfully.")


if __name__ == '__main__':
    main()
