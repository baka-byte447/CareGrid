"""Persistent history for allocation recommendations.

Recommendation records are separate from AuditLog action events. A row stores
the recommendation that was shown, including failed and safety-intervened
results, without implying that any resource was assigned.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class AllocationRecommendation(Base):
    __tablename__ = "allocation_recommendations"
    __table_args__ = (
        Index("ix_allocation_recommendations_patient_created", "patient_id", "created_at"),
        Index("ix_allocation_recommendations_encounter_created", "encounter_id", "created_at"),
        Index("ix_allocation_recommendations_status_created", "status", "created_at"),
        Index("ix_allocation_recommendations_decision_status_decided_at", "decision_status", "decided_at"),
        Index("ix_allocation_recommendations_decided_by", "decided_by"),
    )

    recommendation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.patient_id", ondelete="RESTRICT"), nullable=False
    )
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.encounter_id", ondelete="SET NULL"), nullable=True
    )
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    recommended_bed_id: Mapped[str | None] = mapped_column(
        ForeignKey("beds.bed_id", ondelete="SET NULL"), nullable=True
    )
    proposed_action: Mapped[int | None] = mapped_column(Integer)
    final_action: Mapped[int | None] = mapped_column(Integer)
    proposed_bed_type: Mapped[str | None] = mapped_column(String(30))
    final_bed_type: Mapped[str | None] = mapped_column(String(30))
    safety_overridden: Mapped[bool | None] = mapped_column(Boolean)
    safety_rule_triggered: Mapped[str | None] = mapped_column(String(100))
    safety_original_action: Mapped[int | None] = mapped_column(Integer)
    safety_reason: Mapped[str | None] = mapped_column(Text)
    q_values: Mapped[list[float] | None] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_status: Mapped[str | None] = mapped_column(String(30))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_allocation_recommendations_decided_by_users",
        ),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient = relationship("Patient")
    encounter = relationship("Encounter")
    recommended_bed = relationship("Bed")
    requester = relationship("User", foreign_keys=[requested_by])
    decider = relationship("User", foreign_keys=[decided_by])
