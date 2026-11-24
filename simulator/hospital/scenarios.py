"""
CareGrid-RL: Arrival-rate scenarios

Surge scenarios are produced by compressing the arrival times of the (calibrated)
normal patient file; patient attributes stay identical, so a policy is compared
on exactly the same patients at every load level. The multipliers match the
ratios used when generating the surge datasets (1.3 / 0.8 and 2.2 / 0.8) and the
`arrival_rate_multiplier` of the backend's /surge/simulate endpoint.
"""
from typing import Iterable

SCENARIO_MULTIPLIERS = {
    "normal": 1.0,
    "moderate_surge": 1.6,
    "severe_surge": 2.7,
}

SHORTAGE_SCENARIOS = {
    "icu_shortage": "50% ICU beds taken out of service",
    "equipment_shortage": "50% ventilators in maintenance",
    "staff_shortage": "20% ward and step-down beds out of service",
    "combined_crisis": "moderate surge arrivals + 50% ICU cut + 50% ventilator cut",
}


def apply_shortage(state, name: str, seed: int = 0) -> None:
    """Take beds or equipment out of service according to shortage scenario."""
    if not name or name == "none" or name not in SHORTAGE_SCENARIOS:
        return
    import numpy as np

    rng = np.random.default_rng(seed)

    if name in ("icu_shortage", "combined_crisis"):
        icu_beds = sorted(
            [b for b in state.beds.values() if b.bed_type == "ICU"],
            key=lambda b: b.bed_id,
        )
        n_cut = len(icu_beds) // 2
        if icu_beds and n_cut > 0:
            for b in rng.choice(icu_beds, size=n_cut, replace=False):
                b.status = "OUT_OF_SERVICE"

    if name in ("equipment_shortage", "combined_crisis"):
        vents = sorted(
            [e for e in state.equipment.values() if e.type == "VENTILATOR"],
            key=lambda e: e.equipment_id,
        )
        n_cut = len(vents) // 2
        if vents and n_cut > 0:
            for e in rng.choice(vents, size=n_cut, replace=False):
                e.status = "MAINTENANCE"

    if name == "staff_shortage":
        general_beds = sorted(
            [b for b in state.beds.values() if b.bed_type in ("WARD", "STEP_DOWN")],
            key=lambda b: b.bed_id,
        )
        n_cut = max(1, int(len(general_beds) * 0.20))
        if general_beds and n_cut > 0:
            for b in rng.choice(general_beds, size=n_cut, replace=False):
                b.status = "OUT_OF_SERVICE"


def scale_arrivals(patients: Iterable, multiplier: float) -> None:
    """Compress (multiplier > 1) or stretch (< 1) arrival times IN PLACE,
    measured from the earliest arrival."""
    if multiplier <= 0:
        raise ValueError("multiplier must be > 0")
    patients = list(patients)
    if multiplier == 1.0 or not patients:
        return
    start = min(p.arrival_time for p in patients)
    for p in patients:
        p.arrival_time = start + (p.arrival_time - start) / multiplier
