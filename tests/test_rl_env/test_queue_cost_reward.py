"""Phase 8 / T2: acuity-weighted queue-cost reward, valid-action mask, log-scaled queue feature."""
from datetime import datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from rl.environment.hospital_env import (OBSERVATION_FEATURES, QUEUE_LOG_CAP, WAIT_ACTION,
                                         CareGridHospitalEnv)
from rl.environment.rewards import DEFAULT_ACUITY_WEIGHTS, QueueCostTracker, validate_weights
from rl.evaluation.policies import always_wait_policy, make_random_policy, rule_based_policy
from simulator.patients.patient import Patient
from simulator.patients.streams import EVAL_SEEDS, generate_stream

T0 = datetime(2026, 1, 1, 8, 0, 0)
IDX = {name: i for i, name in enumerate(OBSERVATION_FEATURES)}
SCALE = 10.0


def patient(pid, acuity=1, arrival=T0, iso=False, vent=False):
    return Patient(pid, "18-64", acuity, "GENERAL", 2.0, iso, vent, arrival)


def make_env(data_dir, predictor, days, **kw):
    kw.setdefault("reward_mode", "queue_cost")
    kw.setdefault("invalid_action_penalty", 0.1)
    return CareGridHospitalEnv(data_dir=data_dir, max_episode_days=days, los_predictor=predictor, **kw)


def run(env, policy, stream):
    obs, _ = env.reset(seed=0, options={"patients": stream})
    total, invalid, queue_cost = 0.0, 0, 0.0
    while True:
        obs, r, term, trunc, info = env.step(policy(obs, env))
        total += r
        invalid += info.get("invalid_reason") is not None
        queue_cost += info.get("queue_cost", 0.0)
        if term or trunc:
            return total, invalid, queue_cost


def expected_cost_days(env, weights=DEFAULT_ACUITY_WEIGHTS):
    """Independent calculation from the final patient records."""
    end = env._end_time
    total = 0.0
    for p in env.engine.patients.values():
        if p.arrival_time > end:
            continue
        wait = (p.admission_time or end) - p.arrival_time
        total += weights[p.acuity] * wait.total_seconds() / 86400.0
    return total


def horizon_days(stream, drain=7.0):
    arrivals = [p.arrival_time for p in stream]
    return (max(arrivals) - min(arrivals)).total_seconds() / 86400 + drain


# ---------- the identity that ties reward to the metric ----------

@pytest.mark.parametrize("policy_factory", [lambda: rule_based_policy, lambda: make_random_policy(0)])
def test_episode_return_equals_the_acuity_weighted_wait(data_dir, counting_predictor, policy_factory):
    stream = generate_stream(EVAL_SEEDS[0], days=5)
    env = make_env(data_dir, counting_predictor, horizon_days(stream))
    total, invalid, _ = run(env, policy_factory(), stream)
    expected = -expected_cost_days(env) / SCALE - 0.1 * invalid
    assert total == pytest.approx(expected, abs=1e-6)


def test_never_admitting_is_charged_until_the_common_horizon_end(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[1], days=3)
    env = make_env(data_dir, counting_predictor, horizon_days(stream, drain=2))
    total, invalid, _ = run(env, always_wait_policy, stream)
    end = env._end_time
    expected = -sum(DEFAULT_ACUITY_WEIGHTS[p.acuity] * (end - p.arrival_time).total_seconds() / 86400
                    for p in stream) / SCALE
    assert invalid == 0
    assert total == pytest.approx(expected, abs=1e-6)


def test_info_queue_cost_matches_the_scaled_reward(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[2], days=4)
    env = make_env(data_dir, counting_predictor, horizon_days(stream))
    total, invalid, queue_cost = run(env, rule_based_policy, stream)
    assert invalid == 0
    assert total == pytest.approx(-queue_cost / SCALE, abs=1e-9)
    assert queue_cost == pytest.approx(expected_cost_days(env), abs=1e-6)


def test_custom_weights_and_scale_change_the_reward_proportionally(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[3], days=4)
    days = horizon_days(stream)
    base, _, _ = run(make_env(data_dir, counting_predictor, days), rule_based_policy, stream)
    doubled = {a: 2 * w for a, w in DEFAULT_ACUITY_WEIGHTS.items()}
    twice, _, _ = run(make_env(data_dir, counting_predictor, days, acuity_weights=doubled),
                      rule_based_policy, stream)
    half_scale, _, _ = run(make_env(data_dir, counting_predictor, days, reward_scale=5.0),
                           rule_based_policy, stream)
    assert twice == pytest.approx(2 * base, rel=1e-9)
    assert half_scale == pytest.approx(2 * base, rel=1e-9)


def test_caller_tick_hook_still_runs_in_queue_cost_mode(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[4], days=1)
    env = make_env(data_dir, counting_predictor, horizon_days(stream))
    ticks = []
    obs, _ = env.reset(seed=0, options={"patients": stream, "on_tick": lambda s: ticks.append(s.current_time)})
    env.step(WAIT_ACTION)
    assert len(ticks) > 0


def test_legacy_mode_is_unchanged_and_has_no_queue_cost(data_dir, counting_predictor):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=1, los_predictor=counting_predictor)
    assert env.reward_mode == "legacy"
    env.reset(seed=0, options={"patients": [patient("a")]})
    _, reward, _, _, info = env.step(2)                     # admit to a ward bed
    assert reward == pytest.approx(1.0)                     # admission_reward, zero wait
    assert "queue_cost" not in info


