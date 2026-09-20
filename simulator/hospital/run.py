"""
Loads hospital + patient data, runs the discrete-event simulation with
the rule-based allocation baseline, prints periodic dashboard snapshots,
and reports a final summary.
"""
import argparse
from datetime import timedelta

from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.dashboard import print_dashboard


def main():
    parser = argparse.ArgumentParser(description="CareGrid-RL Simulator (rule-based baseline)")
    parser.add_argument("--data", default="data/synthetic", help="Directory with synthetic CSVs")
    parser.add_argument("--patients", default="patients.csv", help="Patient arrivals file")
    parser.add_argument("--dashboard-every-hours", type=float, default=1.0,
                         help="Print the dashboard every N simulated hours (0 = never)")
    args = parser.parse_args()

    state = load_hospital_state(args.data)
    patients = load_patients(args.data, args.patients)

    engine = SimulationEngine(state, patients)
    engine.seed_arrivals()

    print(f"Loaded {len(state.beds)} beds, {len(state.staff)} staff, "
          f"{len(state.equipment)} equipment, {len(patients)} patients.\n")

    last_dashboard_time = [None]
    interval = timedelta(hours=args.dashboard_every_hours) if args.dashboard_every_hours > 0 else None

    def on_tick(current_state):
        if interval is None:
            return
        if (last_dashboard_time[0] is None
                or current_state.current_time - last_dashboard_time[0] >= interval):
            print_dashboard(current_state)
            last_dashboard_time[0] = current_state.current_time

    engine.run(on_tick=on_tick)

    discharged = [p for p in engine.patients.values() if p.status == "DISCHARGED"]
    still_waiting = len(state.waiting_queue)
    wait_times = [p.wait_minutes for p in engine.patients.values() if p.wait_minutes is not None]
    avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0.0

    print("\n" + "=" * 40)
    print("SIMULATION COMPLETE")
    print("=" * 40)
    print(f"Total patients loaded:     {len(patients)}")
    print(f"Total admitted:            {engine.admitted_count}")
    print(f"Total discharged:          {len(discharged)}")
    print(f"Still waiting at end:      {still_waiting}")
    print(f"Average wait (admitted):   {avg_wait:.1f} minutes")
    print("=" * 40)


if __name__ == "__main__":
    main()
