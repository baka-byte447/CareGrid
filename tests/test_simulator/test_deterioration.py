from datetime import datetime
from simulator.hospital.deterioration import news2
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.state import Bed, HospitalState
from simulator.patients.patient import Patient


def test_news2_and_icu_request():
    now = datetime(2026, 1, 1)
    patient = Patient("p", "51-65", 3, "General", 2, False, False, now,
                      status="ADMITTED", bed_id="w")
    state = HospitalState(beds={"w": Bed("w", "WARD", "W", "OCCUPIED", False)}, current_time=now)
    engine = SimulationEngine(state, [patient])
    engine.queue.schedule(now, "DETERIORATION", dict(patient_id="p", respiratory_rate=28,
                          spo2=91, systolic_bp=95, pulse=85, temperature=37, consciousness="A"))
    engine.run()
    assert patient.acuity == 5
    assert engine.transfer_requests == [dict(patient_id="p", destination="ICU", news2=8, timestamp=now)]


def test_oxygen_scales_and_single_red():
    assert news2(12, 96, 120, 65, 37, "A") == (0, "low")
    assert news2(12, 99, 120, 65, 37, "C") == (3, "single_red")
    assert news2(12, 97, 120, 65, 37, "A", True, 2) == (5, "medium")


def test_classic_sofa_scores_worst_daily_values():
    from simulator.hospital.deterioration import classic_sofa
    normal = dict(pao2_fio2_mmhg=400, respiratory_support=False, platelets_10e9_l=150,
                  bilirubin_mg_dl=1, map_mmhg=70, dopamine=0, dobutamine=0, epinephrine=0,
                  norepinephrine=0, glasgow_coma_scale=15, creatinine_mg_dl=1, urine_ml_24h=500)
    assert classic_sofa(**normal)["score"] == 0
    severe = dict(normal, pao2_fio2_mmhg=90, respiratory_support=True, platelets_10e9_l=15,
                  bilirubin_mg_dl=13, norepinephrine=.2, glasgow_coma_scale=5, urine_ml_24h=150)
    assert classic_sofa(**severe)["score"] == 24
