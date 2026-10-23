"""API tests for /allocation/recommend and /allocation/approve.

The key test is the parity check: for hospitals in several different states the
API's recommendation must equal what the simulator's own `decide_bed` returns for
the same patient and the same state, so the backend can never silently drift from
the rules the RL agent is trained against."""
import pytest

from backend.models import Bed, Equipment, Patient
from simulator.hospital.allocation_rules import decide_bed
from simulator.hospital.loader import load_hospital_state, load_patients

from .conftest import DATA_DIR

PATTERNS = ["empty", "icu_full", "no_ventilators", "no_isolation_beds", "half_full"]


def _pattern_sets(beds, vents, name):
    """-> (bed_ids to mark OCCUPIED, ventilator ids to mark IN_USE)"""
    beds = sorted(beds, key=lambda b: b.bed_id)
    vents = sorted(vents, key=lambda e: e.equipment_id)
    if name == "empty":
        return set(), set()
    if name == "icu_full":
        return {b.bed_id for b in beds if b.bed_type == "ICU"}, set()
    if name == "no_ventilators":
        return set(), {e.equipment_id for e in vents}
    if name == "no_isolation_beds":
        return {b.bed_id for b in beds if b.isolation_capable}, set()
    if name == "half_full":
        return ({b.bed_id for i, b in enumerate(beds) if i % 2 == 0},
                {e.equipment_id for i, e in enumerate(vents) if i % 2 == 0})
    raise AssertionError(name)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_api_recommendation_matches_simulator_rules(client, db_session, pattern):
    sim_state = load_hospital_state(DATA_DIR)            # same beds, started empty
    sim_patients = load_patients(DATA_DIR)

    occupied, in_use = _pattern_sets(sim_state.beds.values(),
                                     [e for e in sim_state.equipment.values()
                                      if e.type == "VENTILATOR"], pattern)
    for bed_id in occupied:
        sim_state.beds[bed_id].status = "OCCUPIED"
        db_session.get(Bed, bed_id).status = "OCCUPIED"
    for eq_id in in_use:
        sim_state.equipment[eq_id].status = "IN_USE"
        db_session.get(Equipment, eq_id).status = "IN_USE"
    db_session.commit()

    for patient in sim_patients[:250]:
        expected = decide_bed(patient, sim_state)
        body = client.post("/allocation/recommend",
                           json={"patient_id": patient.patient_id}).json()
        if expected is None:
            assert body["status"] == "NO_SUITABLE_BED", patient.patient_id
            assert body["recommended_bed_id"] is None
        else:
            assert body["status"] == "RECOMMENDED", patient.patient_id
            assert body["recommended_bed_id"] == expected.bed_id, patient.patient_id


def test_response_contract_and_reason_strings(client, db_session):
    # critical ventilated patient on an empty hospital -> ICU bed
    crit = (db_session.query(Patient)
            .filter(Patient.acuity == 5, Patient.ventilator_required.is_(True)).first())
    body = client.post("/allocation/recommend", json={"patient_id": crit.patient_id}).json()
    assert set(body) == {"patient_id", "recommended_bed_id", "algorithm", "reason", "status"}
    assert body["algorithm"] == "rule_based"
    assert body["status"] == "RECOMMENDED"
    assert body["reason"] == "Compatible ICU bed available"
    assert db_session.get(Bed, body["recommended_bed_id"]).bed_type == "ICU"

    # no ventilator free -> specific reason, no bed
    db_session.query(Equipment).filter(Equipment.type == "VENTILATOR").update(
        {Equipment.status: "IN_USE"})
    db_session.commit()
    body = client.post("/allocation/recommend", json={"patient_id": crit.patient_id}).json()
    assert body["status"] == "NO_SUITABLE_BED"
    assert body["reason"] == "No available ventilator"

    # no ICU bed free (and no ventilator needed) -> generic reason
    plain = (db_session.query(Patient)
             .filter(Patient.acuity == 5, Patient.ventilator_required.is_(False)).first())
    db_session.query(Bed).filter(Bed.bed_type == "ICU").update({Bed.status: "OCCUPIED"})
    db_session.commit()
    body = client.post("/allocation/recommend", json={"patient_id": plain.patient_id}).json()
    assert body["status"] == "NO_SUITABLE_BED"
    assert body["reason"] == "No compatible available bed found"


def test_recommend_error_cases(client, db_session):
    assert client.post("/allocation/recommend", json={"patient_id": "NOPE"}).status_code == 404

    p = db_session.query(Patient).first()
    p.acuity = 9
    db_session.commit()
    r = client.post("/allocation/recommend", json={"patient_id": p.patient_id})
    assert r.status_code == 400 and r.json()["detail"] == "Invalid patient acuity"

    p.acuity = 3
    p.current_status = "ADMITTED"
    db_session.commit()
    assert client.post("/allocation/recommend", json={"patient_id": p.patient_id}).status_code == 409


def test_approve_accepts_every_recommendation_the_api_makes(client, db_session):
    """Recommend and approve must agree on what is a valid bed. Sequentially admit
    patients (the hospital fills up as we go) and require every recommendation to
    be approvable."""
    approved = 0
    for p in load_patients(DATA_DIR)[:150]:
        rec = client.post("/allocation/recommend", json={"patient_id": p.patient_id}).json()
        if rec["status"] != "RECOMMENDED":
            continue
        r = client.post("/allocation/approve",
                        json={"patient_id": p.patient_id, "bed_id": rec["recommended_bed_id"]})
        assert r.status_code == 200, (p.patient_id, r.json())
        approved += 1
    assert approved > 50


def test_approve_rejects_wrong_tier_and_non_isolation_beds(client, db_session):
    crit = db_session.query(Patient).filter(Patient.acuity == 5,
                                            Patient.ventilator_required.is_(False),
                                            Patient.isolation_required.is_(False)).first()
    ward = db_session.query(Bed).filter(Bed.bed_type == "WARD").first()
    r = client.post("/allocation/approve",
                    json={"patient_id": crit.patient_id, "bed_id": ward.bed_id})
    assert r.status_code == 400
    assert r.json()["detail"] == "Bed type is incompatible with patient acuity"

    iso = db_session.query(Patient).filter(Patient.acuity == 1,
                                           Patient.isolation_required.is_(True)).first()
    plain_ward = db_session.query(Bed).filter(Bed.bed_type == "WARD",
                                              Bed.isolation_capable.is_(False)).first()
    r = client.post("/allocation/approve",
                    json={"patient_id": iso.patient_id, "bed_id": plain_ward.bed_id})
    assert r.status_code == 400
    assert r.json()["detail"] == "Patient requires an isolation-capable bed"
