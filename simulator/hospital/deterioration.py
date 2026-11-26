"""Adult NEWS2 component scores from the Royal College of Physicians observation chart."""
from bisect import bisect_right


def news2(respiratory_rate, spo2, systolic_bp, pulse, temperature, consciousness,
          supplemental_oxygen=False, oxygen_scale=1):
    rr = (3, 1, 0, 2, 3)[bisect_right((9, 12, 21, 25), respiratory_rate)]
    if oxygen_scale == 1:
        oxygen = (3, 2, 1, 0)[bisect_right((92, 94, 96), spo2)]
    else:
        oxygen = (3, 2, 1, 0, 1, 2, 3)[bisect_right((84, 86, 88, 93, 95, 97), spo2)]
        if spo2 >= 93 and not supplemental_oxygen:
            oxygen = 0
    bp = (3, 2, 1, 0, 3)[bisect_right((91, 101, 111, 220), systolic_bp)]
    hr = (3, 1, 0, 1, 2, 3)[bisect_right((41, 51, 91, 111, 131), pulse)]
    temp = (3, 1, 0, 1, 2)[bisect_right((35.1, 36.1, 38.1, 39.1), temperature)]
    components = [rr, oxygen, bp, hr, temp, 0 if consciousness.upper() in ("A", "ALERT") else 3,
                  2 if supplemental_oxygen else 0]
    total = sum(components)
    risk = "high" if total >= 7 else "medium" if total >= 5 else "single_red" if 3 in components else "low"
    return total, risk


def classic_sofa(*, pao2_fio2_mmhg, respiratory_support, platelets_10e9_l, bilirubin_mg_dl,
                 map_mmhg, dopamine, dobutamine, epinephrine, norepinephrine,
                 glasgow_coma_scale, creatinine_mg_dl, urine_ml_24h):
    """Classic SOFA, Sepsis-3 Table 1. Inputs represent the worst values for a 24-hour assessment."""
    respiration = sum(pao2_fio2_mmhg < t for t in (400, 300))
    if respiratory_support:
        respiration += sum(pao2_fio2_mmhg < t for t in (200, 100))
    cardiovascular = int(map_mmhg < 70)
    if dopamine > 0 or dobutamine > 0:
        cardiovascular = 2
    if dopamine > 5 or epinephrine > 0 or norepinephrine > 0:
        cardiovascular = 3
    if dopamine > 15 or epinephrine > 0.1 or norepinephrine > 0.1:
        cardiovascular = 4
    renal = max(bisect_right((1.2, 2.0, 3.5, 5.0), creatinine_mg_dl),
                4 if urine_ml_24h < 200 else 3 if urine_ml_24h < 500 else 0)
    components = {
        "respiration": respiration,
        "coagulation": sum(platelets_10e9_l < t for t in (150, 100, 50, 20)),
        "liver": bisect_right((1.2, 2.0, 6.0, 12.0), bilirubin_mg_dl),
        "cardiovascular": cardiovascular,
        "neurological": sum(glasgow_coma_scale < t for t in (15, 13, 10, 6)),
        "renal": renal,
    }
    return {"score": sum(components.values()), "components": components}
