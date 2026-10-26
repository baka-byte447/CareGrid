"""Phase 7b: LOS caching, isolation-aware observation, fresh streams, tick hook."""
from datetime import datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from rl.environment.hospital_env import (OBSERVATION_FEATURES, WAIT_ACTION,
                                         CareGridHospitalEnv)
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.state import Bed, HospitalState
from simulator.patients.patient import Patient
from simulator.patients.streams import StreamSampler

T0 = datetime(2026, 1, 1, 8, 0, 0)
IDX = {name: i for i, name in enumerate(OBSERVATION_FEATURES)}


def patient(pid, acuity=1, arrival=T0, iso=False, vent=False):
    return Patient(pid, "18-64", acuity, "GENERAL", 2.0, iso, vent, arrival)


# ---------- LOS estimates are computed once per episode, not once per step ----------

def test_los_is_batched_once_per_reset(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    env.reset(seed=1, options={"patients": [patient("a"), patient("b", arrival=T0 + timedelta(hours=1))]})
    for _ in range(3):
        if env.current_patient is None:
            break
        env.step(WAIT_ACTION)
    assert counting_predictor.predict_many_calls == 1
    assert counting_predictor.predict_calls == 0


def test_predictors_without_predict_many_still_work(data_dir):
    class OnlyPredict:
        calls = 0

        def predict(self, p):
            OnlyPredict.calls += 1
            return 4.0

    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=OnlyPredict())
    obs, _ = env.reset(seed=1, options={"patients": [patient("a"), patient("b")]})
    assert OnlyPredict.calls == 2                       # once per patient, up front
    assert obs[IDX["los_estimate"]] == pytest.approx(0.4)
    env.step(WAIT_ACTION)
    assert OnlyPredict.calls == 2                       # not again per step


def test_observation_never_contains_the_true_stay(data_dir, counting_predictor):
    counting_predictor.value = 7.0
    p = patient("a")
    p.predicted_los = 1.0                               # the hidden true stay
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    obs, _ = env.reset(seed=1, options={"patients": [p]})
    assert obs[IDX["los_estimate"]] == pytest.approx(0.7)


# ---------- observation: isolation-bed availability and queue severity ----------

def test_isolation_bed_availability_is_observed_per_tier(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    obs, _ = env.reset(seed=1, options={"patients": [patient("a")]})
    assert obs[IDX["ward_isolation_beds_available"]] == 1.0

    ward_iso = [b for b in env.state.beds_by_type("WARD") if b.isolation_capable]
    assert ward_iso, "the demo hospital has isolation-capable ward beds"
    for b in ward_iso[:-1]:
        b.status = "OCCUPIED"
    obs = env._observation()
    assert obs[IDX["ward_isolation_beds_available"]] == pytest.approx(1 / len(ward_iso))
    ward_iso[-1].status = "OCCUPIED"
    obs = env._observation()
    assert obs[IDX["ward_isolation_beds_available"]] == 0.0
    # other tiers and the plain availability ratio are unaffected by the isolation signal
    assert obs[IDX["icu_isolation_beds_available"]] == 1.0
    assert obs[IDX["ward_beds_available"]] > 0.0


def test_tier_without_isolation_beds_reports_zero(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    env.reset(seed=1, options={"patients": [patient("a")]})
    for b in env.state.beds_by_type("STEP_DOWN"):
        b.isolation_capable = False
    assert env._observation()[IDX["step_down_isolation_beds_available"]] == 0.0


def test_critical_share_of_the_waiting_queue(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    pts = [patient("crit", acuity=5, arrival=T0), patient("mild", acuity=1, arrival=T0 + timedelta(minutes=5))]
    obs, _ = env.reset(seed=1, options={"patients": pts})
    assert obs[IDX["critical_share_of_queue"]] == 0.0   # nobody waiting yet
    obs, *_ = env.step(WAIT_ACTION)                     # the critical patient waits
    assert env.current_patient.patient_id == "mild"
    assert obs[IDX["critical_share_of_queue"]] == 1.0


def test_all_observations_stay_inside_the_declared_space(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=3, los_predictor=counting_predictor,
                              patient_source=StreamSampler(days=3))
    obs, _ = env.reset(seed=3)
    rng = np.random.default_rng(0)
    for _ in range(300):
        assert env.observation_space.contains(obs)
        obs, _, terminated, truncated, _ = env.step(int(rng.integers(4)))
        if terminated or truncated:
            break


# ---------- fresh streams per episode ----------

def test_patient_source_gives_a_new_stream_each_reset_but_is_reproducible(data_dir, counting_predictor):
    sampler = StreamSampler(days=2)
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=2, los_predictor=counting_predictor,
                              patient_source=sampler)

    def ids_and_times(seed):
        env.reset(seed=seed)
        return [(p.patient_id, p.arrival_time) for p in env._patients.values()]

    a1, a2, b = ids_and_times(11), ids_and_times(11), ids_and_times(12)
    assert a1 == a2
    assert a1 != b


def test_explicit_patients_take_priority_over_the_source(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor,
                              patient_source=StreamSampler(days=2))
    env.reset(seed=1, options={"patients": [patient("only-one")]})
    assert list(env._patients) == ["only-one"]


# ---------- metrics hook in external-decision mode ----------

def test_tick_hook_fires_after_events_and_after_decisions(data_dir):
    state = HospitalState(
        beds={"W1": Bed("W1", "WARD", "A", "AVAILABLE", False)}, equipment={}, current_time=T0)
    p = patient("p1", acuity=1)
    ticks = []
    engine = SimulationEngine(state, [p])
    engine.enable_external_decisions(on_tick=lambda s: ticks.append(
        (s.current_time, s.beds["W1"].status, len(s.waiting_queue))))
    engine.seed_arrivals()
    assert engine.advance_to_decision() == "p1"
    n_after_arrival = len(ticks)
    assert n_after_arrival >= 1

    from simulator.hospital.allocation_rules import AllocationDecision
    engine.admit_pending_patient(AllocationDecision("W1"))
    assert ticks[-1][1] == "OCCUPIED"                   # tick saw the admission
    assert len(ticks) == n_after_arrival + 1

    engine.advance_to_decision()                        # discharge + cleaning events
    statuses = [t[1] for t in ticks]
    assert "CLEANING" in statuses and statuses[-1] == "AVAILABLE"


def test_tick_hook_is_optional(data_dir):
    state = HospitalState(beds={"W1": Bed("W1", "WARD", "A", "AVAILABLE", False)}, current_time=T0)
    engine = SimulationEngine(state, [patient("p1")])
    engine.enable_external_decisions()                  # no callback
    engine.seed_arrivals()
    assert engine.advance_to_decision() == "p1"
