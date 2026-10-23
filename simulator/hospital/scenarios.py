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
