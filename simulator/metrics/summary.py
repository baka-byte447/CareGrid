import statistics 
from typing import Dict


from simulator.metrics.audit import audit_violations
from simulator.metrics.collector import MetricsCollector, BED_TYPES

def _pct(values, q):
    if not values:
        return 0.0
    s =sorted(values)
    return s[min(int(len(s)*q),len(s)-1)]

def compute_metrics(engine, collector: MetricsCollector, as_of=None) -> Dict:
    patients = list(engine.patients.values())
    waits = [p.wait_minutes for p in patients if p.wait_minutes is not None]
    window = collector.window_minutes or 1.0
    beds_by_type = {t: sum(1 for b in engine.state.beds.values()if b.bed_type==t) for t in BED_TYPES}
    total_beds = sum(beds_by_type.values())
    vents_total= sum(1 for e in engine.state.equipment.values() if e.type=="VENTILATOR")

    utilization = {
        t:round(collector.occupied_minutes[t] / (beds_by_type[t]*window),4)
        for t in BED_TYPES if beds_by_type[t]
    }
    overall_util = (sum(collector.occupied_minutes.values()) / (total_beds*window) if total_beds else 0.0)

    waits_by_acuity={}
    for a in range(1,6):
        w = [p.wait_minutes for p in patients if p.acuity == a and p.wait_minutes is not None]
        waits_by_acuity[str(a)] = round(sum(w) / len(w), 2) if w else None

    # Patients never admitted would otherwise be silently dropped from the averages,
    # which lets a policy look good by leaving hard patients waiting. Count them as
    # having waited until the end of the run (a lower bound on their true wait).
    # `as_of` is the common evaluation end time. Pass it whenever policies are compared:
    # an episode can stop early (e.g. nothing was admitted, so no event is left), and
    # censoring at "the last event" would then flatter exactly the worst policies.
    now = as_of if as_of is not None else engine.state.current_time
    censored = [
        p.wait_minutes if p.wait_minutes is not None
        else max((now - p.arrival_time).total_seconds() / 60.0, 0.0)
        for p in patients if now is not None and p.arrival_time <= now
    ]

    discharged = sum(1 for p in patients if p.status =="DISCHARGED")

    discharged_in_window = sum(
        1 for p in patients if p.discharge_time is not None and collector.window_start <= p.discharge_time<=collector.window_end
    )
    window_days = window/(60*24)


    return {
        "patients_total": len(patients),
        "patients_admitted": engine.admitted_count,
        "patients_discharged": discharged,
        "patients_still_waiting": len(engine.state.waiting_queue),
        "avg_wait_min": round(sum(waits) / len(waits), 2) if waits else 0.0,
        "median_wait_min": round(statistics.median(waits), 2) if waits else 0.0,
        "avg_wait_incl_unadmitted_min": round(sum(censored) / len(censored), 2) if censored else 0.0,
        "p90_wait_incl_unadmitted_min": round(_pct(censored, 0.90), 2),
        "p90_wait_min": round(_pct(waits, 0.90), 2),
        "max_wait_min": round(max(waits), 2) if waits else 0.0,
        "avg_wait_by_acuity_min": waits_by_acuity,
        "pct_admitted_within_60min": round(
            sum(1 for w in waits if w <= 60) / len(waits), 4) if waits else 0.0,
        "icu_utilization": utilization.get("ICU"),
        "step_down_utilization": utilization.get("STEP_DOWN"),
        "ward_utilization": utilization.get("WARD"),
        "overall_bed_utilization": round(overall_util, 4),
        "ventilator_utilization": round(
            collector.vent_in_use_minutes / (vents_total * window), 4) if vents_total else None,
        "bed_turnover_per_bed_per_day": round(discharged_in_window / total_beds / window_days, 4)
            if total_beds and window_days else 0.0,
        "peak_waiting_queue": collector.peak_waiting,
        "constraint_violations": audit_violations(engine),
        "measurement_window_hours": round(window / 60, 1),
    }