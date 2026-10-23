"""Shared clinical/resource allocation rules for all simulator policies."""
from dataclasses import dataclass
from typing import List, Optional

from simulator.hospital.state import HospitalState, Bed
from simulator.patients.patient import Patient


@dataclass
class AllocationDecision:
    bed_id: str
    equipment_id: Optional[str] = None


class AllocationValidationError(ValueError):
    """Raised when an allocation violates simulator invariants."""


def _candidate_bed_types(acuity: int) -> List[str]:
    if acuity == 5:
        return ["ICU"]
    if acuity == 4:
        return ["ICU", "STEP_DOWN"]
    if acuity == 3:
        return ["STEP_DOWN", "WARD"]
    return ["WARD"]  # acuity 1-2


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
    if bed.bed_type not in _candidate_bed_types(patient.acuity):
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
    if bed_type not in _candidate_bed_types(patient.acuity):
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


def decide_bed(patient: Patient, state: HospitalState) -> Optional[AllocationDecision]:
    """Return the first feasible allocation according to legacy rule-based policy."""
    for bed_type in _candidate_bed_types(patient.acuity):
        decision, _ = allocation_for_bed_type(patient, state, bed_type)
        if decision is not None:
            return decision
    return None
