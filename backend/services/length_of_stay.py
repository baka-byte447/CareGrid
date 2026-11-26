from math import isfinite

from backend.models.encounter import Encounter


def admission_los_estimates(rows: list[tuple[Encounter, str]]) -> dict[int, float]:
    """Return saved predictions and estimate older admissions in a single model batch."""
    estimates = {}
    missing = {}
    for encounter, age_group in rows:
        if encounter.los_estimate_days is not None:
            estimates[encounter.encounter_id] = encounter.los_estimate_days
        else:
            missing[encounter.encounter_id] = {
                "age_group": age_group,
                "acuity": encounter.acuity,
                "specialty": encounter.specialty,
                "isolation_required": encounter.isolation_required,
                "ventilator_required": encounter.ventilator_required,
            }
    if missing:
        try:
            from ml.los.predictor import get_los_predictor

            predictions = get_los_predictor().predict_many(missing.values())
        except Exception:
            return estimates
        estimates.update(
            (encounter_id, days)
            for encounter_id, days in zip(missing, predictions, strict=True)
            if isfinite(days) and days > 0
        )
    return estimates
