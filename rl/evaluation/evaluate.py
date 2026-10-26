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
)


def evaluate_policy(policy: Policy, patients: Sequence, *, drain_days: float = 7.0,
                    los_predictor: Any = None, name: str = "policy",
                    data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Run one episode over `patients` and return the standard metrics.

    The episode lasts until `drain_days` after the last arrival; patients still
    waiting then are reported as such. Utilization is measured between the first and
    last arrival (same window as experiments/run_experiment.py)."""
    arrivals = [p.arrival_time for p in patients]
    start, last = min(arrivals), max(arrivals)
    horizon_days = (last - start).total_seconds() / 86400 + drain_days

    collector = MetricsCollector(window_start=start, window_end=last)
    env = CareGridHospitalEnv(data_dir=data_dir, max_episode_days=horizon_days,
                              los_predictor=los_predictor)
    obs, _ = env.reset(seed=0, options={"patients": list(patients),
                                        "on_tick": collector.on_tick})
    total_reward, decisions, invalid = 0.0, 0, 0
    while True:
        obs, reward, terminated, truncated, info = env.step(policy(obs, env))
        total_reward += reward
        decisions += 1
        invalid += info.get("invalid_reason") is not None
        if terminated or truncated:
            break
    result = {
        "policy": name,
        "decisions": decisions,
        "invalid_actions": int(invalid),
        "episode_return": round(total_reward, 3),
        "metrics": compute_metrics(env.engine, collector,
                                   as_of=start + timedelta(days=horizon_days)),
    }
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
        print(f"  {key:34s} {v['mean']:>12.3f}  (std {v['std']:.3f})")
    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"eval__{args.policy}__{args.mode}__{datetime.now():%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(result, indent=2))
        print(f"Saved: {out}")


if __name__ == "__main__":
    main()
