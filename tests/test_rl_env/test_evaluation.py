"""The evaluation harness: policies are measured exactly like the simulator baseline."""
from datetime import timedelta

import pytest

pytest.importorskip("gymnasium")

from rl.evaluation.evaluate import evaluate_on_streams, evaluate_policy
from rl.evaluation.policies import (always_wait_policy, make_random_policy, model_policy,
                                    rule_based_policy)
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics
from simulator.patients.streams import EVAL_SEEDS, generate_stream

PARITY_KEYS = (
    "patients_admitted", "patients_discharged", "patients_still_waiting", "avg_wait_min",
    "median_wait_min", "p90_wait_min", "max_wait_min", "pct_admitted_within_60min",
    "icu_utilization", "step_down_utilization", "ward_utilization",
    "overall_bed_utilization", "ventilator_utilization", "bed_turnover_per_bed_per_day",
    "peak_waiting_queue", "constraint_violations", "avg_wait_by_acuity_min",
)


def test_rule_policy_through_the_env_reproduces_the_simulator_baseline(data_dir, counting_predictor):
    """THE guarantee that makes RL-vs-baseline comparisons fair: with identical decisions,
    the environment + collector give identical metrics to SimulationEngine.run()."""
    # reference: the simulator's own rule-based run
    state = load_hospital_state(str(data_dir))
    patients = load_patients(str(data_dir))
    engine = SimulationEngine(state, patients)
    engine.seed_arrivals()
    arrivals = [p.arrival_time for p in patients]
    collector = MetricsCollector(min(arrivals), max(arrivals))
    engine.run(on_tick=collector.on_tick)
    expected = compute_metrics(engine, collector)

    # same patients, same rules, but driven step by step through the Gymnasium env
    result = evaluate_policy(rule_based_policy, load_patients(str(data_dir)), drain_days=40,
                             los_predictor=counting_predictor, data_dir=str(data_dir))
    got = result["metrics"]
    for key in PARITY_KEYS:
        assert got[key] == expected[key], key
    assert result["invalid_actions"] == 0


def test_unadmitted_patients_are_counted_not_hidden(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[0], days=3)
    r = evaluate_policy(always_wait_policy, stream, drain_days=1,
                        los_predictor=counting_predictor, data_dir=str(data_dir))["metrics"]
    assert r["patients_admitted"] == 0
    assert r["patients_still_waiting"] == len(stream)
    assert r["avg_wait_min"] == 0.0                          # the old metric would call this perfect
    assert r["avg_wait_incl_unadmitted_min"] > 60            # the honest metric does not


def test_censoring_uses_the_same_end_time_for_every_policy(data_dir, counting_predictor):
    """Never admitting anyone ends the episode early (no events left); the metric must
    still measure the wait until the common horizon end, not until that early stop."""
    stream = generate_stream(EVAL_SEEDS[4], days=3)
    r = evaluate_policy(always_wait_policy, stream, drain_days=2,
                        los_predictor=counting_predictor, data_dir=str(data_dir))["metrics"]
    start = min(p.arrival_time for p in stream)
    last = max(p.arrival_time for p in stream)
    end = start + (last - start) + timedelta(days=2)
    expected = sum((end - p.arrival_time).total_seconds() / 60 for p in stream) / len(stream)
    assert r["avg_wait_incl_unadmitted_min"] == pytest.approx(expected, abs=0.01)


def test_baseline_beats_the_sanity_floors(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[1], days=7)
    kw = dict(drain_days=3, los_predictor=counting_predictor, data_dir=str(data_dir))
    rule = evaluate_policy(rule_based_policy, stream, **kw)
    never = evaluate_policy(always_wait_policy, stream, **kw)
    rand = evaluate_policy(make_random_policy(0), stream, **kw)
    wait = lambda r: r["metrics"]["avg_wait_incl_unadmitted_min"]
    assert wait(rule) < wait(rand) < wait(never)
    # random play also pays invalid-action penalties, so only the baseline's lead is required
    assert rule["episode_return"] > rand["episode_return"]
    assert rule["episode_return"] > never["episode_return"]
    assert rule["invalid_actions"] == 0 and rand["invalid_actions"] > 0


def test_evaluation_is_deterministic_and_does_not_mutate_the_input(data_dir, counting_predictor):
    stream = generate_stream(EVAL_SEEDS[2], days=4)
    before = [(p.status, p.admission_time) for p in stream]
    kw = dict(drain_days=2, los_predictor=counting_predictor, data_dir=str(data_dir))
    a = evaluate_policy(rule_based_policy, stream, **kw)
    b = evaluate_policy(rule_based_policy, stream, **kw)
    assert a == b
    assert [(p.status, p.admission_time) for p in stream] == before


def test_evaluate_on_streams_aggregates_across_held_out_seeds(counting_predictor):
    out = evaluate_on_streams(rule_based_policy, seeds=list(EVAL_SEEDS)[:3], days=4, drain_days=2,
                              los_predictor=counting_predictor, name="rule_based")
    assert out["streams"] == 3 and [r["stream_seed"] for r in out["runs"]] == list(EVAL_SEEDS)[:3]
    for key in ("avg_wait_incl_unadmitted_min", "icu_utilization", "episode_return",
                "constraint_violations"):
        assert set(out["summary"][key]) == {"mean", "std"}
    assert out["summary"]["constraint_violations"]["mean"] == 0


def test_model_policy_wraps_any_predict_model(data_dir, counting_predictor):
    class AlwaysWard:
        def predict(self, obs, deterministic=True):
            return [2], None

    stream = generate_stream(EVAL_SEEDS[3], days=2)
    r = evaluate_policy(model_policy(AlwaysWard()), stream, drain_days=1,
                        los_predictor=counting_predictor, data_dir=str(data_dir))
    assert r["decisions"] > 0
