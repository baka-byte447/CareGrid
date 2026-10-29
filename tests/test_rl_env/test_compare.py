"""Phase 8 / T4: paired statistics, the comparison harness and the evaluation-seed guard."""
import numpy as np
import pytest

pytest.importorskip("gymnasium")

from rl.evaluation.compare import (action_distribution, compare_policies, paired_bootstrap,
                                   resolve_seeds, summarize, write_markdown_report)
from rl.evaluation.policies import (always_wait_policy, lowest_tier_first_policy,
                                    rule_based_policy)
from simulator.patients.streams import EVAL_SEEDS, VAL_SEEDS


def test_bootstrap_contains_the_true_mean_and_wins_when_all_diffs_are_negative():
    diffs = [-10, -12, -8, -11, -9, -13, -10, -9]
    r = paired_bootstrap(diffs, n_resamples=2000)
    assert r["mean"] == pytest.approx(np.mean(diffs))
    assert r["ci_low"] <= r["mean"] <= r["ci_high"]
    assert r["ci_high"] < 0 and r["win_rate"] == 1.0 and r["n"] == 8


def test_bootstrap_on_zero_and_mixed_differences():
    zero = paired_bootstrap([0.0, 0.0, 0.0], n_resamples=500)
    assert zero["mean"] == zero["ci_low"] == zero["ci_high"] == 0.0 and zero["win_rate"] == 0.0
    mixed = paired_bootstrap([-5, 5, -4, 6, -5, 5], n_resamples=2000)
    assert mixed["ci_low"] < 0 < mixed["ci_high"]            # no significant difference
    with pytest.raises(ValueError):
        paired_bootstrap([])


def test_bootstrap_is_reproducible_for_a_given_seed():
    d = list(np.random.default_rng(1).normal(size=20))
    assert paired_bootstrap(d, 1000, seed=3) == paired_bootstrap(d, 1000, seed=3)


def test_compare_policies_uses_identical_streams_for_every_policy(counting_predictor):
    pols = {"b1": rule_based_policy, "h1": lowest_tier_first_policy, "always_wait": always_wait_policy}
    seeds = {"normal": list(VAL_SEEDS)[:2]}
    res = compare_policies(pols, ["normal"], seeds, days=3, drain_days=2, los_predictor=counting_predictor)
    assert set(res["normal"]) == set(pols)
    for name in pols:
        assert [r["stream_seed"] for r in res["normal"][name]] == seeds["normal"]
    # same patients -> same number of arrivals handled
    assert len({r["metrics"]["patients_total"] for runs in res["normal"].values() for r in runs[:1]}) == 1
    # identical decisions on identical streams are reproducible
    again = compare_policies({"b1": rule_based_policy}, ["normal"], seeds, 3, 2, counting_predictor)
    assert again["normal"]["b1"][0]["metrics"] == res["normal"]["b1"][0]["metrics"]


def test_summary_and_markdown_report(counting_predictor, tmp_path):
    pols = {"b1": rule_based_policy, "h1": lowest_tier_first_policy, "always_wait": always_wait_policy}
    res = compare_policies(pols, ["normal"], {"normal": list(VAL_SEEDS)[:3]}, days=4, drain_days=2,
                           los_predictor=counting_predictor)
    summary = summarize(res, n_resamples=500)
    comp = summary["normal"]["comparisons"]
    assert "vs_b1" in comp["h1"]["acuity_weighted_avg_wait_min"]
    assert "vs_b1" not in comp["b1"].get("acuity_weighted_avg_wait_min", {})
    assert comp["always_wait"]["acuity_weighted_avg_wait_min"]["vs_b1"]["mean"] > 0   # never admitting is worse
    meta = {"split": "val", "seed_ranges": "80000-80019", "days": 4.0, "drain_days": 2.0,
            "created_at": "2026-01-01T00:00:00", "streams_per_mode": {"normal": 3}}
    out = tmp_path / "r.md"
    write_markdown_report(summary, meta, out, "Test report")
    text = out.read_text()
    for needle in ("# Test report", "## normal (3 streams)", "| b1 |", "| h1 |", "| always_wait |",
                   "Paired differences", "Weighted wait (min)"):
        assert needle in text


def test_action_distribution_rows_sum_to_one(counting_predictor):
    res = compare_policies({"b1": rule_based_policy}, ["normal"], {"normal": list(VAL_SEEDS)[:2]},
                           days=3, drain_days=2, los_predictor=counting_predictor)
    dist = action_distribution(res)["normal"]["b1"]
    for acuity, row in dist.items():
        assert sum(row) == pytest.approx(1.0, abs=0.01) or sum(row) == 0


# ---------- protecting the held-out evaluation streams ----------

def test_eval_split_requires_the_final_flag():
    with pytest.raises(SystemExit, match="--final"):
        resolve_seeds("eval", 5, final=False)
    assert list(resolve_seeds("eval", 5, final=True)) == list(EVAL_SEEDS)[:5]


def test_val_split_is_the_default_pool_and_bounded():
    assert list(resolve_seeds("val", 3, final=False)) == list(VAL_SEEDS)[:3]
    with pytest.raises(SystemExit):
        resolve_seeds("val", len(VAL_SEEDS) + 1, final=False)
