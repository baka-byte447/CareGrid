from collections import defaultdict
from typing import Dict, List

ALLOWED_TIERS = {
    5:{"ICU"},
    4:{"ICU","STEP_DOWN"},
}

def audit_violations(engine) -> Dict[str, int]:
    beds = engine.state.beds
    equipment = engine.state.equipment
    counts = {
        "acuity_tier":0,
        "isolation":0,
        "ventilator":0,
        "double_booking":0,
    }

    stays =defaultdict(list)

    for p in engine.patients.values():
        if p.admission_time is None:
            continue
        bed  = beds[p.bed_id]
        allowed = ALLOWED_TIERS.get(p.acuity)
        if allowed is not None and bed.bed_type not in allowed:
            counts["acuity_tier"]+=1
        if p.isolation_required and not bed.isolation_capable:
            counts["isolation"]+=1
        if p.ventilator_required:
            eq = equipment.get(p.equipment_id) if p.equipment_id else None
            if eq is None or eq.type!= "VENTILATOR":
                counts["ventilator"]+=1
        end = p.discharge_time or engine.state.current_time
        stays[p.bed_id].append((p.admission_time, end))

    for intervals in stays.values():
        intervals.sort()
        for(_, prev_end), (next_start, _) in zip(intervals, intervals[1:]):
            if next_start<prev_end:
                counts["double_booking"]+=1

    counts["total"]= sum(counts.values())
    return counts