"""
Shared observation builder for CareGrid-RL.

Extracted from CareGridHospitalEnv._observation() so that the serving layer
can build the same vector without importing the Gymnasium environment.

The function signature mirrors the env's internal state; callers supply the
already-computed LOS estimate and the mapping of patient_id -> Patient.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

from simulator.patients.patient import Patient
from simulator.hospital.state import HospitalState

BED_ACTIONS = ("ICU", "STEP_DOWN", "WARD")
QUEUE_LOG_CAP = 200

N_OBSERVATIONS = 14   # obs v1
N_OBSERVATIONS_V2 = 17  # obs v2 (adds wait_so_far, tod_sin, tod_cos)


def build_observation(
    patient: Optional[Patient],
    state: HospitalState,
    los_estimate: float,
    now: Optional[datetime],
    version: int = 2,
    patients_by_id: Optional[dict] = None,
) -> np.ndarray:
    """Build the RL observation vector for *patient* given *state*.

    Parameters
    ----------
    patient:
        The patient currently awaiting an allocation decision. If None, a
        zero vector is returned (terminal observation).
    state:
        Live hospital state (beds, equipment, waiting_queue, current_time).
    los_estimate:
        Pre-computed LOS prediction for this patient (days).
    now:
        Wall-clock time for time-of-day features.  Falls back to
        ``state.current_time`` when None.
    version:
        Observation version: 1 (14 features) or 2 (17 features).
    patients_by_id:
        Mapping patient_id → Patient used to compute critical_share_of_queue.
        May be None; if so, the queue-critical feature is 0.
    """
    if version not in (1, 2):
        raise ValueError(f"version must be 1 or 2, got {version!r}")

    n_obs = N_OBSERVATIONS if version == 1 else N_OBSERVATIONS_V2

    if patient is None:
        return np.zeros(n_obs, dtype=np.float32)

    effective_now = now or state.current_time

    values = [
        patient.acuity / 5.0,
        1.0 if patient.age_group in ("65+", "65_PLUS", "SENIOR", "ELDERLY") else 0.0,
        float(patient.isolation_required),
        float(patient.ventilator_required),
        min(max(float(los_estimate), 1.0), 10.0) / 10.0,
    ]

    # Bed availability per tier
    for bed_type in BED_ACTIONS:
        beds = state.beds_by_type(bed_type)
        available = sum(b.status == "AVAILABLE" for b in beds)
        values.append(available / len(beds) if beds else 0.0)

    # Ventilator availability
    vents = [e for e in state.equipment.values() if e.type == "VENTILATOR"]
    available_vents = sum(e.status == "AVAILABLE" for e in vents)
    values.append(available_vents / len(vents) if vents else 0.0)

    # Queue size (log-normalised)
    values.append(
        min(float(np.log1p(len(state.waiting_queue))) / np.log1p(QUEUE_LOG_CAP), 1.0)
    )

    # Isolation-capable bed availability per tier
    for bed_type in BED_ACTIONS:
        iso_beds = [b for b in state.beds_by_type(bed_type) if b.isolation_capable]
        free = sum(b.status == "AVAILABLE" for b in iso_beds)
        values.append(free / len(iso_beds) if iso_beds else 0.0)

    # Critical share of queue (acuity >= 4)
    waiting = state.waiting_queue
    if waiting and patients_by_id:
        critical = sum(
            patients_by_id[pid].acuity >= 4
            for pid in waiting
            if pid in patients_by_id
        )
        values.append(critical / len(waiting))
    else:
        values.append(0.0)

    # v2 extra features
    if version == 2:
        # wait_so_far: how long has this patient been waiting? (normalised to 7 days)
        if patient.arrival_time and effective_now:
            elapsed_days = max(
                0.0,
                (effective_now - patient.arrival_time).total_seconds() / 86400.0,
            )
            wait_val = min(elapsed_days / 7.0, 1.0)
        else:
            wait_val = 0.0

        # time_of_day (sin / cos encoding, shifted to [0, 1])
        if effective_now:
            hour = effective_now.hour + effective_now.minute / 60.0
            tod_sin = (np.sin(2.0 * np.pi * hour / 24.0) + 1.0) / 2.0
            tod_cos = (np.cos(2.0 * np.pi * hour / 24.0) + 1.0) / 2.0
        else:
            tod_sin, tod_cos = 0.5, 0.5

        values.extend([float(wait_val), float(tod_sin), float(tod_cos)])

    return np.asarray(values, dtype=np.float32)

