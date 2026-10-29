"""Phase 8 / T3: heuristic baselines, masked greedy policy, weighted wait metrics."""
from datetime import datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from rl.environment.hospital_env import BED_ACTIONS, WAIT_ACTION, CareGridHospitalEnv
from rl.evaluation.evaluate import evaluate_on_streams, evaluate_policy, wait_group_metrics
from rl.evaluation.policies import (BASELINES, combined_heuristic_policy, lowest_tier_first_policy,
                                    masked_greedy_policy, protect_isolation_policy,
                                    rule_based_policy)
from simulator.patients.patient import Patient
from simulator.patients.streams import VAL_SEEDS, generate_stream

T0 = datetime(2026, 1, 1, 8, 0, 0)
HEURISTICS = {"h1": lowest_tier_first_policy, "h2": protect_isolation_policy,
              "h3": combined_heuristic_policy}


def patient(pid, acuity=1, arrival=T0, iso=False, vent=False):
    return Patient(pid, "18-64", acuity, "GENERAL", 2.0, iso, vent, arrival)


def env_with(data_dir, predictor, patients, days=1):
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=days, los_predictor=predictor)
    env.reset(seed=0, options={"patients": patients})
    return env


# ---------- registry ----------

def test_all_baselines_are_registered_with_aliases():
    assert {"b1", "rule_based", "h1_lowest_tier", "h2_protect_isolation", "h3_combined",
            "always_wait", "random"} <= set(BASELINES)
    assert BASELINES["b1"]() is BASELINES["rule_based"]()


# ---------- heuristic behaviour ----------

@pytest.mark.parametrize("name", sorted(HEURISTICS))
def test_heuristics_are_always_valid_and_safe(data_dir, counting_predictor, name):
    for seed in list(VAL_SEEDS)[:3]:
        r = evaluate_policy(HEURISTICS[name], generate_stream(seed, days=7), drain_days=3,
                            los_predictor=counting_predictor, data_dir=str(data_dir))
        assert r["invalid_actions"] == 0
        assert r["metrics"]["constraint_violations"]["total"] == 0


def test_h1_keeps_the_icu_free_for_critical_patients(data_dir, counting_predictor):
    """On held-out validation streams the cheapest-tier-first rule waits less for critical
    patients AND for the acuity-weighted average than the strict rule table."""
    kw = dict(drain_days=3, los_predictor=counting_predictor, data_dir=str(data_dir))
    for seed in list(VAL_SEEDS)[:3]:
        stream = generate_stream(seed, days=14)
        b1 = evaluate_policy(rule_based_policy, stream, **kw)["metrics"]
        h1 = evaluate_policy(lowest_tier_first_policy, stream, **kw)["metrics"]
        assert h1["critical_avg_wait_min"] < 0.5 * b1["critical_avg_wait_min"] or \
            h1["critical_avg_wait_min"] <= 5
        assert h1["acuity_weighted_avg_wait_min"] < b1["acuity_weighted_avg_wait_min"]


def test_h1_orders_tiers_cheapest_first(data_dir, counting_predictor):
    env = env_with(data_dir, counting_predictor, [patient("a4", acuity=4)])
    assert env.valid_actions()[0] and env.valid_actions()[1]            # ICU and step-down both free
    assert rule_based_policy(None, env) == BED_ACTIONS.index("ICU")     # B1: ICU first
    assert lowest_tier_first_policy(None, env) == BED_ACTIONS.index("STEP_DOWN")   # H1: conserve ICU


def test_h2_protects_the_scarce_ward_isolation_beds(data_dir, counting_predictor):
    env = env_with(data_dir, counting_predictor, [patient("a3", acuity=3, iso=True)])
    for bed in env.state.beds_by_type("STEP_DOWN"):
        if bed.isolation_capable:
            bed.status = "OCCUPIED"
    assert env.valid_actions()[BED_ACTIONS.index("WARD")]               # a ward isolation bed is free
    assert rule_based_policy(None, env) == BED_ACTIONS.index("WARD")    # B1 takes it
    assert protect_isolation_policy(None, env) == WAIT_ACTION           # H2 keeps it for acuity 1-2
    assert combined_heuristic_policy(None, env) == WAIT_ACTION