# ---------- configuration is validated ----------

def test_bad_reward_configuration_raises(data_dir, counting_predictor):
    with pytest.raises(ValueError):
        CareGridHospitalEnv(data_dir=data_dir, los_predictor=counting_predictor, reward_mode="nope")
    with pytest.raises(ValueError):
        CareGridHospitalEnv(data_dir=data_dir, los_predictor=counting_predictor, reward_scale=0)
    with pytest.raises(ValueError):
        validate_weights({1: 1, 2: 1, 3: 1, 4: 1})                  # acuity 5 missing
    with pytest.raises(ValueError):
        validate_weights({1: 1, 2: 1, 3: 1, 4: 1, 5: 0})            # not positive


def test_tracker_integrates_a_known_queue():
    class S:
        def __init__(self, t, q):
            self.current_time, self.waiting_queue = t, q

    pts = {"a": patient("a", acuity=5), "b": patient("b", acuity=3)}
    tr = QueueCostTracker(DEFAULT_ACUITY_WEIGHTS)
    tr.update(S(T0, []), pts)
    tr.update(S(T0 + timedelta(hours=12), ["a"]), pts)             # nobody waited before this
    tr.update(S(T0 + timedelta(hours=24), ["a", "b"]), pts)        # 'a' waited 12 h
    tr.close(T0 + timedelta(hours=48))                              # 'a','b' wait 24 h more
    # 8 * 0.5 + (8 + 2) * 1.0 = 14 weighted patient-days
    assert tr.pop() == pytest.approx(14.0)
    assert tr.pop() == 0.0


# ---------- valid-action mask ----------

def test_valid_actions_follow_the_hard_rules(data_dir, counting_predictor):
    env = make_env(data_dir, counting_predictor, 1)
    env.reset(seed=0, options={"patients": [patient("mild", acuity=1)]})
    assert env.valid_actions().tolist() == [False, False, True, True]     # ward + wait

    env.reset(seed=0, options={"patients": [patient("crit", acuity=5)]})
    assert env.valid_actions().tolist() == [True, False, False, True]     # ICU + wait
    for b in env.state.beds_by_type("ICU"):
        b.status = "OCCUPIED"
    assert env.valid_actions().tolist() == [False, False, False, True]    # only wait


def test_valid_actions_without_a_ventilator_allow_only_wait(data_dir, counting_predictor):
    env = make_env(data_dir, counting_predictor, 1)
    env.reset(seed=0, options={"patients": [patient("vent", acuity=5, vent=True)]})
    for e in env.state.equipment.values():
        if e.type == "VENTILATOR":
            e.status = "IN_USE"
    assert env.valid_actions().tolist() == [False, False, False, True]


def test_wait_is_always_valid_and_mask_is_safe_between_episodes(data_dir, counting_predictor):
    env = make_env(data_dir, counting_predictor, 1)
    env.reset(seed=0, options={"patients": [patient("p")]})
    while True:
        assert env.valid_actions()[WAIT_ACTION]
        _, _, term, trunc, _ = env.step(WAIT_ACTION)
        if term or trunc:
            break
    assert env.valid_actions().tolist() == [False, False, False, True]    # no current patient


def test_invalid_choice_is_exactly_wait_plus_penalty(data_dir, counting_predictor):
    """The property that justifies training WITHOUT masking (plan decision D11)."""
    pts = [patient("a", acuity=1), patient("b", acuity=1, arrival=T0 + timedelta(hours=3))]
    results = {}
    for name, action in (("wait", WAIT_ACTION), ("invalid", 0)):       # ICU is invalid for acuity 1
        env = make_env(data_dir, counting_predictor, 1)
        env.reset(seed=0, options={"patients": pts})
        _, r, _, _, info = env.step(action)
        results[name] = (r, info["waiting_count"])
    assert results["invalid"][0] == pytest.approx(results["wait"][0] - 0.1)
    assert results["invalid"][1] == results["wait"][1]


# ---------- log-scaled queue feature ----------

@pytest.mark.parametrize("n_waiting", [0, 3, 11, 118, 5000])
def test_queue_feature_is_log_scaled_and_independent_of_episode_size(data_dir, counting_predictor, n_waiting):
    patients = [patient("head")] + [patient(f"w{i}", acuity=3, arrival=T0 + timedelta(minutes=i + 1))
                                    for i in range(n_waiting)]
    env = make_env(data_dir, counting_predictor, 30)
    env.reset(seed=0, options={"patients": patients})
    env.state.waiting_queue = [f"w{i}" for i in range(n_waiting)]
    expected = min(np.log1p(n_waiting) / np.log1p(QUEUE_LOG_CAP), 1.0)
    assert env._observation()[IDX["waiting_queue_size"]] == pytest.approx(expected, abs=1e-6)


# ---------- next-decision mask reported for masked Bellman targets ----------

def test_info_reports_the_valid_actions_of_the_next_decision(data_dir, counting_predictor):
    pts = [patient("a", acuity=1), patient("b", acuity=5, arrival=T0 + timedelta(hours=1))]
    env = make_env(data_dir, counting_predictor, 2)
    _, info = env.reset(seed=0, options={"patients": pts})
    assert info["next_valid_actions"] == [False, False, True, True]          # patient 'a': ward + wait
    _, _, _, _, info = env.step(2)                                           # admit 'a' to a ward bed
    assert env.current_patient.patient_id == "b"
    assert info["next_valid_actions"] == env.valid_actions().tolist() == [True, False, False, True]
