import argparse
import json
from datetime import datetime
from pathlib import Path

from simulator.hospital.engine import SimulationEngine
from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.hospital.scenarios import SCENARIO_MULTIPLIERS, scale_arrivals
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics

RESULTS_DIR = Path(__file__).parent / "results"

SUPPORTED_ALGORITHMS = ("rule_based",)

def run_experiment(algorithm: str, scenario: str, data_dir: str, patients_file: str,
                   arrival_multiplier: float = None) -> dict:
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{algorithm}'. Supported: {SUPPORTED_ALGORITHMS}")

    if arrival_multiplier is None:
        arrival_multiplier = SCENARIO_MULTIPLIERS.get(scenario, 1.0)

    state = load_hospital_state(data_dir)
    patients = load_patients(data_dir, patients_file)
    scale_arrivals(patients, arrival_multiplier)
    arrivals = [p.arrival_time for p in patients]

    engine = SimulationEngine(state, patients)
    engine.seed_arrivals()
    collector = MetricsCollector(window_start=min(arrivals), window_end=max(arrivals))
    engine.run(on_tick=collector.on_tick)

    created = datetime.now()
    return {
        "experiment_id": f"{algorithm}__{scenario}__{created:%Y%m%d_%H%M%S}",
        "algorithm": algorithm,
        "scenario": scenario,
        "patients_file": patients_file,
        "arrival_multiplier": arrival_multiplier,
        "created_at": created.isoformat(timespec="seconds"),
        "metrics": compute_metrics(engine, collector),
    }


def main():
    ap = argparse.ArgumentParser(description="Run one CareGrid experiment")
    ap.add_argument("--algorithm", default="rule_based")
    ap.add_argument("--scenario", default="normal")
    ap.add_argument("--data", default="data/synthetic")
    ap.add_argument("--patients", default="patients.csv")
    ap.add_argument("--arrival-multiplier", type=float, default=None,
                    help="override the scenario's arrival-rate multiplier")
    args = ap.parse_args()

    result = run_experiment(args.algorithm, args.scenario, args.data, args.patients,
                            args.arrival_multiplier)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{result['experiment_id']}.json"
    out.write_text(json.dumps(result, indent=2))

    m = result["metrics"]
    print(f"Experiment: {result['experiment_id']}  (arrival x{result['arrival_multiplier']})")
    print(f"  Admitted / total:      {m['patients_admitted']} / {m['patients_total']}")
    print(f"  Avg / median wait:     {m['avg_wait_min']} / {m['median_wait_min']} min")
    print(f"  ICU utilization:       {m['icu_utilization']}")
    print(f"  Overall bed util:      {m['overall_bed_utilization']}")
    print(f"  Bed turnover/bed/day:  {m['bed_turnover_per_bed_per_day']}")
    print(f"  Violations:            {m['constraint_violations']['total']}")
    print(f"  Saved: {out}")


if __name__ == "__main__":
    main()
