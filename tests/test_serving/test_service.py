"""
Tests for rl.serving.service.AllocationService.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pytest

from rl.serving.service import AllocationService, DEFAULT_MODEL_PATH
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.patients.patient import Patient


def make_test_state():
    state = HospitalState()
    # 2 ICU, 2 STEP_DOWN, 2 WARD
    state.beds["B_ICU_1"] = Bed("B_ICU_1", "ICU", "ICU_WARD", "AVAILABLE", isolation_capable=True)
    state.beds["B_ICU_2"] = Bed("B_ICU_2", "ICU", "ICU_WARD", "OCCUPIED", isolation_capable=False)
    state.beds["B_SD_1"] = Bed("B_SD_1", "STEP_DOWN", "SD_WARD", "AVAILABLE", isolation_capable=False)
    state.beds["B_SD_2"] = Bed("B_SD_2", "STEP_DOWN", "SD_WARD", "AVAILABLE", isolation_capable=True)
    state.beds["B_W_1"] = Bed("B_W_1", "WARD", "GEN_WARD", "AVAILABLE", isolation_capable=False)
    state.beds["B_W_2"] = Bed("B_W_2", "WARD", "GEN_WARD", "OCCUPIED", isolation_capable=False)
    state.equipment["E_VENT_1"] = Equipment("E_VENT_1", "VENTILATOR", "AVAILABLE", "ICU_WARD")
    state.current_time = datetime(2026, 1, 1, 12, 0, 0)
    return state


def test_allocation_service_recommendation():
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Model file not found: {DEFAULT_MODEL_PATH}")

    service = AllocationService(DEFAULT_MODEL_PATH)
    assert service.policy is not None

    state = make_test_state()
    # Acuity 5 critical patient
    patient = Patient(
        patient_id="P_CRIT",
        age_group="ADULT",
        acuity=5,
        specialty="GENERAL",
        predicted_los=4.0,
        isolation_required=False,
        ventilator_required=True,
        arrival_time=datetime(2026, 1, 1, 11, 0, 0),
    )

    result = service.recommend(patient, state)
    assert result.patient_id == "P_CRIT"
    assert result.algorithm == "dqn_safe"
    assert result.status == "RECOMMENDED"
    assert result.recommended_bed_id == "B_ICU_1"
    assert result.final_bed_type == "ICU"
    assert result.safety is not None
    assert len(result.q_values) == 4


def test_allocation_service_fallback():
    # Service with missing model should gracefully use rule-based fallback
    service = AllocationService(model_path="nonexistent_model.npz")
    assert service.policy is None

    state = make_test_state()
    patient = Patient(
        patient_id="P_NORM",
        age_group="ADULT",
        acuity=1,
        specialty="GENERAL",
        predicted_los=2.0,
        isolation_required=False,
        ventilator_required=False,
        arrival_time=datetime(2026, 1, 1, 8, 0, 0),
    )

    result = service.recommend(patient, state)
    assert result.patient_id == "P_NORM"
    assert result.algorithm == "rule_based_fallback"
    assert result.status == "RECOMMENDED"
    assert result.recommended_bed_id == "B_W_1"
