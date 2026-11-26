"""Paired benchmark of adaptive planner weights. Run from the repository root."""
import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from statistics import mean

from backend.services.surge import run_adaptive
from ml.los.predictor import DEFAULT_MODEL, LOSPredictor
from rl.evaluation.compare import paired_bootstrap
from rl.evaluation.evaluate import wait_group_metrics
from simulator.hospital.loader import load_hospital_state
from simulator.hospital.scenarios import apply_shortage
from simulator.metrics.audit import audit_violations
from simulator.patients.streams import EVAL_SEEDS, generate_stream

SCENARIOS = {
    "normal": ("normal", None),
    "moderate_surge": ("moderate_surge", None),
    "severe_surge": ("severe_surge", None),
    "icu_shortage": ("normal", "icu_shortage"),
    "equipment_shortage": ("normal", "equipment_shortage"),
    "staff_shortage": ("normal", "staff_shortage"),
    "combined_crisis": ("moderate_surge", "combined_crisis"),
}
SERVING = Path("models/serving")


class ResourceUsage:
    def __init__(self):
        self.daily_overtime = {}
        self.peak_fatigue = 0.0

    def on_tick(self, state):
        day = state.current_time.date()
        self.daily_overtime[day] = max(self.daily_overtime.get(day, 0), state.turnaround_overtime_minutes)
        self.peak_fatigue = max(self.peak_fatigue, state.nurse_fatigue_index)


@lru_cache(maxsize=1)
def predictor():
    return LOSPredictor.load()


def evaluate_pair(task):
    scenario, seed, candidate = task
    mode, shortage = SCENARIOS[scenario]
    patients = generate_stream(seed, days=30, mode=mode)
    end = min(p.arrival_time for p in patients) + timedelta(days=30)
    pair = {"seed": seed, "scenario": scenario}
    for label, models in (("serving", SERVING), ("candidate", candidate)):
        state = load_hospital_state("data/synthetic", start_empty=True)
        if shortage:
            apply_shortage(state, shortage, seed=seed)
        usage = ResourceUsage()
        engine, interrupts = run_adaptive(state, patients, 720, usage, models=models, seed=seed, predictor=predictor())
        metrics = wait_group_metrics(engine.patients.values(), end)
        pair[label] = {
            "weighted_wait_min": metrics["acuity_weighted_avg_wait_min"],
            "critical_wait_min": metrics["critical_avg_wait_min"],
            "audited_violations": audit_violations(engine)["total"],
            "peak_fatigue_observed": usage.peak_fatigue,
            "max_daily_overtime_observed_min": max(usage.daily_overtime.values()),
            "staff_floats": engine.resource_interventions["float_staff"],
            "interrupts": interrupts,
        }
    return pair


def summarize(pairs):
    result = {}
    for label in ("serving", "candidate"):
        result[label] = {key: mean(row[label][key] for row in pairs) for key in pairs[0][label]}
    result["paired_wait_delta_min"] = paired_bootstrap([
        row["candidate"]["weighted_wait_min"] - row["serving"]["weighted_wait_min"] for row in pairs
    ])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    paths = [DEFAULT_MODEL, SERVING / "dqn_x6_obs_v2.npz"]
    paths.extend(directory / filename for directory in (SERVING, args.candidate)
                 for filename in ("resource_agent.npz", "surge_agent.npz"))
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    tasks = [(scenario, seed, args.candidate) for scenario in SCENARIOS for seed in EVAL_SEEDS]
    pairs = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for pair in pool.map(evaluate_pair, tasks):
            pairs.append(pair)
            if len(pairs) % len(EVAL_SEEDS) == 0:
                print(f"Completed {pair['scenario']} ({len(pairs)}/{len(tasks)} pairs)", flush=True)
    summary = {scenario: summarize([p for p in pairs if p["scenario"] == scenario]) for scenario in SCENARIOS}
    result = {"days": 30, "initial_state": "empty hospital with scenario shortage", "sha256": hashes,
              "summary": summary, "pairs": pairs}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
