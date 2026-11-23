"""
Parity tests for shared observation builder rl.environment.observation.
"""
from __future__ import annotations

import numpy as np
import pytest

from rl.environment.hospital_env import CareGridHospitalEnv, N_OBSERVATIONS, N_OBSERVATIONS_V2
from rl.environment.observation import build_observation


def test_observation_dimensions():
    from simulator.hospital.state import HospitalState
    from simulator.patients.patient import Patient

    from datetime import datetime
    state = HospitalState()
    patient = Patient(
        patient_id="P1",
        age_group="ADULT",
        acuity=3,
        specialty="GENERAL",
        predicted_los=3.5,
        isolation_required=False,
        ventilator_required=False,
        arrival_time=datetime(2026, 1, 1, 8, 0, 0),
    )

    obs_v1 = build_observation(patient, state, 3.5, now=None, version=1)
    assert obs_v1.shape == (N_OBSERVATIONS,)
    assert obs_v1.dtype == np.float32

    obs_v2 = build_observation(patient, state, 3.5, now=None, version=2)
    assert obs_v2.shape == (N_OBSERVATIONS_V2,)
    assert obs_v2.dtype == np.float32

    # Terminal observation when patient is None
    obs_term = build_observation(None, state, 0.0, now=None, version=2)
    assert obs_term.shape == (N_OBSERVATIONS_V2,)
    assert np.all(obs_term == 0.0)


def test_env_observation_delegation():
    """Verify CareGridHospitalEnv produces the exact same observation as build_observation."""
    env = CareGridHospitalEnv(observation_version=2)
    obs, info = env.reset(seed=42)

    patient = env.current_patient
    assert patient is not None
    pred_los = env._los_estimates[patient.patient_id]
    expected = build_observation(
        patient=patient,
        state=env.state,
        los_estimate=pred_los,
        now=env.state.current_time,
        version=2,
        patients_by_id=env._patients,
    )

    np.testing.assert_allclose(obs, expected, atol=1e-6)
