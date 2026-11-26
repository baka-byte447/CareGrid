"""Explain the observed decision using the same feasibility check as serving."""
from dataclasses import dataclass
from simulator.hospital.allocation_rules import allocation_for_bed_type, candidate_bed_types

ACTIONS = ("ICU", "STEP_DOWN", "WARD", "WAIT")


@dataclass
class ClinicalExplanation:
    summary: str
    chosen_reason: str
    counterfactual: str
    safety_guarantee: str
    confidence_margin: float | None


def explain(patient, state, proposed_action, final_action, q_values, safety_block):
    chosen = ACTIONS[final_action]
    alternatives = [i for i in range(4) if i != final_action]
    margin = None
    if q_values is not None:
        alternative = max(alternatives, key=lambda i: q_values[i])
        margin = round(q_values[final_action] - q_values[alternative], 4)
    else:
        order = [ACTIONS.index(t) for t in candidate_bed_types(patient.acuity)]
        alternative = next(i for i in dict.fromkeys(order + alternatives) if i != final_action)
    override = safety_block and safety_block.get("overridden")
    if override:
        alternative = proposed_action
        margin = None
    other = ACTIONS[alternative]
    reason = None if other == "WAIT" else allocation_for_bed_type(patient, state, other)[1]
    rule = (safety_block or {}).get("rule_triggered") or (safety_block or {}).get("reason")
    rule_text = {
        "G1_CRITICAL_WAIT": "A critical patient is waiting despite a feasible bed.",
        "G2_MAX_WAIT": "Waiting exceeds the configured limit for this acuity.",
        "TIER_NOT_ALLOWED": "The proposed bed tier is incompatible with the recorded acuity.",
        "NO_FREE_BED": "The proposed tier has no free bed.",
        "ISOLATION_BED_REQUIRED": "The patient requires an isolation-capable bed.",
        "NO_VENTILATOR": "The required ventilator is unavailable.",
    }
    if rule in rule_text:
        rule = f"{rule}: {rule_text[rule]}"
    if override:
        comparison = f"{other} triggered the safety review: {rule}."
    elif reason:
        comparison = f"{other} was excluded: {reason.replace('_', ' ')}."
    elif q_values is not None:
        comparison = f"{other} scored {q_values[alternative]:.3f}; {chosen} scored {q_values[final_action]:.3f}."
    else:
        comparison = f"The allocation rules selected {chosen} ahead of {other}."
    if chosen == "WAIT":
        rationale = "The patient remains in the admission queue."
    else:
        rationale = f"A compatible {chosen} bed is available for acuity {patient.acuity} and the recorded resource needs."
    safety = rule or "Bed compatibility and resource availability were checked."
    return ClinicalExplanation(f"Recommended action: {chosen}.", rationale, comparison, safety, margin)
