"""
CareGrid-RL: diagnostic tool for comparing agent behaviour vs baselines (Phase 8)

Prints action distributions, WAIT-with-feasible-bed rates, per-acuity waits, and
(when a trained agent is provided) Q-value statistics (mean/min/max Q per action,
max Q-spread per decision).

Usage (from the repo root):
    python -m rl.evaluation.diagnose --streams 20 --split val
    python -m rl.evaluation.diagnose --agent rl/agents/models/dqn_v1_s0/best.zip --streams 20
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from rl.evaluation.evaluate import evaluate_policy
from rl.evaluation.policies import (BASELINES, Policy, masked_greedy_policy,
                                    rule_based_policy, lowest_tier_first_policy,
                                    combined_heuristic_policy)
from simulator.patients.streams import (EVAL_SEEDS, MODES, VAL_CONFIRM_SEEDS,
                                        VAL_SEEDS, generate_stream)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "docs" / "results"

ACTION_NAMES = ["ICU", "STEP_DOWN", "WARD", "WAIT"]

# Policies always evaluated for comparison
REFERENCE_POLICIES = {
    "b1": rule_based_policy,
    "h1": lowest_tier_first_policy,
    "h3": combined_heuristic_policy,
}


def resolve_seeds(split: str, n_streams: int) -> Sequence[int]:
    """Return seeds for the given split."""
    pools = {"val": VAL_SEEDS, "val_confirm": VAL_CONFIRM_SEEDS, "eval": EVAL_SEEDS}
    if split not in pools:
        raise ValueError(f"Unknown split {split!r}; use val, val_confirm")
    pool = list(pools[split])
    if n_streams > len(pool):
        raise SystemExit(f"--split {split} has only {len(pool)} streams")
    return pool[:n_streams]


def run_diagnosis(
    agent_path: Optional[str],
    seeds: Sequence[int],
    modes: Sequence[str] = ("normal", "moderate_surge"),
    days: float = 30.0,
    drain_days: float = 7.0,
    los_predictor: Any = None,
) -> Dict[str, Any]:
    """Run all reference policies + agent on the same streams; return diagnostics."""
    policies: Dict[str, Policy] = dict(REFERENCE_POLICIES)

    agent_q_fn = None
    q_records: Dict[str, List[np.ndarray]] = {m: [] for m in modes}

    if agent_path:
        from stable_baselines3 import DQN
        from rl.agents.sb3_utils import sb3_q_fn
        model = DQN.load(agent_path, device="cpu")
        raw_q_fn = sb3_q_fn(model)

        current_mode = ["normal"]

        def tracking_agent_policy(obs: np.ndarray, env) -> int:
            q = np.array(raw_q_fn(obs), dtype=float).reshape(-1)
            q_records[current_mode[0]].append(q.copy())
            q_masked = q.copy()
            q_masked[~env.valid_actions()] = -np.inf
            return int(np.argmax(q_masked))

        policies["agent"] = tracking_agent_policy

    results: Dict[str, Any] = {}
    for mode in modes:
        if agent_path:
            current_mode[0] = mode
        results[mode] = {}
        for seed in seeds:
            stream = generate_stream(int(seed), days=days, mode=mode)
            for name, policy in policies.items():
                t0 = time.time()
                run = evaluate_policy(
                    policy, stream, drain_days=drain_days,
                    los_predictor=los_predictor, name=name,
                    record_actions=True,
                )
                run["stream_seed"] = int(seed)
                results[mode].setdefault(name, []).append(run)
                elapsed = time.time() - t0
                wt = run["metrics"].get("acuity_weighted_avg_wait_min", 0)
                print(f"  {mode:15s} seed {seed} {name:10s}  wt_wait={wt:8.1f}  "
                      f"still_waiting={run['metrics'].get('patients_still_waiting', 0)}  "
                      f"{elapsed:4.1f}s", flush=True)

    # Attach Q records if agent was run
    if agent_path:
        results["_q_records"] = q_records

    return results


def compute_diagnostics(results: Dict[str, Any]) -> Dict[str, Any]:
    """Compute summary diagnostics from raw results."""
    diag: Dict[str, Any] = {}
    q_records = results.get("_q_records", {})

    for mode in ("normal", "moderate_surge"):
        if mode not in results:
            continue
        by_policy = results[mode]
        mode_diag: Dict[str, Any] = {}
        for name, runs in by_policy.items():
            total_counts = {str(a): np.zeros(4) for a in range(1, 6)}
            total_wait_feasible = 0
            total_wait_feasible_by_acuity = {str(a): 0 for a in range(1, 6)}
            total_decisions = 0
            weighted_waits = []
            avg_waits = []
            still_waitings = []
            icu_utils = []
            acuity_waits = {str(a): [] for a in range(1, 6)}

            for r in runs:
                for a, counts in r.get("action_counts", {}).items():
                    total_counts[a] += np.array(counts)
                total_wait_feasible += r.get("wait_with_feasible_bed", 0)
                for a, c in r.get("wait_with_feasible_by_acuity", {}).items():
                    total_wait_feasible_by_acuity[a] += c
                total_decisions += r["decisions"]
                weighted_waits.append(r["metrics"]["acuity_weighted_avg_wait_min"])
                avg_waits.append(r["metrics"]["avg_wait_incl_unadmitted_min"])
                still_waitings.append(r["metrics"]["patients_still_waiting"])
                icu_utils.append(r["metrics"]["icu_utilization"])

                m_acuity = r["metrics"].get("avg_wait_by_acuity_min", {})
                for a in range(1, 6):
                    v = m_acuity.get(a) or m_acuity.get(str(a))
                    if v is not None:
                        acuity_waits[str(a)].append(v)

            # Normalize action distributions
            action_dist = {}
            for a, v in total_counts.items():
                s = v.sum()
                action_dist[a] = (v / s).round(4).tolist() if s > 0 else [0, 0, 0, 0]

            total_actions = sum(v.sum() for v in total_counts.values())
            wait_feasible_rate = (total_wait_feasible / total_actions) if total_actions > 0 else 0

            acuity_wait_means = {
                a: round(float(np.mean(vals)), 1) if vals else 0.0
                for a, vals in acuity_waits.items()
            }

            policy_stats = {
                "action_dist_per_acuity": action_dist,
                "wait_with_feasible_bed_total": int(total_wait_feasible),
                "wait_with_feasible_rate": round(wait_feasible_rate, 4),
                "wait_feasible_by_acuity": total_wait_feasible_by_acuity,
                "weighted_wait_mean": round(float(np.mean(weighted_waits)), 2),
                "weighted_wait_std": round(float(np.std(weighted_waits)), 2),
                "avg_wait_mean": round(float(np.mean(avg_waits)), 2),
                "still_waiting_mean": round(float(np.mean(still_waitings)), 2),
                "icu_util_mean": round(float(np.mean(icu_utils)), 4),
                "acuity_waits_mean": acuity_wait_means,
                "decisions_total": int(total_decisions),
            }

            # If agent, compute Q-value statistics
            if name == "agent" and mode in q_records and len(q_records[mode]) > 0:
                q_arr = np.array(q_records[mode])  # shape (N, 4)
                q_spreads = q_arr.max(axis=1) - q_arr.min(axis=1)
                policy_stats["q_stats"] = {
                    "mean_q_per_action": q_arr.mean(axis=0).round(3).tolist(),
                    "min_q_per_action": q_arr.min(axis=0).round(3).tolist(),
                    "max_q_per_action": q_arr.max(axis=0).round(3).tolist(),
                    "mean_q_spread": round(float(q_spreads.mean()), 3),
                    "max_q_spread": round(float(q_spreads.max()), 3),
                }

            mode_diag[name] = policy_stats

        diag[mode] = mode_diag

    return diag


def format_report(diag: Dict[str, Any], agent_path: Optional[str],
                  split: str, n_streams: int) -> str:
    """Format diagnostics as a markdown report."""
    lines = [
        "# Phase 8 DQN Diagnosis Report",
        "",
        f"_Generated: {datetime.now().isoformat(timespec='seconds')}_  ",
        f"_Split: **{split}** ({n_streams} streams per scenario)_  ",
        "",
    ]

    if agent_path:
        lines += [f"**Agent checkpoint**: `{agent_path}`", ""]

    for mode, by_policy in diag.items():
        lines += [f"## Scenario: {mode}", "",
                  "### 1. Summary Performance", "",
                  "| Policy | Weighted wait (min) | Avg wait (min) | Still waiting | ICU util | WAIT-feasible rate | Decisions |",
                  "|:-------|--------------------:|---------------:|--------------:|---------:|-------------------:|----------:|"]
        for name, d in by_policy.items():
            lines.append(
                f"| **{name}** | {d['weighted_wait_mean']:.1f} ± {d['weighted_wait_std']:.1f} | "
                f"{d['avg_wait_mean']:.1f} | {d['still_waiting_mean']:.1f} | "
                f"{d['icu_util_mean']:.2%} | {d['wait_with_feasible_rate']:.4f} | "
                f"{d['decisions_total']} |"
            )
        lines.append("")

        # Per-acuity average waits
        lines += ["### 2. Wait by Acuity Level (minutes)", "",
                  "| Policy | Acuity 1 | Acuity 2 | Acuity 3 | Acuity 4 | Acuity 5 |",
                  "|:-------|---------:|---------:|---------:|---------:|---------:|"]
        for name, d in by_policy.items():
            aw = d.get("acuity_waits_mean", {})
            lines.append(
                f"| {name} | {aw.get('1', 0):.1f} | {aw.get('2', 0):.1f} | "
                f"{aw.get('3', 0):.1f} | {aw.get('4', 0):.1f} | {aw.get('5', 0):.1f} |"
            )
        lines.append("")

        # Action distribution per acuity
        lines += ["### 3. Action Distribution per Acuity Level", ""]
        for name, d in by_policy.items():
            lines += [f"#### {name}", "",
                      "| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |",
                      "|:-------|--------:|--------------:|---------:|---------:|---------------:|"]
            for a in range(1, 6):
                dist = d["action_dist_per_acuity"][str(a)]
                wf = d["wait_feasible_by_acuity"].get(str(a), 0)
                lines.append(
                    f"| Acuity {a} | {dist[0]:.3f} | {dist[1]:.3f} | {dist[2]:.3f} | "
                    f"{dist[3]:.3f} | {wf} |"
                )
            lines.append("")

        # Q-statistics if present
        if "agent" in by_policy and "q_stats" in by_policy["agent"]:
            qs = by_policy["agent"]["q_stats"]
            lines += ["### 4. Agent Q-Value Statistics", "",
                      f"- **Mean Q-spread per decision**: `{qs['mean_q_spread']}`  ",
                      f"- **Max Q-spread per decision**: `{qs['max_q_spread']}`  ",
                      "",
                      "| Action | Mean Q | Min Q | Max Q |",
                      "|:-------|-------:|------:|------:|"]
            for idx, act in enumerate(ACTION_NAMES):
                lines.append(
                    f"| {act} ({idx}) | {qs['mean_q_per_action'][idx]:.3f} | "
                    f"{qs['min_q_per_action'][idx]:.3f} | {qs['max_q_per_action'][idx]:.3f} |"
                )
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnose DQN agent behaviour vs baselines")
    ap.add_argument("--agent", default="", help="path to trained DQN .zip file")
    ap.add_argument("--streams", type=int, default=20,
                    help="number of streams per mode")
    ap.add_argument("--split", choices=("val", "val_confirm"), default="val")
    ap.add_argument("--modes", default="normal,moderate_surge")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--drain-days", type=float, default=7.0)
    ap.add_argument("--out", default="", help="output markdown path (default: docs/results/phase8_diagnosis.md)")
    args = ap.parse_args()

    seeds = resolve_seeds(args.split, args.streams)
    modes = [m for m in args.modes.split(",") if m]

    from ml.los.predictor import LOSPredictor
    predictor = LOSPredictor.load()

    agent_path = args.agent or None
    print(f"Running diagnosis: {len(seeds)} streams x {len(modes)} modes, "
          f"policies: b1, h1, h3{', agent' if agent_path else ''}", flush=True)

    results = run_diagnosis(agent_path, seeds, modes, args.days, args.drain_days, predictor)
    diag = compute_diagnostics(results)
    report = format_report(diag, agent_path, args.split, args.streams)

    out_path = Path(args.out) if args.out else RESULTS_DIR / "phase8_diagnosis.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nSaved report to: {out_path}")

    # Print summary to stdout
    for mode, by_policy in diag.items():
        print(f"\n=== {mode} ===")
        for name, d in by_policy.items():
            print(f"  {name:10s}  wt_wait={d['weighted_wait_mean']:8.1f}  "
                  f"still_waiting={d['still_waiting_mean']:5.1f}  "
                  f"wait_feasible_rate={d['wait_with_feasible_rate']:.4f}")


if __name__ == "__main__":
    main()
