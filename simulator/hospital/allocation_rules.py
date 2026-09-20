from dataclasses import dataclass
from typing import List, Optional

from simulator.hospital.state import HospitalState, Bed
from simulator.patients.patient import Patient


@dataclass
class AllocationDecision:
    bed_id: str
    equipment_id: Optional[str] = None   


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


def decide_bed(patient: Patient, state: HospitalState) -> Optional[AllocationDecision]:
    """
    Pure function: reads state, never mutates it. Returns an
    AllocationDecision if the patient can be admitted right now,
    or None if they must remain WAITING.
    """
    chosen_bed: Optional[Bed] = None

    for bed_type in _candidate_bed_types(patient.acuity):
        candidates = state.available_beds_by_type(bed_type)
        if patient.isolation_required:
            candidates = [b for b in candidates if b.isolation_capable]
        chosen_bed = _pick_bed(candidates)
        if chosen_bed is not None:
            break

    if chosen_bed is None:
        return None  

    equipment_id = None
    if patient.ventilator_required:
        available_vents = state.available_ventilators()
        if not available_vents:
            return None
        equipment_id = min(available_vents, key=lambda e: e.equipment_id).equipment_id

    return AllocationDecision(bed_id=chosen_bed.bed_id, equipment_id=equipment_id)
