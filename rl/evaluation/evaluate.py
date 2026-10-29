"""
CareGrid-RL: policy evaluation on the Gymnasium environment (Phase 7b)

Every policy -- the rule-based baseline today, DQN / MARL later -- is scored by the
SAME code: run an episode through CareGridHospitalEnv with a MetricsCollector
attached, then compute_metrics(). Policies therefore differ only in the decisions
they make, never in how they are measured.

Waits of patients who are never admitted are counted (as waiting until the end of
the evaluation horizon, the same instant for every policy), so a policy cannot look
good by leaving hard patients in the queue or by ending the episode early.

Usage (from the repo root):
    python -m rl.evaluation.evaluate --policy rule_based --mode normal --streams 5
    python -m rl.evaluation.evaluate --policy random --mode severe_surge --days 14 --save
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from rl.environment.hospital_env import CareGridHospitalEnv
from rl.environment.rewards import DEFAULT_ACUITY_WEIGHTS
from rl.evaluation.policies import BASELINES, Policy
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics
from simulator.patients.streams import EVAL_SEEDS, MODES, generate_stream

RESULTS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"

# Headline numbers aggregated across streams.
SUMMARY_KEYS = (
    "avg_wait_incl_unadmitted_min", "p90_wait_incl_unadmitted_min", "avg_wait_min",
    "icu_utilization", "step_down_utilization", "ward_utilization",
    "overall_bed_utilization", "bed_turnover_per_bed_per_day",
    "patients_still_waiting", "peak_waiting_queue",
    "acuity_weighted_avg_wait_min", "critical_avg_wait_min", "low_acuity_isolation_avg_wait_min",
)


def wait_group_metrics(patients, as_of, weights=None) -> Dict[str, Any]:
    """Waiting-time metrics that depend on WHO waited (all censored at `as_of`: a patient
    never admitted counts as waiting until then, identically for every policy).

    acuity_weighted_avg_wait_min   sum(w * wait) / sum(w): the training objective
    critical_avg_wait_min          acuity 4-5
    low_acuity_isolation_avg_wait_min   acuity 1-2 needing isolation (None if none exist)"""
    weights = weights or DEFAULT_ACUITY_WEIGHTS
    rows = []
    for p in patients:
        if p.arrival_time > as_of:
            continue
        end = p.admission_time if p.admission_time is not None else as_of
        rows.append((p, max((end - p.arrival_time).total_seconds() / 60.0, 0.0)))

    def mean(selected):
        return round(sum(w for _, w in selected) / len(selected), 2) if selected else None

    total_w = sum(weights[p.acuity] for p, _ in rows)
    weighted = (sum(weights[p.acuity] * w for p, w in rows) / total_w) if total_w else 0.0
    return {
        "acuity_weighted_avg_wait_min": round(weighted, 2),
        "critical_avg_wait_min": mean([r for r in rows if r[0].acuity >= 4]),
        "low_acuity_isolation_avg_wait_min": mean(
            [r for r in rows if r[0].acuity <= 2 and r[0].isolation_required]),
    }


def evaluate_policy(policy: Policy, patients: Sequence, *, drain_days: float = 7.0,
                    los_predictor: Any = None, name: str = "policy",
                    data_dir: Optional[str] = None,
                    record_actions: bool = False) -> Dict[str, Any]:
    """Run one episode over `patients` and return the standard metrics.

    The episode lasts until `drain_days` after the last arrival; patients still
    waiting then are reported as such. Utilization is measured between the first and
    last arrival (same window as experiments/run_experiment.py).

    record_actions=True adds result['action_counts']: for each acuity '1'..'5' how often
    each action [ICU, STEP_DOWN, WARD, WAIT] was chosen (what the policy actually does)."""
    arrivals = [p.arrival_time for p in patients]
    start, last = min(arrivals), max(arrivals)
    horizon_days = (last - start).total_seconds() / 86400 + drain_days

    collector = MetricsCollector(window_start=start, window_end=last)
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=horizon_days,
                              los_predictor=los_predictor)
    obs, _ = env.reset(seed=0, options={"patients": list(patients),
                                        "on_tick": collector.on_tick})
    total_reward, decisions, invalid = 0.0, 0, 0
    action_counts = {str(a): [0, 0, 0, 0] for a in range(1, 6)}
    while True:
        action = policy(obs, env)
        if record_actions and env.current_patient is not None:
            action_counts[str(env.current_patient.acuity)][int(action)] += 1
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        decisions += 1
        invalid += info.get("invalid_reason") is not None
        if terminated or truncated:
            break
    as_of = start + timedelta(days=horizon_days)
    metrics = compute_metrics(env.engine, collector, as_of=as_of)
    metrics.update(wait_group_metrics(env.engine.patients.values(), as_of))
    result = {
        "policy": name,
        "decisions": decisions,
        "invalid_actions": int(invalid),
        "episode_return": round(total_reward, 3),
        "metrics": metrics,
    }
    if record_actions:
        result["action_counts"] = action_counts
    env.close()
    return result


def evaluate_on_streams(policy: Policy, *, seeds: Sequence[int] = tuple(EVAL_SEEDS[:5]),
                        days: float = 30.0, mode: str = "normal", drain_days: float = 7.0,
                        los_predictor: Any = None, name: str = "policy") -> Dict[str, Any]:
    """Evaluate on several held-out patient streams and aggregate (mean, std)."""
    runs: List[Dict[str, Any]] = []
    for seed in seeds:
        stream = generate_stream(seed, days=days, mode=mode)
        run = evaluate_policy(policy, stream, drain_days=drain_days,
                              los_predictor=los_predictor, name=name)
        run["stream_seed"] = int(seed)
        runs.append(run)

    def agg(values):
        arr = np.array([v for v in values if v is not None], dtype=float)
        if arr.size == 0:
            return {"mean": None, "std": None}
        return {"mean": round(float(arr.mean()), 4), "std": round(float(arr.std()), 4)}

    summary = {k: agg(r["metrics"][k] for r in runs) for k in SUMMARY_KEYS}
    summary["episode_return"] = agg(r["episode_return"] for r in runs)
    summary["invalid_actions"] = agg(r["invalid_actions"] for r in runs)
    summary["constraint_violations"] = agg(
        r["metrics"]["constraint_violations"]["total"] for r in runs)
    return {"policy": name, "mode": mode, "days": days, "streams": len(runs),
            "summary": summary, "runs": runs}


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a baseline policy on held-out streams")
    ap.add_argument("--policy", choices=sorted(BASELINES), default="rule_based")
    ap.add_argument("--mode", choices=MODES, default="normal")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--streams", type=int, default=5, help="number of held-out streams")
    ap.add_argument("--save", action="store_true", help="write JSON to experiments/results/")
    args = ap.parse_args()

    seeds = list(EVAL_SEEDS)[:args.streams]
    result = evaluate_on_streams(BASELINES[args.policy](), seeds=seeds, days=args.days,
                                 mode=args.mode, name=args.policy)
    print(f"Policy: {args.policy} | scenario: {args.mode} | {args.days:g} days | "
          f"{result['streams']} held-out streams (seeds {seeds[0]}..{seeds[-1]})")
    for key, v in result["summary"].items():
        if v["mean"] is None:
            print(f"  {key:34s} {'n/a':>12s}")
        else:
            print(f"  {key:34s} {v['mean']:>12.3f}  (std {v['std']:.3f})")
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"eval__{args.policy}__{args.mode}__{datetime.now():%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(result, indent=2))
        print(f"Saved: {out}")


if __name__ == "__main__":
    main()
