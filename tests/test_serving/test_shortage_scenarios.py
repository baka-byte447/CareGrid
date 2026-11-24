"""
Tests for shortage scenarios and isolation overflow.
"""
from __future__ import annotations

import pytest

from rl.environment.hospital_env import CareGridHospitalEnv
from simulator.hospital.loader import load_hospital_state
from simulator.hospital.scenarios import SHORTAGE_SCENARIOS, apply_shortage
from simulator.patients.patient import Patient
from datetime import datetime


def test_shortage_scenarios_cut_capacities():
    data_dir = "data/synthetic"
    base_state = load_hospital_state(data_dir)
    icu_total = len([b for b in base_state.beds.values() if b.bed_type == "ICU"])
    vent_total = len([e for e in base_state.equipment.values() if e.type == "VENTILATOR"])

    # Test icu_shortage
    s = load_hospital_state(data_dir)
    apply_shortage(s, "icu_shortage", seed=42)
    icu_oos = sum(b.status == "OUT_OF_SERVICE" for b in s.beds.values() if b.bed_type == "ICU")
    assert icu_oos == icu_total // 2

    # Test equipment_shortage
    s = load_hospital_state(data_dir)
    apply_shortage(s, "equipment_shortage", seed=42)
    vent_maint = sum(e.status == "MAINTENANCE" for e in s.equipment.values() if e.type == "VENTILATOR")
    assert vent_maint == vent_total // 2

    # Test staff_shortage
    s = load_hospital_state(data_dir)
    apply_shortage(s, "staff_shortage", seed=42)
    gen_oos = sum(b.status == "OUT_OF_SERVICE" for b in s.beds.values() if b.bed_type in ("WARD", "STEP_DOWN"))
    assert gen_oos > 0

    # Test combined_crisis
    s = load_hospital_state(data_dir)
    apply_shortage(s, "combined_crisis", seed=42)
    assert sum(b.status == "OUT_OF_SERVICE" for b in s.beds.values() if b.bed_type == "ICU") == icu_total // 2
    assert sum(e.status == "MAINTENANCE" for e in s.equipment.values() if e.type == "VENTILATOR") == vent_total // 2


def test_isolation_overflow_behavior():
    # Without overflow: acuity 2 isolation patient cannot take STEP_DOWN
    env_strict = CareGridHospitalEnv(isolation_overflow=False)
    env_strict.reset(seed=1)
    # Fill all ward isolation beds
    for b in env_strict.state.beds_by_type("WARD"):
        if b.isolation_capable:
            b.status = "OCCUPIED"

    p_iso = Patient(
        patient_id="P_ISO",
        age_group="ADULT",
        acuity=2,
        specialty="GENERAL",
        predicted_los=3.0,
        isolation_required=True,
        ventilator_required=False,
        arrival_time=datetime(2026, 1, 1, 8, 0, 0),
    )
    env_strict._current_patient_id = "P_ISO"
    env_strict._patients["P_ISO"] = p_iso
    mask_strict = env_strict.valid_actions()
    # STEP_DOWN (index 1) should be False
    assert not mask_strict[1]

    # With overflow: acuity 2 isolation patient CAN take STEP_DOWN when ward isolation is full
    env_overflow = CareGridHospitalEnv(isolation_overflow=True)
    env_overflow.reset(seed=1)
    for b in env_overflow.state.beds_by_type("WARD"):
        if b.isolation_capable:
            b.status = "OCCUPIED"

    env_overflow._current_patient_id = "P_ISO"
    env_overflow._patients["P_ISO"] = p_iso
    mask_overflow = env_overflow.valid_actions()
    # STEP_DOWN (index 1) should now be True
    assert mask_overflow[1]
