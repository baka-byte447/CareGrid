"""A single hospital admission for a permanent patient identity.

Encounter statuses: WAITING (awaiting allocation), ADMITTED (currently in
care), and DISCHARGED (closed admission). A future lifecycle service owns
transitions between these states.
"""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class Encounter(Base):
    __tablename__ = "encounters"
    __table_args__ = (
        CheckConstraint("status IN ('WAITING', 'ADMITTED', 'DISCHARGED')", name="ck_encounters_status"),
        CheckConstraint("discharged_at IS NULL OR admitted_at IS NULL OR discharged_at >= admitted_at", name="ck_encounters_discharge_after_admit"),
        Index("ix_encounters_patient_status", "patient_id", "status"),
    )

    encounter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id", ondelete="RESTRICT"), nullable=False)
    acuity: Mapped[int] = mapped_column(Integer, nullable=False)
    clinical_risk: Mapped[str | None] = mapped_column(String(20))
    specialty: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_los: Mapped[float] = mapped_column(Float, nullable=False)
    isolation_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ventilator_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="WAITING", server_default="WAITING")

    patient: Mapped["Patient"] = relationship(back_populates="encounters")
    bed_assignments: Mapped[list["BedAssignment"]] = relationship(back_populates="encounter")
    equipment_assignments: Mapped[list["EquipmentAssignment"]] = relationship(back_populates="encounter")
