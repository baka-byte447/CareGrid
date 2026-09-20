from simulator.hospital.state import HospitalState


def print_dashboard(state: HospitalState) -> None:
    snap = state.snapshot()
    print("-" * 40)
    print("CAREGRID SIMULATION")
    print("-" * 40)
    print(f"Time: {snap['time']}")
    print()
    for bed_type, counts in snap["beds"].items():
        label = bed_type.replace("_", "-").title()
        print(f"{label:<12} {counts['occupied']}/{counts['total']} occupied "
              f"({counts['available']} free, {counts['cleaning']} cleaning)")
    print()
    print(f"Waiting patients: {snap['waiting_count']}")
    print()
    vents = snap["ventilators"]
    print(f"Ventilators: {vents['available']} available / {vents['total']} total")
    print("-" * 40)
