"""
Tests for Resource Manager simulator hooks, ResourceManagerAgent, and 3-agent MARL.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np

from rl.environment.hospital_env import CareGridHospitalEnv
from rl.marl.multi_agent_env import CareGridMAEnv, MODE_NORMAL, MODE_SURGE
from rl.marl.resource_agent import (
    RESOURCE_EXPEDITE_CLEANING,
    RESOURCE_FLOAT_STAFF,
    RESOURCE_HOLD,
    RESOURCE_MOBILIZE_VENT,
    ResourceManagerAgent,
)
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.loader import load_hospital_state
from simulator.hospital.scenarios import apply_shortage


def test_engine_resource_manager_hooks():
    state = load_hospital_state("data/synthetic", start_empty=True)
    state.current_time = datetime(2026, 1, 1, 12, 0, 0)
    apply_shortage(state, "equipment_shortage", seed=0)
    engine = SimulationEngine(state, [])

    # 1. Mobilize ventilator from MAINTENANCE -> AVAILABLE
    maint_before = len(state.maintenance_ventilators())
    assert maint_before > 0
    vent_id = engine.mobilize_ventilator()
    assert vent_id is not None
    assert len(state.maintenance_ventilators()) == maint_before - 1
    assert state.equipment[vent_id].status == "AVAILABLE"
    assert engine.resource_interventions["mobilize_ventilator"] == 1

    # 2. Expedite cleaning on an ICU bed currently in CLEANING
    icu_bed = state.beds_by_type("ICU")[0]
    icu_bed.status = "CLEANING"
    accelerated = engine.expedite_cleaning("ICU", minutes=10)
    assert accelerated == 1
    assert engine._cleaning_minutes["ICU"] == 10
    assert engine.resource_interventions["expedite_cleaning"] == 1

    # 3. Float staff from General/Step-down -> Critical-care
    gen_staff = state.staff_by_skill("General") or state.staff_by_skill("Step-down")
    if gen_staff:
        from_skill = gen_staff[0].skill_level
        crit_before = len(state.staff_by_skill("Critical-care"))
        staff_id = engine.float_staff(from_skill, "Critical-care")
        assert staff_id is not None
        assert len(state.staff_by_skill("Critical-care")) == crit_before + 1
        assert engine.resource_interventions["float_staff"] == 1


def test_resource_agent_inference_save_load(tmp_path):
    agent = ResourceManagerAgent()
    obs = np.array([0.5, 0.2, 0.5, 0.2, 0.3, 0.8, 0.6, 1.0], dtype=np.float32)

    q = agent.q_values(obs)
    assert q.shape == (4,)
    action = agent.predict(obs)
    assert action in (0, 1, 2, 3)

    save_path = tmp_path / "resource_agent.npz"
    agent.save(save_path)
    loaded = ResourceManagerAgent.load(save_path)
    np.testing.assert_allclose(agent.W, loaded.W)
    np.testing.assert_allclose(agent.b, loaded.b)
    assert loaded.predict(obs) == action


def test_three_agent_marl_step():
    base_env = CareGridHospitalEnv(
        observation_version=2,
        max_episode_days=2.0,
        shortage_scenario="equipment_shortage",
    )
    ma_env = CareGridMAEnv(base_env=base_env, macro_interval=5)
    surge_obs, info = ma_env.reset(seed=7)

    assert surge_obs.shape == (6,)
    res_obs = info["resource_obs"]
    assert res_obs.shape == (8,)

    res_mask = ma_env.valid_resource_actions()
    assert res_mask[RESOURCE_HOLD]
    assert res_mask[RESOURCE_MOBILIZE_VENT]

    # Joint step with (SURGE, MOBILIZE_VENTILATOR)
    next_obs, reward, term, trunc, step_info = ma_env.step((MODE_SURGE, RESOURCE_MOBILIZE_VENT))
    assert next_obs.shape == (6,)
    assert step_info["mode"] == "SURGE"
    assert step_info["resource_action"] == "MOBILIZE_VENTILATOR"
    assert step_info["resource_intervened"] is True
    assert isinstance(reward, float)


def test_float_penalty_increases_above_fatigue_threshold():
    obs = np.zeros(8, dtype=np.float32)
    fresh, tired = ResourceManagerAgent(), ResourceManagerAgent()
    fresh.update(obs, RESOURCE_FLOAT_STAFF, 0, obs, True, fatigue=.7)
    tired.update(obs, RESOURCE_FLOAT_STAFF, 0, obs, True, fatigue=1.0)
    assert tired.q_values(obs)[RESOURCE_FLOAT_STAFF] < fresh.q_values(obs)[RESOURCE_FLOAT_STAFF]


def test_repeated_floating_and_budget_reset():
    state = load_hospital_state("data/synthetic", start_empty=True)
    state.current_time = datetime(2026, 1, 1, 22)
    engine = SimulationEngine(state, [])
    for _ in range(5):
        assert engine.float_staff()
    assert np.isclose(state.nurse_fatigue_index, .75)
    bed = state.beds_by_type("ICU")[0]
    bed.status = "CLEANING"
    state.turnaround_overtime_minutes = 290
    assert engine.expedite_cleaning() == 0
    assert state.turnaround_overtime_minutes == 290
    engine._advance_clock(state.current_time + timedelta(hours=2))
    assert np.isclose(state.nurse_fatigue_index, .71)
    assert state.turnaround_overtime_minutes == 0
    assert engine.expedite_cleaning() == 1
    assert state.turnaround_overtime_minutes == 15
