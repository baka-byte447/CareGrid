"""Shared clinical/resource allocation rules for all simulator policies.

This module is the SINGLE implementation of the allocation rules: the simulator
engine, the Gymnasium environment, the experiment runner and the backend's
/allocation/recommend and /allocation/approve endpoints all call it, so the rules
cannot drift apart. Rule-based recommendations are exposed through
simulator/hospital/policy.py (`recommend`), where DQN + safety plug in later.

Rules: hard isolation / ventilator constraints first; acuity decides the acceptable
tiers with escalation (5: ICU | 4: ICU, STEP_DOWN | 3: STEP_DOWN, WARD | 1-2: WARD);
lowest bed_id breaks ties.
"""
from dataclasses import dataclass
from typing import List, Optional

from simulator.hospital.state import HospitalState, Bed
from simulator.patients.patient import Patient


@dataclass
class AllocationDecision:
    bed_id: str
    equipment_id: Optional[str] = None


REASON_NO_VENTILATOR = "No available ventilator"
REASON_NO_BED = "No compatible available bed found"


@dataclass
class AllocationResult:
    """A decision plus a human-readable reason (used by the API and, later, the
    audit log / explanation panel). `decision` is None when the patient must keep
    waiting."""
    decision: Optional[AllocationDecision]
    reason: str


class AllocationValidationError(ValueError):
    """Raised when an allocation violates simulator invariants."""


def candidate_bed_types(acuity: int) -> List[str]:
    """Acceptable bed tiers for an acuity level, in order of preference.
    Raises ValueError for acuity outside 1-5."""
    if acuity == 5:
        return ["ICU"]
    if acuity == 4:
        return ["ICU", "STEP_DOWN"]
    if acuity == 3:
        return ["STEP_DOWN", "WARD"]
    if acuity in (1, 2):
        return ["WARD"]
    raise ValueError(f"Invalid patient acuity: {acuity!r} (expected 1-5)")


def _pick_bed(candidates: List[Bed]) -> Optional[Bed]:
    if not candidates:
        return None
    return min(candidates, key=lambda b: b.bed_id)


def allocation_error(
    patient: Patient,
    state: HospitalState,
    decision: AllocationDecision,
    *,
    check_patient_status: bool = True,
) -> Optional[str]:
    """Return a clear reason if a proposed allocation is invalid, else ``None``.

    This function is read-only and is shared by the environment and engine so
    policy-side feasibility checks cannot drift from the engine's safety checks.
    """
    if not isinstance(decision, AllocationDecision):
        return "decision_must_be_an_AllocationDecision"
    if check_patient_status:
        if patient.patient_id in state.admitted_patients or patient.status == "ADMITTED":
            return "patient_already_admitted"
        if patient.status == "DISCHARGED":
            return "patient_already_discharged"
        if patient.status != "WAITING":
            return "patient_not_waiting"

    bed = state.beds.get(decision.bed_id)
    if bed is None:
        return "bed_not_found"
    if bed.status != "AVAILABLE":
        return "bed_not_available"
    try:
        acceptable_types = candidate_bed_types(patient.acuity)
    except ValueError:
        return "invalid_acuity"
    if bed.bed_type not in acceptable_types:
        return "bed_type_incompatible_with_acuity"
    if patient.isolation_required and not bed.isolation_capable:
        return "bed_not_isolation_capable"

    if patient.ventilator_required:
        if not decision.equipment_id:
            return "ventilator_required"
        equipment = state.equipment.get(decision.equipment_id)
        if equipment is None:
            return "equipment_not_found"
        if equipment.type != "VENTILATOR":
            return "equipment_not_a_ventilator"
        if equipment.status != "AVAILABLE":
            return "ventilator_unavailable"
    elif decision.equipment_id is not None:
        return "unneeded_equipment_must_not_be_reserved"
    return None


def validate_allocation(patient: Patient, state: HospitalState, decision: AllocationDecision) -> None:
    """Raise before mutation if the proposed allocation is not safe."""
    reason = allocation_error(patient, state, decision)
    if reason is not None:
        raise AllocationValidationError(
            f"Invalid allocation for patient {patient.patient_id!r}: {reason}."
        )


def allocation_for_bed_type(
    patient: Patient, state: HospitalState, bed_type: str
) -> tuple[Optional[AllocationDecision], Optional[str]]:
    """Choose the deterministic feasible allocation for a requested bed type."""
    try:
        acceptable_types = candidate_bed_types(patient.acuity)
    except ValueError:
        return None, "invalid_acuity"
    if bed_type not in acceptable_types:
        return None, "bed_type_incompatible_with_acuity"
    candidates = state.available_beds_by_type(bed_type)
    if patient.isolation_required:
        candidates = [bed for bed in candidates if bed.isolation_capable]
    bed = _pick_bed(candidates)
    if bed is None:
        return None, "no_compatible_bed_available"

    equipment_id = None
    if patient.ventilator_required:
        vents = state.available_ventilators()
        if not vents:
            return None, "ventilator_unavailable"
        equipment_id = min(vents, key=lambda equipment: equipment.equipment_id).equipment_id

    decision = AllocationDecision(bed_id=bed.bed_id, equipment_id=equipment_id)
    # Keep feasibility and final engine validation on the same contract.
    reason = allocation_error(patient, state, decision)
    return (None, reason) if reason else (decision, None)


def evaluate_allocation(patient: Patient, state: HospitalState) -> AllocationResult:
    """Rule-based recommendation with a reason. Pure: reads state, never mutates it.

    The ventilator is checked before beds, so a bed is never offered to a patient
    who cannot be safely cared for in it (and the API keeps its specific reason).
    Raises ValueError for acuity outside 1-5."""
    bed_types = candidate_bed_types(patient.acuity)
    if patient.ventilator_required and not state.available_ventilators():
        return AllocationResult(None, REASON_NO_VENTILATOR)
    for bed_type in bed_types:
        decision, _ = allocation_for_bed_type(patient, state, bed_type)
        if decision is not None:
            return AllocationResult(decision, f"Compatible {bed_type} bed available")
    return AllocationResult(None, REASON_NO_BED)


def decide_bed(patient: Patient, state: HospitalState) -> Optional[AllocationDecision]:
    """Decision only (None = stays WAITING). Used by the simulator engine."""
    return evaluate_allocation(patient, state).decision
