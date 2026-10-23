"""
CareGrid-RL: Allocation policy registry

One entry point, `recommend(patient, state, algorithm)`, for everything that needs
an allocation recommendation (the backend today; experiments and the DQN + safety
pipeline later). Adding a new algorithm is a single `register_policy(...)` call --
callers and the API response shape do not change.

A policy is any callable (patient, state) -> AllocationResult.
"""
from typing import Callable, Dict, List

from simulator.hospital.allocation_rules import AllocationResult, evaluate_allocation
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient

Policy = Callable[[Patient, HospitalState], AllocationResult]

DEFAULT_ALGORITHM = "rule_based"
_POLICIES: Dict[str, Policy] = {DEFAULT_ALGORITHM: evaluate_allocation}


def register_policy(name: str, policy: Policy) -> None:
    _POLICIES[name] = policy


def available_algorithms() -> List[str]:
    return sorted(_POLICIES)


def recommend(patient: Patient, state: HospitalState,
              algorithm: str = DEFAULT_ALGORITHM) -> AllocationResult:
    try:
        policy = _POLICIES[algorithm]
    except KeyError:
        raise ValueError(
            f"Unknown algorithm '{algorithm}'. Available: {available_algorithms()}") from None
    return policy(patient, state)
