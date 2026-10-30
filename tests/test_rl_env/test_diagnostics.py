"""Tests for PR-1 diagnostics: VAL_CONFIRM_SEEDS, record_actions, wait_with_feasible_bed."""
import pytest

pytest.importorskip("gymnasium")

from rl.evaluation.evaluate import evaluate_policy
from rl.evaluation.policies import (always_wait_policy, combined_heuristic_policy,
                                    make_random_policy, rule_based_policy)
from simulator.patients.streams import (EVAL_SEEDS, TRAIN_SEEDS, VAL_CONFIRM_SEEDS,
                                        VAL_SEEDS, generate_stream)


def test_val_confirm_seeds_are_disjoint_from_everything():
    """VAL_CONFIRM_SEEDS must not overlap with any other seed range."""
    confirm = set(VAL_CONFIRM_SEEDS)
    assert len(confirm) == 20
    assert not confirm.intersection(TRAIN_SEEDS)
    assert not confirm.intersection(VAL_SEEDS)
    assert not confirm.intersection(EVAL_SEEDS)
    assert not confirm.intersection({42, 1001, 2002})


def test_val_confirm_seeds_range():
    """VAL_CONFIRM_SEEDS spans 81000..81019."""
    assert VAL_CONFIRM_SEEDS == range(81_000, 81_020)


def test_record_actions_off_by_default(data_dir, counting_predictor):
    """When record_actions is not set, action_counts / wait_with_feasible are absent."""
    stream = generate_stream(EVAL_SEEDS[0], days=2)
    result = evaluate_policy(rule_based_policy, stream, drain_days=1,
                             los_predictor=counting_predictor, data_dir=str(data_dir))
    assert "action_counts" not in result
    assert "wait_with_feasible_bed" not in result


def test_record_actions_on_returns_action_counts(data_dir, counting_predictor):
    """record_actions=True produces per-acuity action counts."""
    stream = generate_stream(EVAL_SEEDS[0], days=3)
    result = evaluate_policy(rule_based_policy, stream, drain_days=1,
                             los_predictor=counting_predictor, data_dir=str(data_dir),
                             record_actions=True)
    assert "action_counts" in result
    counts = result["action_counts"]
    assert set(counts.keys()) == {"1", "2", "3", "4", "5"}
    for a in counts.values():
        assert len(a) == 4
        assert all(isinstance(x, int) for x in a)
    total = sum(sum(a) for a in counts.values())
    assert total > 0  # at least some decisions were made


def test_rule_based_has_zero_wait_with_feasible(data_dir, counting_predictor):
    """The rule-based policy never WAITs when a feasible bed exists (by construction)."""
    stream = generate_stream(EVAL_SEEDS[0], days=5)
    result = evaluate_policy(rule_based_policy, stream, drain_days=2,
                             los_predictor=counting_predictor, data_dir=str(data_dir),
                             record_actions=True)
    assert result.get("wait_with_feasible_bed", 0) == 0


def test_always_wait_has_nonzero_wait_with_feasible(data_dir, counting_predictor):
    """always_wait policy WAITs even when beds are free, so wait_with_feasible > 0."""
    stream = generate_stream(EVAL_SEEDS[0], days=3)
    result = evaluate_policy(always_wait_policy, stream, drain_days=1,
                             los_predictor=counting_predictor, data_dir=str(data_dir),
                             record_actions=True)
    assert result["wait_with_feasible_bed"] > 0
    assert result["wait_with_feasible_by_acuity"] is not None
    # At least some acuity levels should have feasible waits
    total = sum(result["wait_with_feasible_by_acuity"].values())
    assert total == result["wait_with_feasible_bed"]


def test_h3_has_zero_wait_with_feasible(data_dir, counting_predictor):
    """H3 (combined heuristic) never WAITs when a feasible bed exists."""
    stream = generate_stream(EVAL_SEEDS[1], days=5)
    result = evaluate_policy(combined_heuristic_policy, stream, drain_days=2,
                             los_predictor=counting_predictor, data_dir=str(data_dir),
                             record_actions=True)
    assert result.get("wait_with_feasible_bed", 0) == 0

