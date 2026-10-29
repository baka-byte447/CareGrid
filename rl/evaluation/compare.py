"""
CareGrid-RL: fair comparison of allocation policies (Phase 8)

Every policy is evaluated on the SAME patient streams (each stream is generated once per
scenario and seed) and scored by the SAME code (rl.evaluation.evaluate.evaluate_policy).
Differences between policies are then bootstrapped per stream (paired), which removes the
large stream-to-stream noise and gives an honest confidence interval.

Usage (from the repo root):
    # development, on validation streams
    python -m rl.evaluation.compare --policies b1,h1,h2,h3,random,always_wait --streams 20
    # the ONE final comparison on the held-out evaluation streams (guarded by --final)
    python -m rl.evaluation.compare --policies b1,h1,h2,h3 \
        --agent rl/agents/models/dqn_v1_s0/best.zip --split eval --final --streams 50

Report names: b1 = strict rule table, h1/h2/h3 = hand-written heuristics (see policies.py).
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from rl.evaluation.evaluate import evaluate_policy
from rl.evaluation.policies import BASELINES, Policy, masked_greedy_policy
from simulator.patients.streams import EVAL_SEEDS, MODES, VAL_SEEDS, generate_stream

REPO_ROOT = Path(__file__).resolve().parents[2]

POLICY_ALIASES = {
    "b1": "rule_based", "h1": "h1_lowest_tier", "h2": "h2_protect_isolation",
    "h3": "h3_combined", "random": "random", "always_wait": "always_wait",
}
HEURISTICS = ("h1", "h2", "h3")

# (key, label, decimals) columns of the main report table; lower is better for waits.
REPORT_METRICS = (
    ("acuity_weighted_avg_wait_min", "Weighted wait (min)", 1),
    ("avg_wait_incl_unadmitted_min", "Avg wait (min)", 1),
    ("critical_avg_wait_min", "Critical wait (min)", 1),
    ("low_acuity_isolation_avg_wait_min", "Low-acuity isolation wait (min)", 1),
    ("p90_wait_incl_unadmitted_min", "P90 wait (min)", 1),
    ("icu_utilization", "ICU util", 2),
    ("patients_still_waiting", "Still waiting", 1),
    ("peak_waiting_queue", "Peak queue", 1),
    ("invalid_actions", "Invalid actions", 1),
    ("constraint_violations", "Violations", 1),
)
PRIMARY_METRICS = ("acuity_weighted_avg_wait_min", "avg_wait_incl_unadmitted_min",
                   "critical_avg_wait_min")


# ----------------------------------------------------------------- statistics

def paired_bootstrap(diffs: Sequence[float], n_resamples: int = 10_000, seed: int = 0) -> Dict[str, float]:
    """Bootstrap the mean of per-stream differences (policy minus baseline).
    Returns mean, 95% CI and win_rate = share of streams where the policy is better
    (difference < 0, lower is better)."""
    diffs = np.asarray([d for d in diffs if d is not None], dtype=float)
    if diffs.size == 0:
        raise ValueError("diffs must not be empty")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diffs.size, size=(n_resamples, diffs.size))
    means = diffs[idx].mean(axis=1)
    return {
        "mean": float(diffs.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "win_rate": float((diffs < 0).mean()),
        "n": int(diffs.size),
    }


# --------------------------------------------------------------- running policies

def get_metric(run: Dict[str, Any], key: str):
    if key == "invalid_actions":
        return run["invalid_actions"]
    if key == "episode_return":
        return run["episode_return"]
    if key == "constraint_violations":
        return run["metrics"]["constraint_violations"]["total"]
    return run["metrics"].get(key)


def compare_policies(policies: Dict[str, Policy], modes: Sequence[str], seeds_by_mode: Dict[str, Sequence[int]],
                     days: float = 30.0, drain_days: float = 7.0, los_predictor: Any = None,
                     record_actions: bool = True, verbose: bool = False) -> Dict[str, Dict[str, List[dict]]]:
    """results[mode][policy_name] = list of evaluate_policy results aligned by stream seed."""
    results: Dict[str, Dict[str, List[dict]]] = {m: {name: [] for name in policies} for m in modes}
    for mode in modes:
        for seed in seeds_by_mode[mode]:
            stream = generate_stream(int(seed), days=days, mode=mode)   # generated ONCE, shared
            for name, policy in policies.items():
                t0 = time.time()
                run = evaluate_policy(policy, stream, drain_days=drain_days, los_predictor=los_predictor,
                                      name=name, record_actions=record_actions)
                run["stream_seed"] = int(seed)
                results[mode][name].append(run)
                if verbose:
                    print(f"  {mode:15s} seed {seed} {name:14s} {time.time() - t0:5.1f}s", flush=True)
    return results


# ------------------------------------------------------------------- summaries

def summarize(results: Dict[str, Dict[str, List[dict]]], heuristics: Sequence[str] = HEURISTICS,
              baseline: str = "b1", metrics: Sequence[str] = PRIMARY_METRICS,
              n_resamples: int = 10_000) -> Dict[str, Any]:
    """Per mode and policy: mean/std of every report metric, plus paired comparisons against
    the baseline and against the best heuristic (best = lowest mean, per metric)."""
    summary: Dict[str, Any] = {}
    for mode, by_policy in results.items():
        stats: Dict[str, Dict[str, Any]] = {}
        for name, runs in by_policy.items():
            stats[name] = {}
            keys = [k for k, _, _ in REPORT_METRICS] + ["episode_return"]
            for key in keys:
                vals = [v for v in (get_metric(r, key) for r in runs) if v is not None]
                stats[name][key] = ({"mean": float(np.mean(vals)), "std": float(np.std(vals))}
                                    if vals else {"mean": None, "std": None})
        comparisons: Dict[str, Dict[str, Any]] = {}
        present_h = [h for h in heuristics if h in by_policy]
        for name, runs in by_policy.items():
            comparisons[name] = {}
            for metric in metrics:
                values = {name: [get_metric(r, metric) for r in runs]}
                targets = {}
                if baseline in by_policy and name != baseline:
                    targets["vs_" + baseline] = baseline
                if present_h:
                    best = min(present_h, key=lambda h: _mean(by_policy[h], metric))
                    if name != best:
                        targets["vs_best_heuristic"] = best
                for label, ref in targets.items():
                    ref_vals = [get_metric(r, metric) for r in by_policy[ref]]
                    pairs = [(a, b) for a, b in zip(values[name], ref_vals) if a is not None and b is not None]
                    if pairs:
                        res = paired_bootstrap([a - b for a, b in pairs], n_resamples=n_resamples)
                        res["reference"] = ref
                        comparisons[name].setdefault(metric, {})[label] = res
        summary[mode] = {"stats": stats, "comparisons": comparisons}
    return summary


def _mean(runs: List[dict], metric: str) -> float:
    vals = [v for v in (get_metric(r, metric) for r in runs) if v is not None]
    return float(np.mean(vals)) if vals else float("inf")


# --------------------------------------------------------------------- reports

def _fmt(stat: Optional[dict], decimals: int) -> str:
    if not stat or stat["mean"] is None:
        return "n/a"
    return f"{stat['mean']:.{decimals}f} ± {stat['std']:.{decimals}f}"


def write_markdown_report(summary: Dict[str, Any], meta: Dict[str, Any], path: Path, title: str) -> None:
    lines = [f"# {title}", "",
             f"_Split: **{meta['split']}** (seeds {meta['seed_ranges']}), {meta['days']:g}-day streams, "
             f"{meta['drain_days']:g} days drain, generated {meta['created_at']}. Mean ± std across streams; "
             f"lower is better for waits. All policies were evaluated on identical streams._", ""]
    for mode, block in summary.items():
        n = meta["streams_per_mode"][mode]
        lines += [f"## {mode} ({n} streams)", "",
                  "| Policy | " + " | ".join(label for _, label, _ in REPORT_METRICS) + " |",
                  "|---|" + "---|" * len(REPORT_METRICS)]
        for name, stats in block["stats"].items():
            lines.append(f"| {name} | " + " | ".join(_fmt(stats[k], d) for k, _, d in REPORT_METRICS) + " |")
        lines += ["", "**Paired differences** (policy minus reference; negative = policy is better; "
                      "95% bootstrap CI; win = share of streams where the policy is better)", "",
                  "| Policy | Metric | vs | Mean diff | 95% CI | Win rate |", "|---|---|---|---|---|---|"]
        for name, per_metric in block["comparisons"].items():
            for metric, refs in per_metric.items():
                for label, r in refs.items():
                    lines.append(f"| {name} | {metric} | {r['reference']} | {r['mean']:.1f} | "
                                 f"[{r['ci_low']:.1f}, {r['ci_high']:.1f}] | {r['win_rate']:.0%} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def compact_runs(results: Dict[str, Dict[str, List[dict]]]) -> Dict[str, Any]:
    keep = [k for k, _, _ in REPORT_METRICS if k not in ("invalid_actions", "constraint_violations")]
    out: Dict[str, Any] = {}
    for mode, by_policy in results.items():
        out[mode] = {}
        for name, runs in by_policy.items():
            out[mode][name] = [{
                "seed": r["stream_seed"], "decisions": r["decisions"],
                "invalid_actions": r["invalid_actions"], "episode_return": r["episode_return"],
                "constraint_violations": r["metrics"]["constraint_violations"]["total"],
                **{k: r["metrics"].get(k) for k in keep},
            } for r in runs]
    return out


def action_distribution(results: Dict[str, Dict[str, List[dict]]]) -> Dict[str, Any]:
    """Behaviour analysis: how often each policy picks each action per acuity level."""
    out: Dict[str, Any] = {}
    for mode, by_policy in results.items():
        out[mode] = {}
        for name, runs in by_policy.items():
            total = {str(a): np.zeros(4) for a in range(1, 6)}
            for r in runs:
                for a, counts in r.get("action_counts", {}).items():
                    total[a] += np.array(counts)
            out[mode][name] = {a: (v / v.sum()).round(3).tolist() if v.sum() else [0, 0, 0, 0]
                               for a, v in total.items()}
    return out


# ------------------------------------------------------------------------- CLI

def resolve_seeds(split: str, n_streams: int, final: bool) -> Sequence[int]:
    """Validation streams for development; evaluation streams only with an explicit --final."""
    if split == "val":
        pool = list(VAL_SEEDS)
    elif split == "eval":
        if not final:
            raise SystemExit("The evaluation split is reserved for the final claim: add --final "
                             "(use --split val for development and tuning).")
        pool = list(EVAL_SEEDS)
    else:
        raise ValueError(f"unknown split {split!r}")
    if n_streams > len(pool):
        raise SystemExit(f"--split {split} has only {len(pool)} streams")
    return pool[:n_streams]


def load_agent_policy(path: str) -> Policy:
    from stable_baselines3 import DQN
    from rl.agents.sb3_utils import sb3_q_fn
    model = DQN.load(path, device="cpu")
    return masked_greedy_policy(sb3_q_fn(model))


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare allocation policies on identical streams")
    ap.add_argument("--policies", default="b1,h1,h2,h3,random,always_wait")
    ap.add_argument("--agent", default="", help="comma-separated paths to trained DQN .zip files")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--split", choices=("val", "eval"), default="val")
    ap.add_argument("--final", action="store_true", help="required for --split eval")
    ap.add_argument("--streams", type=int, default=20)
    ap.add_argument("--severe-streams", type=int, default=None, help="override stream count for severe_surge")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--drain-days", type=float, default=7.0)
    ap.add_argument("--resamples", type=int, default=10_000)
    ap.add_argument("--out-md", default="")
    ap.add_argument("--out-json", default="")
    ap.add_argument("--title", default="Policy comparison")
    args = ap.parse_args()

    policies: Dict[str, Policy] = {}
    for short in [p for p in args.policies.split(",") if p]:
        policies[short] = BASELINES[POLICY_ALIASES.get(short, short)]()
    for path in [p for p in args.agent.split(",") if p]:
        policies[Path(path).parent.name] = load_agent_policy(path)
    modes = [m for m in args.modes.split(",") if m]
    seeds_by_mode = {m: resolve_seeds(args.split, args.severe_streams if (m == "severe_surge" and
                                      args.severe_streams) else args.streams, args.final) for m in modes}

    from ml.los.predictor import LOSPredictor
    predictor = LOSPredictor.load()
    t0 = time.time()
    results = compare_policies(policies, modes, seeds_by_mode, args.days, args.drain_days, predictor,
                               verbose=True)
    summary = summarize(results, n_resamples=args.resamples)
    pool = VAL_SEEDS if args.split == "val" else EVAL_SEEDS
    meta = {"split": args.split, "seed_ranges": f"{pool.start}-{pool.stop - 1}", "days": args.days,
            "drain_days": args.drain_days, "created_at": datetime.now().isoformat(timespec="seconds"),
            "streams_per_mode": {m: len(seeds_by_mode[m]) for m in modes}, "policies": list(policies),
            "runtime_seconds": round(time.time() - t0, 1)}
    if args.out_md:
        write_markdown_report(summary, meta, Path(args.out_md), args.title)
        print(f"Saved {args.out_md}")
    if args.out_json:
        out = {"meta": meta, "summary": summary, "action_distribution": action_distribution(results),
               "runs": compact_runs(results)}
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(json.dumps(out, indent=1))
        print(f"Saved {args.out_json}")
    for mode, block in summary.items():
        print(f"\n{mode}")
        for name, stats in block["stats"].items():
            print(f"  {name:14s} weighted {stats['acuity_weighted_avg_wait_min']['mean']:9.1f} | "
                  f"avg {stats['avg_wait_incl_unadmitted_min']['mean']:9.1f} | "
                  f"critical {stats['critical_avg_wait_min']['mean'] or float('nan'):8.1f}")


if __name__ == "__main__":
    main()