def test_heuristics_wait_when_nothing_fits(data_dir, counting_predictor):
    env = env_with(data_dir, counting_predictor, [patient("c", acuity=5)])
    for bed in env.state.beds_by_type("ICU"):
        bed.status = "OCCUPIED"
    for name, policy in HEURISTICS.items():
        assert policy(None, env) == WAIT_ACTION, name


# ---------- masked greedy policy ----------

def test_masked_policy_ignores_invalid_actions_even_when_q_prefers_them(data_dir, counting_predictor):
    env = env_with(data_dir, counting_predictor, [patient("mild", acuity=1)])   # valid: WARD, WAIT
    policy = masked_greedy_policy(lambda obs: np.array([100.0, 90.0, 1.0, 0.5]))
    assert policy(None, env) == 2                                          # best VALID action
    policy = masked_greedy_policy(lambda obs: np.array([100.0, 90.0, 0.2, 0.5]))
    assert policy(None, env) == WAIT_ACTION


def test_masked_policy_never_returns_an_invalid_action(data_dir, counting_predictor):
    rng = np.random.default_rng(0)
    policy = masked_greedy_policy(lambda obs: rng.normal(size=4) * 50)
    stream = generate_stream(VAL_SEEDS[5], days=4)
    result = evaluate_policy(policy, stream, drain_days=2, los_predictor=counting_predictor,
                             data_dir=str(data_dir))
    assert result["invalid_actions"] == 0
    assert result["metrics"]["constraint_violations"]["total"] == 0


# ---------- weighted / group wait metrics ----------

def _admitted(p, wait_min):
    p.admission_time = p.arrival_time + timedelta(minutes=wait_min)
    return p


def test_wait_group_metrics_known_values():
    as_of = T0 + timedelta(days=1)
    pts = [
        _admitted(patient("a", acuity=1), 100),                          # w=1
        _admitted(patient("b", acuity=5), 40),                           # w=8, critical
        patient("c", acuity=2, iso=True),                                # never admitted: waits 1440
        patient("late", acuity=3, arrival=T0 + timedelta(days=2)),       # arrives after as_of: ignored
    ]
    m = wait_group_metrics(pts, as_of)
    assert m["acuity_weighted_avg_wait_min"] == pytest.approx((1 * 100 + 8 * 40 + 1 * 1440) / 10, abs=0.01)
    assert m["critical_avg_wait_min"] == 40.0
    assert m["low_acuity_isolation_avg_wait_min"] == 1440.0


def test_wait_group_metrics_report_none_for_missing_groups():
    m = wait_group_metrics([_admitted(patient("a", acuity=3), 10)], T0 + timedelta(days=1))
    assert m["critical_avg_wait_min"] is None
    assert m["low_acuity_isolation_avg_wait_min"] is None


def test_evaluate_on_streams_summary_has_the_weighted_metrics(counting_predictor):
    out = evaluate_on_streams(rule_based_policy, seeds=list(VAL_SEEDS)[:2], days=3, drain_days=2,
                              los_predictor=counting_predictor)
    for key in ("acuity_weighted_avg_wait_min", "critical_avg_wait_min",
                "low_acuity_isolation_avg_wait_min"):
        assert key in out["summary"]
        assert set(out["summary"][key]) == {"mean", "std"}


def test_record_actions_counts_every_decision(data_dir, counting_predictor):
    stream = generate_stream(VAL_SEEDS[6], days=3)
    r = evaluate_policy(rule_based_policy, stream, drain_days=2, los_predictor=counting_predictor,
                        data_dir=str(data_dir), record_actions=True)
    counts = r["action_counts"]
    assert set(counts) == {"1", "2", "3", "4", "5"}
    assert sum(sum(v) for v in counts.values()) == r["decisions"]
    assert counts["5"][0] == sum(counts["5"][:3])        # critical patients only ever pick ICU (or wait)
