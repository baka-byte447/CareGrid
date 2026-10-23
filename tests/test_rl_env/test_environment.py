from datetime import datetime

import numpy as np
import pytest

gym = pytest.importorskip("gymnasium")

from rl.environment.hospital_env import CareGridHospitalEnv
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.patients.patient import Patient


class FakePredictor:
    def predict(self, patient):
        # Intentionally does not read patient.predicted_los.
        return 3.25


def test_reset_observation_contract(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    obs, info = env.reset(seed=123)
    assert obs.shape == (10,)
    assert obs.dtype == np.float32
    assert env.observation_space.contains(obs)
    assert info["simulation_time"] is not None
    env.close()


def test_invalid_incompatible_bed_request_is_rejected(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    env.reset(seed=1)
    # For a WARD-only acuity, ICU is incompatible; if the first synthetic patient
    # differs, set a focused one-patient episode through reset options.
    patient = Patient("p1", "18-64", 1, "GENERAL", 2.0, False, False, datetime(2026, 1, 1, 8))
    env.reset(seed=1, options={"patients": [patient]})
    # Existing bed file starts empty; action 0 is incompatible for acuity 1.
    _, reward, terminated, truncated, info = env.step(0)
    assert reward <= -env.invalid_action_penalty
    assert info.get("invalid_reason") == "bed_type_incompatible_with_acuity"
    assert not (terminated and truncated)
    env.close()


def test_wait_action_keeps_patient_waiting(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    patient = Patient("p1", "18-64", 1, "GENERAL", 2.0, False, False, datetime(2026, 1, 1, 8))
    env.reset(seed=1, options={"patients": [patient]})
    _, reward, _, _, info = env.step(3)
    assert reward == pytest.approx(-env.wait_penalty)
    assert info["waiting_count"] == 1
    env.close()


def test_ventilator_requirement_is_hard_constraint(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    patient = Patient("p1", "18-64", 5, "GENERAL", 2.0, False, True, datetime(2026, 1, 1, 8))
    env.reset(seed=1, options={"patients": [patient]})
    # Remove all ventilators from the otherwise loaded hospital.
    env.state.equipment = {k: v for k, v in env.state.equipment.items() if v.type != "VENTILATOR"}
    _, reward, _, _, info = env.step(0)
    assert reward <= -env.invalid_action_penalty
    assert info["invalid_reason"] == "ventilator_unavailable"
    assert not env.state.admitted_patients
    env.close()


def test_seeded_reset_repeats_initial_observation(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    obs1, _ = env.reset(seed=42)
    obs2, _ = env.reset(seed=42)
    np.testing.assert_allclose(obs1, obs2)
    env.close()


def test_valid_ward_action_admits_patient(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    patient = Patient("p1", "18-64", 1, "GENERAL", 2.0, False, False, datetime(2026, 1, 1, 8))
    env.reset(seed=5, options={"patients": [patient]})
    engine_patient = env.engine.patients["p1"]

    print("Same object:", engine_patient is patient)
    print("Original patient ID:", id(patient))
    print("Engine patient ID:", id(engine_patient))
    print("Engine patient status:", engine_patient.status)
    print("Original patient status:", patient.status)

    _, reward, _, _, info = env.step(2)
    
    print("Engine status after step:", engine_patient.status)
    print("Original status after step:", patient.status)
    assert reward > 0
    assert info["admitted_count"] == 1
    admitted_patient = env._patients["p1"]
    assert admitted_patient.status == "ADMITTED"
    assert admitted_patient.bed_id is not None
    env.close()


def test_legacy_rule_based_engine_still_runs(data_dir):
    from simulator.hospital.engine import SimulationEngine
    from simulator.hospital.loader import load_hospital_state

    patient = Patient("legacy-p1", "18-64", 1, "GENERAL", 1.0, False, False, datetime(2026, 1, 1, 8))
    state = load_hospital_state(str(data_dir), start_empty=True)
    engine = SimulationEngine(state, [patient])
    engine.seed_arrivals()
    engine.run()
    assert engine.admitted_count == 1
    assert engine.discharged_count == 1
    assert patient.status == "DISCHARGED"


def test_episode_time_limit_truncates_without_processing_future_discharge(data_dir):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=FakePredictor())
    patient = Patient("long-stay", "18-64", 1, "GENERAL", 3.0, False, False, datetime(2026, 1, 1, 8))
    env.reset(seed=9, options={"patients": [patient]})
    engine_patient = env.engine.patients["long-stay"]
    observation, reward, terminated, truncated, info = env.step(2)
    assert engine_patient.status == "ADMITTED"
    assert not terminated
    assert truncated
    assert env.state.current_time == datetime(2026, 1, 2, 8)
    assert not env.engine.queue.is_empty()
    assert env.engine.queue.peek().timestamp > env._end_time
    assert env.engine.patients["long-stay"].status == "ADMITTED"    
    assert info["episode_summary"]["admitted"] == 1
    env.close()
