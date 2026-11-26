from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db.database import get_db
from backend.models import AuditLog, Bed, BedAssignment, Encounter, Patient, TelemetryRecord
from simulator.hospital.deterioration import classic_sofa, news2

router = APIRouter()


class ClassicSofaAssessment(BaseModel):
    """Worst daily inputs. Catecholamines are in micrograms/kg/min for at least one hour."""
    pao2_fio2_mmhg: float = Field(gt=0, allow_inf_nan=False)
    respiratory_support: bool
    platelets_10e9_l: float = Field(ge=0, allow_inf_nan=False)
    bilirubin_mg_dl: float = Field(ge=0, allow_inf_nan=False)
    map_mmhg: float = Field(ge=0, le=400)
    dopamine: float = Field(ge=0, allow_inf_nan=False)
    dobutamine: float = Field(ge=0, allow_inf_nan=False)
    epinephrine: float = Field(ge=0, allow_inf_nan=False)
    norepinephrine: float = Field(ge=0, allow_inf_nan=False)
    glasgow_coma_scale: int = Field(ge=3, le=15)
    creatinine_mg_dl: float = Field(ge=0, allow_inf_nan=False)
    urine_ml_24h: float = Field(ge=0, allow_inf_nan=False)


class TelemetryRecordRequest(BaseModel):
    sofa: ClassicSofaAssessment | None = None
    respiratory_rate: int = Field(ge=0, le=150)
    spo2: float = Field(ge=0, le=100)
    systolic_bp: int = Field(ge=0, le=400)
    pulse: int = Field(ge=0, le=400)
    temperature: float = Field(ge=20, le=50, multiple_of=0.1)
    consciousness: Literal["A", "C", "V", "P", "U"]
    supplemental_oxygen: bool
    oxygen_scale: Literal[1, 2] = 1

    @field_validator("consciousness", mode="before")
    @classmethod
    def normalize_consciousness(cls, value):
        names = {"ALERT": "A", "NEW CONFUSION": "C", "VOICE": "V", "PAIN": "P", "UNRESPONSIVE": "U"}
        value = value.strip().upper() if isinstance(value, str) else value
        return names.get(value, value) if isinstance(value, str) else value


@router.post("/patients/{patient_id}/telemetry", status_code=201)
def record_telemetry(patient_id: str, request: TelemetryRecordRequest,
                     db: Session = Depends(get_db), user=Depends(require_permission("patients:intake"))):
    patient = db.get(Patient, patient_id, with_for_update=True)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    if patient.age_group == "0-17":
        raise HTTPException(422, "This intake profile requires an adult patient for NEWS2")
    encounter = db.scalar(select(Encounter).where(Encounter.patient_id == patient_id,
                          Encounter.status == "ADMITTED").with_for_update())
    if encounter is None:
        raise HTTPException(409, "Telemetry requires an admitted encounter")
    bed = db.scalar(select(Bed).join(BedAssignment).where(
        BedAssignment.encounter_id == encounter.encounter_id, BedAssignment.released_at.is_(None)))
    if bed is None:
        raise HTTPException(409, "Active bed assignment is missing")
    observations = request.model_dump(exclude={"sofa"})
    score, risk = news2(**observations)
    sofa = None
    if request.sofa:
        inputs = request.sofa.model_dump()
        sofa = classic_sofa(**inputs)
        observations["classic_sofa"] = {"inputs": inputs, **sofa}
    encounter.clinical_risk = risk
    transfer = score >= 7 and bed.bed_type in ("WARD", "STEP_DOWN")
    if score >= 7:
        patient.acuity = encounter.acuity = 5
        db.add(AuditLog(patient_id=patient_id, bed_id=bed.bed_id, action="NEWS2_EMERGENCY", algorithm="news2"))
    if transfer:
        db.add(AuditLog(patient_id=patient_id, bed_id=bed.bed_id, action="ICU_TRANSFER_REQUEST", algorithm="news2"))
    db.add(TelemetryRecord(encounter_id=encounter.encounter_id, observations=observations,
                           score=score, risk=risk, transfer_requested=transfer))
    db.commit()
    return {"encounter_id": encounter.encounter_id, "news2": score, "risk": risk, "transfer_requested": transfer, "classic_sofa": sofa}


@router.get("/clinical/activity")
def clinical_activity(db: Session = Depends(get_db), user=Depends(require_permission("patients:read"))):
    from backend.models import FhirResource
    rows = db.execute(select(TelemetryRecord, Encounter.patient_id).join(Encounter)
                      .order_by(TelemetryRecord.id.desc()).limit(20))
    return {
        "telemetry": [{"patient_id": pid, "observed_at": record.observed_at, "news2": record.score,
                       "risk": record.risk, "transfer_requested": record.transfer_requested,
                       "sofa": record.observations.get("classic_sofa", {}).get("score")}
                      for record, pid in rows],
        "fhir_encounters": db.scalars(select(FhirResource.reference).where(
            FhirResource.reference.like("Encounter/%")).order_by(FhirResource.reference).limit(20)).all(),
    }
