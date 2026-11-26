"""FHIR R4 intake profile. Location references name CareGrid beds."""
from fhirclient.models.bundle import Bundle as R4Bundle
from fhirclient.models.encounter import Encounter as R4Encounter
from fhirclient.models.fhirabstractbase import FHIRValidationError
from datetime import date, datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from fastapi import APIRouter, Body, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db.database import get_db
from backend.models import BedAssignment, Encounter, Equipment, FhirResource, Patient
from backend.services.patient_lifecycle import (
    LifecycleError, approve_encounter, close_waiting_encounter, create_encounter, discharge_encounter, transfer_encounter,
)

class IntakeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                return outcome("; ".join(error["msg"] for error in exc.errors()))

        return handle


router = APIRouter(route_class=IntakeRoute)
FHIR_JSON = "application/fhir+json"
FhirId = Annotated[str, Field(pattern=r"^[A-Za-z0-9.-]{1,64}$")]


class Element(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def check_modifiers(cls, data):
        if isinstance(data, dict) and data.get("modifierExtension"):
            raise ValueError("Unsupported modifierExtension")
        return data


class Reference(Element):
    reference: str


class Coding(Element):
    code: str
    system: str | None = None


class Concept(Element):
    coding: list[Coding] = Field(default_factory=list)
    text: str | None = None


class Resource(Element):
    id: FhirId | None = None


class PatientResource(Resource):
    resourceType: Literal["Patient"]
    birthDate: date | None = None


class Period(Element):
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.start and self.end:
            if self.start.tzinfo is None or self.end.tzinfo is None or self.end < self.start:
                raise ValueError("Expected an ordered period with time zones")
        return self


class Location(Element):
    location: Reference
    status: Literal["planned", "active", "reserved", "completed"] | None = None


class EncounterResource(Resource):
    resourceType: Literal["Encounter"]
    status: Literal["planned", "arrived", "in-progress", "finished"]
    class_: Coding = Field(alias="class")
    subject: Reference
    period: Period = Field(default_factory=Period)
    location: list[Location] = Field(default_factory=list)


class ConditionResource(Resource):
    resourceType: Literal["Condition"]
    subject: Reference
    severity: Concept | None = None


class DeviceResource(Resource):
    resourceType: Literal["Device"]
    type: Concept | None = None
    location: Reference | None = None
    status: Literal["active", "inactive", "entered-in-error", "unknown"] | None = None


Inbound = Annotated[Union[PatientResource, EncounterResource, ConditionResource, DeviceResource],
                    Field(discriminator="resourceType")]


class EntryRequest(Element):
    method: Literal["POST", "PUT"]
    url: str


class Entry(Element):
    resource: Inbound
    request: EntryRequest
    fullUrl: str | None = None


class Bundle(Element):
    resourceType: Literal["Bundle"]
    type: Literal["transaction"]
    entry: list[Entry] = Field(min_length=1)


def local_reference(reference, kind, aliases):
    ref = aliases.get(reference, reference)
    parts = ref.split("/")
    if len(parts) != 2 or parts[0] != kind:
        raise ValueError(f"Expected a local {kind} reference")
    return TypeAdapter(FhirId).validate_python(parts[1])


def patient_for(db, subject, aliases):
    external = local_reference(subject.reference, "Patient", aliases)
    mapping = db.get(FhirResource, f"Patient/{external}")
    patient = db.get(Patient, mapping.local_id if mapping else external, with_for_update=True)
    if patient is None:
        raise ValueError("Unknown Patient reference")
    return patient


def ingest_patient(db, resource, local, mapped, ref, triage):
    if not mapped and len(local) > 10:
        local = "P" + uuid4().hex[:9]
    patient = db.get(Patient, local, with_for_update=True)
    if patient is None:
        if ref not in triage:
            raise ValueError("New patients require a Condition severity coding using urn:caregrid:acuity")
        patient = Patient(patient_id=local, age_group="Unknown", acuity=triage[ref], specialty="General",
                          predicted_los=3, isolation_required=False, ventilator_required=False,
                          arrival_time=datetime.now(timezone.utc), current_status="DISCHARGED")
        db.add(patient)
    for extension in (resource.model_extra or {}).get("extension", []):
        name = extension.get("url")
        if name in ("urn:caregrid:isolation-required", "urn:caregrid:ventilator-required"):
            value = extension.get("valueBoolean")
            if type(value) is not bool:
                raise ValueError("Resource requirement extension needs valueBoolean")
            if name == "urn:caregrid:isolation-required":
                patient.isolation_required = value
            else:
                patient.ventilator_required = value
    if resource.birthDate:
        today = date.today()
        age = today.year - resource.birthDate.year - ((today.month, today.day) < (resource.birthDate.month, resource.birthDate.day))
        if age < 0:
            raise ValueError("Patient birthDate is in the future")
        patient.age_group = "0-17" if age < 18 else "18-35" if age <= 35 else "36-50" if age <= 50 else "51-65" if age <= 65 else "65+"
    return local


def ingest_condition(db, resource, aliases):
    patient = patient_for(db, resource.subject, aliases)
    local = patient.patient_id
    for coding in resource.severity.coding if resource.severity else []:
        if coding.system == "urn:caregrid:acuity":
            if coding.code not in ("1", "2", "3", "4", "5"):
                raise ValueError("CareGrid acuity must be 1 through 5")
            patient.acuity = int(coding.code)
            active = db.scalar(select(Encounter).where(Encounter.patient_id == local, Encounter.status != "DISCHARGED"))
            if active:
                active.acuity = patient.acuity
    return local


def ingest_device(db, resource, local, mapped, aliases):
    if not mapped and len(local) > 10:
        local = "E" + uuid4().hex[:9]
    device = db.get(Equipment, local, with_for_update=True)
    if device is None:
        device = Equipment(equipment_id=local, type="UNKNOWN", location="Unknown", status="MAINTENANCE")
        db.add(device)
    if resource.type:
        name = resource.type.text or next((c.code for c in resource.type.coding), "UNKNOWN")
        device.type = name.upper()[:50]
    if resource.location:
        device.location = local_reference(resource.location.reference, "Location", aliases)[:50]
    if resource.status in ("inactive", "entered-in-error") and device.status != "IN_USE":
        device.status = "MAINTENANCE"
    return local


def ingest_encounter(db, resource, local, mapped, aliases, actor):
    patient = patient_for(db, resource.subject, aliases)
    enc = db.get(Encounter, int(local), with_for_update=True) if mapped else create_encounter(
        db, patient.patient_id, arrival_time=resource.period.start or datetime.now(timezone.utc))
    if enc.patient_id != patient.patient_id:
        raise ValueError("Encounter subject cannot change")
    local = str(enc.encounter_id)
    if not mapped:
        patient.arrival_time = enc.arrival_time
    if resource.status == "in-progress":
        beds = [loc.location.reference for loc in resource.location if loc.status in (None, "active")]
        if len(beds) != 1:
            raise ValueError("An in-progress encounter requires one active bed location")
        bed = local_reference(beds[0], "Location", aliases)
        if enc.status == "WAITING":
            approve_encounter(db, enc.encounter_id, bed, actor_id=actor)
        elif enc.status == "ADMITTED":
            current = db.scalar(select(BedAssignment.bed_id).where(
                BedAssignment.encounter_id == enc.encounter_id, BedAssignment.released_at.is_(None)))
            if current != bed:
                transfer_encounter(db, enc.encounter_id, bed, actor_id=actor)
        else:
            raise ValueError("Encounter is closed")
    elif resource.status == "finished" and enc.status == "WAITING":
        close_waiting_encounter(db, enc.encounter_id, resource.period.end)
    elif resource.status == "finished" and enc.status != "DISCHARGED":
        discharge_encounter(db, enc.encounter_id, actor_id=actor)
    elif resource.status in ("planned", "arrived") and enc.status != "WAITING":
        raise ValueError("Encounter cannot return to waiting")
    return local


def ingest(db, resource, aliases, actor, triage):
    ref = f"{resource.resourceType}/{resource.id}"
    mapped = db.get(FhirResource, ref, with_for_update=True)
    local = mapped.local_id if mapped else resource.id
    payload = resource.model_dump(mode="json", by_alias=True, exclude_unset=True)
    payload["id"] = resource.id
    if mapped and mapped.resource == payload:
        return "200 OK"
    if isinstance(resource, PatientResource):
        local = ingest_patient(db, resource, local, mapped, ref, triage)
    elif isinstance(resource, ConditionResource):
        local = ingest_condition(db, resource, aliases)
    elif isinstance(resource, DeviceResource):
        local = ingest_device(db, resource, local, mapped, aliases)
    else:
        local = ingest_encounter(db, resource, local, mapped, aliases, actor)
    if mapped:
        mapped.resource = payload
    else:
        db.add(FhirResource(reference=ref, local_id=local, resource=payload))
    db.flush()
    return "200 OK" if mapped else "201 Created"


def outcome(detail):
    return JSONResponse({"resourceType": "OperationOutcome", "issue": [
        {"severity": "error", "code": "invalid", "diagnostics": detail}]},
        status_code=422, media_type=FHIR_JSON)


def process(payload, db, actor):
    try:
        bundle = isinstance(payload, Bundle)
        data = payload.model_dump(mode="json", by_alias=True, exclude_unset=True)
        if bundle:
            R4Bundle(data)
            entries = payload.entry
        else:
            R4Encounter(data)
            entries = [Entry(resource=payload, request=EntryRequest(method="POST", url="Encounter"))]
        aliases = {}
        resources = {}
        for entry in entries:
            if set(entry.request.model_extra or {}) & {"ifMatch", "ifNoneExist", "ifNoneMatch", "ifModifiedSince"}:
                raise ValueError("Conditional writes are unsupported by the intake profile")
            r = entry.resource
            if entry.request.method == "PUT":
                identity = local_reference(entry.request.url, r.resourceType, {})
                if r.id and r.id != identity:
                    raise ValueError("PUT id mismatch")
                r.id = identity
            elif entry.request.url != r.resourceType:
                raise ValueError("POST target must match resource type")
            r.id = r.id or uuid4().hex
            ref = f"{r.resourceType}/{r.id}"
            if ref in resources or (entry.fullUrl and entry.fullUrl in aliases):
                raise ValueError("Duplicate transaction identity")
            resources[ref] = r
            if entry.fullUrl:
                aliases[entry.fullUrl] = ref
        priority = {"Patient": 0, "Condition": 1, "Device": 2, "Encounter": 3}
        triage = {}
        for r in resources.values():
            if isinstance(r, ConditionResource) and r.severity:
                for coding in r.severity.coding:
                    if coding.system == "urn:caregrid:acuity":
                        if coding.code not in ("1", "2", "3", "4", "5"):
                            raise ValueError("Invalid acuity code")
                        subject = "Patient/" + local_reference(r.subject.reference, "Patient", aliases)
                        if subject in triage and triage[subject] != int(coding.code):
                            raise ValueError("Conflicting triage values")
                        triage[subject] = int(coding.code)
        statuses = {ref: ingest(db, resources[ref], aliases, actor, triage)
                    for ref in sorted(resources, key=lambda key: priority[resources[key].resourceType])}
        result = ({"resourceType": "Bundle", "type": "transaction-response",
                   "entry": [{"response": {"status": statuses[ref], "location": ref}} for ref in resources]}
                  if bundle else next(iter(resources.values())).model_dump(mode="json", by_alias=True, exclude_unset=True))
        db.commit()
        return JSONResponse(result, status_code=201, media_type=FHIR_JSON)
    except (ValidationError, FHIRValidationError, ValueError, LifecycleError, IntegrityError) as exc:
        db.rollback()
        if isinstance(exc, ValidationError):
            detail = "; ".join(e["msg"] for e in exc.errors(include_input=False))
        elif isinstance(exc, FHIRValidationError):
            detail = "Resource fails FHIR R4 schema validation"
        else:
            detail = "Resource conflicts with an existing record" if isinstance(exc, IntegrityError) else str(exc)
        return outcome(detail)


@router.post("/Encounter", status_code=201)
def post_encounter(payload: Annotated[EncounterResource, Body(media_type=FHIR_JSON)],
                   db: Session = Depends(get_db), user=Depends(require_permission("patients:intake"))):
    return process(payload, db, user.id)


@router.post("/Bundle", status_code=201)
def post_bundle(payload: Annotated[Bundle, Body(media_type=FHIR_JSON)],
                db: Session = Depends(get_db), user=Depends(require_permission("patients:intake"))):
    return process(payload, db, user.id)
