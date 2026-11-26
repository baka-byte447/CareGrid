from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.database import Base


class FhirResource(Base):
    __tablename__ = "fhir_resources"
    reference: Mapped[str] = mapped_column(String(80), primary_key=True)
    local_id: Mapped[str] = mapped_column(String(64))
    resource: Mapped[dict] = mapped_column(JSON)


class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.encounter_id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    observations: Mapped[dict] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer)
    risk: Mapped[str] = mapped_column(String(20))
    transfer_requested: Mapped[bool]


class SurgeSimulationRun(Base):
    __tablename__ = "surge_simulation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    parameters: Mapped[dict] = mapped_column(JSON)
    operations: Mapped[dict] = mapped_column(JSON)
