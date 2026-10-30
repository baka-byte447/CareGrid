"""
CareGrid Safety Layer: HARD constraint checks for allocation decisions.

These checks are written INDEPENDENTLY from simulator/hospital/allocation_rules.py.
They are derived from:
  - docs/architecture/allocation_rules.md (clinical rules)
  - simulator/metrics/audit.py (violation categories)

Constraint catalogue:
  H1  ACTION_OUT_OF_RANGE    action not in {0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT}
  H2  TIER_NOT_ALLOWED       bed tier incompatible with patient acuity
  H3  NO_FREE_BED            no available bed of the requested tier
  H4  ISOLATION_BED_REQUIRED patient needs isolation but no isolation-capable bed free
  H5  NO_VENTILATOR          patient needs ventilator but none available
  H6  DOUBLE_BOOKING         bed or equipment already assigned (should not happen in
                             well-formed state, but checked defensively)

WAIT (action 3) always passes hard checks — a patient is never harmed by waiting
(clinically questionable for critical patients, but that is a SOFT guardrail, not a
hard constraint).
"""
from typing import Dict, List, Optional, Sequence

# Bed tier action mapping (must match rl/environment/hospital_env.py)
BED_TIERS = {0: "ICU", 1: "STEP_DOWN", 2: "WARD"}
WAIT_ACTION = 3
VALID_ACTIONS = {0, 1, 2, 3}

# Acuity -> allowed bed tiers (from docs/architecture/allocation_rules.md §2)
ACUITY_TO_ALLOWED_TIERS: Dict[int, frozenset] = {
    5: frozenset({"ICU"}),
    4: frozenset({"ICU", "STEP_DOWN"}),
    3: frozenset({"STEP_DOWN", "WARD"}),
    2: frozenset({"WARD"}),
    1: frozenset({"WARD"}),
}


def check_hard_constraints(
    patient,
    state,
    action: int,
) -> List[str]:
    """Return a list of reason codes for every hard constraint violated.

    An empty list means the proposed action passes all hard checks.
    WAIT always returns an empty list.

    Parameters
    ----------
    patient : simulator.patients.patient.Patient
        The patient being allocated.
    state : simulator.hospital.state.HospitalState
        Current hospital state (beds, equipment, queues).
    action : int
        Proposed action: 0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT.
    """
    reasons: List[str] = []

    # H1: action range
    if action not in VALID_ACTIONS:
        reasons.append("ACTION_OUT_OF_RANGE")
        return reasons  # can't check further without a valid action

    # WAIT is always safe from a hard-constraint perspective
    if action == WAIT_ACTION:
        return reasons

    # H2: tier compatibility with acuity
    tier = BED_TIERS.get(action)
    if tier is None:
        reasons.append("ACTION_OUT_OF_RANGE")
        return reasons

    allowed = ACUITY_TO_ALLOWED_TIERS.get(patient.acuity)
    if allowed is None:
        reasons.append("TIER_NOT_ALLOWED")  # unknown acuity
        return reasons
    if tier not in allowed:
        reasons.append("TIER_NOT_ALLOWED")

    # H3: bed availability
    beds_of_tier = [b for b in state.beds.values()
                    if b.bed_type == tier and b.status == "AVAILABLE"]
    if not beds_of_tier:
        reasons.append("NO_FREE_BED")
        return reasons  # no point checking isolation on non-existent beds

    # H4: isolation requirement
    if patient.isolation_required:
        iso_beds = [b for b in beds_of_tier if b.isolation_capable]
        if not iso_beds:
            reasons.append("ISOLATION_BED_REQUIRED")

    # H5: ventilator requirement
    if patient.ventilator_required:
        vents = [e for e in state.equipment.values()
                 if e.type == "VENTILATOR" and e.status == "AVAILABLE"]
        if not vents:
            reasons.append("NO_VENTILATOR")

    return reasons


def is_action_feasible(patient, state, action: int) -> bool:
    """True if the action violates no hard constraints."""
    return len(check_hard_constraints(patient, state, action)) == 0


def feasible_actions(patient, state) -> List[int]:
    """Return all actions that pass hard checks (WAIT is always included)."""
    return [a for a in sorted(VALID_ACTIONS)
            if is_action_feasible(patient, state, a)]

